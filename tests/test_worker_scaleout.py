from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    WorkerQueueAdmissionDecision,
    WorkerQueueAdmissionPackRequest,
    WorkerRunbookPackRequest,
    WorkerSkillRunRecord,
    WorkerSkillRunRequest,
)
from app.utils import new_id, new_trace_id, utc_now

HEADERS = {"X-API-Key": "dev-local-token"}


async def test_worker_run_records_sandbox_preflight_and_invocation_trace() -> None:
    state = create_state()

    run = await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="search_knowledge_base",
            input={"query": "AI governance policy", "limit": 2},
            actor="pytest-worker",
            worker_pool="retrieval_heavy",
            enforce_sandbox=True,
        )
    )

    assert run.status == "succeeded"
    assert run.invocation_id
    assert run.output
    assert run.queue_decision is not None
    assert run.queue_decision.decision == "admit"
    assert run.sandbox_decision is not None
    assert run.sandbox_decision.decision == "allow"
    assert [event.stage for event in run.timeline] == [
        "queued",
        "queue_admission",
        "sandbox_preflight",
        "dispatched",
        "invocation_succeeded",
    ]
    assert any(event.action == "worker_run.succeeded" for event in state.audit.events)


async def test_worker_run_stops_before_execution_when_sandbox_denies() -> None:
    state = create_state()

    run = await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="extract_entities",
            input={"text": "write a file"},
            actor="pytest-worker",
            worker_pool="governance_review",
            enforce_sandbox=True,
            policy_context={"action_class": "filesystem_write"},
        )
    )

    assert run.status == "failed"
    assert run.invocation_id is None
    assert run.output is None
    assert run.queue_decision is not None
    assert run.queue_decision.decision == "admit"
    assert run.sandbox_decision is not None
    assert run.sandbox_decision.decision == "deny"
    assert "action_class_blocked" in run.sandbox_decision.matched_rules
    assert any(event.stage == "sandbox_denied" for event in run.timeline)


async def test_worker_queue_admission_defers_when_pool_is_saturated() -> None:
    state = create_state()
    seed_trace = new_trace_id()
    seed_decision = WorkerQueueAdmissionDecision(
        decision_id=new_id("wad"),
        generated_at=utc_now(),
        decision="admit",
        tenant="internal_demo",
        skill_id="classify_request",
        worker_pool="governance_review",
        priority=5,
        fairness_share={},
        pool_pressure={},
        matched_rules=["seeded_running_run"],
        reasons=["Seeded running worker to simulate local pool pressure."],
        trace_id=seed_trace,
    )
    state.worker_scaleout.runs.append(
        WorkerSkillRunRecord(
            run_id=new_id("wrn"),
            created_at=utc_now(),
            updated_at=utc_now(),
            status="running",
            skill_id="classify_request",
            actor="pytest-seed",
            worker_pool="governance_review",
            priority=5,
            input={"request": "Seeded active run."},
            trace_id=seed_trace,
            queue_decision=seed_decision,
            timeline=[],
        )
    )

    run = await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="classify_request",
            input={"request": "Queue me while governance review is saturated."},
            actor="pytest-worker",
            tenant="healthcare",
            worker_pool="governance_review",
            allow_queue=True,
        )
    )
    report = state.worker_scaleout.queue_admission_report()

    assert run.status == "queued"
    assert run.invocation_id is None
    assert run.queue_decision is not None
    assert run.queue_decision.decision == "queue"
    assert "pool_concurrency_saturated" in run.queue_decision.matched_rules
    assert report.summary["queued_count"] == 1
    assert any(pool["pool_id"] == "governance_review" for pool in report.pool_queue_status)


async def test_worker_queue_admission_rejects_blocked_action_before_sandbox() -> None:
    state = create_state()

    run = await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="extract_entities",
            input={"text": "Try to read secrets before admission."},
            actor="pytest-worker",
            worker_pool="governance_review",
            policy_context={"action_class": "secret_access"},
        )
    )

    assert run.status == "failed"
    assert run.invocation_id is None
    assert run.sandbox_decision is None
    assert run.queue_decision is not None
    assert run.queue_decision.decision == "reject"
    assert "blocked_action_class_at_admission" in run.queue_decision.matched_rules
    assert any(event.stage == "queue_admission" for event in run.timeline)
    assert any(event.action == "worker_run.rejected" for event in state.audit.events)


