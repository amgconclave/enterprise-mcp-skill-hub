from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import WorkerRunbookPackRequest, WorkerSkillRunRequest

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
    assert run.sandbox_decision is not None
    assert run.sandbox_decision.decision == "allow"
    assert [event.stage for event in run.timeline] == [
        "queued",
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
    assert run.sandbox_decision is not None
    assert run.sandbox_decision.decision == "deny"
    assert "action_class_blocked" in run.sandbox_decision.matched_rules
    assert any(event.stage == "sandbox_denied" for event in run.timeline)


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

    assert plan.readiness_status in {"ready", "needs_review"}
    assert plan.summary["run_count"] == 1
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
    assert "worker scale-out" in bundle["architecture_patterns"]


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
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Worker Scale-Out" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/workers/scale-plan" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/worker_runbooks/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/worker_runbooks" for item in inventory.items)
    assert any(item["path"] == "/workers/scale-plan" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /workers/runbook-pack"
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