async def test_worker_scale_plan_and_runbook_pack(tmp_path: Path) -> None:
    state = create_state()
    state.worker_scaleout.output_dir = tmp_path / "worker_runbooks"
    await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="classify_request",
            input={"request": "Security review needed for an enterprise AI workflow."},
            actor="pytest-worker",
            worker_pool="governance_review",
        )
    )

    plan = await state.worker_scaleout.scale_plan()
    pack = await state.worker_scaleout.runbook_pack(
        WorkerRunbookPackRequest(actor="pytest-platform-sre")
    )
    queue_pack = state.worker_scaleout.queue_admission_pack(
        WorkerQueueAdmissionPackRequest(actor="pytest-platform-sre")
    )

    assert plan.readiness_status in {"ready", "needs_review"}
    assert plan.summary["run_count"] == 1
    assert plan.summary["admission_decision_count"] == 1
    assert {pool.pool_id for pool in plan.pools} == {
        "local_mock_general",
        "retrieval_heavy",
        "governance_review",
    }
    assert any(row["skill_id"] == "classify_request" for row in plan.backlog_by_skill)
    assert Path(pack.json_path).exists()
    assert Path(pack.markdown_path).exists()
    bundle = json.loads(Path(pack.json_path).read_text(encoding="utf-8"))
    assert "worker_scale_plan" in bundle
    assert "queue_admission" in bundle
    assert "worker scale-out" in bundle["architecture_patterns"]
    assert Path(queue_pack.json_path).exists()
    assert Path(queue_pack.markdown_path).exists()
    queue_bundle = json.loads(Path(queue_pack.json_path).read_text(encoding="utf-8"))
    assert "queue_admission" in queue_bundle
    assert "state observation" in queue_bundle["architecture_patterns"]


def test_worker_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.worker_scaleout.output_dir = tmp_path / "worker_runbooks"
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    run_response = client.post(
        "/workers/runs",
        headers=HEADERS,
        json={
            "skill_id": "search_knowledge_base",
            "input": {"query": "AI governance policy", "limit": 2},
            "actor": "pytest-worker",
            "worker_pool": "retrieval_heavy",
            "enforce_sandbox": True,
        },
    )
    runs_response = client.get("/workers/runs", headers=HEADERS)
    plan_response = client.get("/workers/scale-plan", headers=HEADERS)
    queue_response = client.get("/workers/queue-admission", headers=HEADERS)
    queue_pack_response = client.post(
        "/workers/queue-pack",
        headers=HEADERS,
        json={"actor": "pytest-platform-sre"},
    )
    pack_response = client.post(
        "/workers/runbook-pack",
        headers=HEADERS,
        json={"actor": "pytest-platform-sre"},
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert run_response.status_code == 200
    assert run_response.json()["status"] == "succeeded"
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 1
    assert plan_response.status_code == 200
    assert plan_response.json()["summary"]["run_count"] == 1
    assert queue_response.status_code == 200
    assert queue_response.json()["summary"]["decision_count"] == 1
    assert queue_pack_response.status_code == 200
    assert Path(queue_pack_response.json()["json_path"]).exists()
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Worker Scale-Out" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/workers/scale-plan" for endpoint in smoke.endpoint_references)
    assert any(endpoint["path"] == "/workers/queue-admission" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/worker_runbooks/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/worker_runbooks" for item in inventory.items)
    assert any(item["path"] == "/workers/scale-plan" for item in api_contract.docs_api_coverage)
    assert any(item["path"] == "/workers/queue-admission" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /workers/runbook-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
    assert any(
        item["producer_endpoint"] == "POST /workers/queue-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )


def test_worker_endpoint_404_for_unknown_skill() -> None:
    state = create_state()
    main_module.state = state
    client = TestClient(app)

    response = client.post(
        "/workers/runs",
        headers=HEADERS,
        json={"skill_id": "missing_skill", "input": {}},
    )

    assert response.status_code == 404
