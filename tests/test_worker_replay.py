from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    PolicyInvocationContext,
    WorkerRunReplayPackRequest,
    WorkerRunReplayRequest,
    WorkerSkillRunRequest,
)

HEADERS = {"X-API-Key": "dev-local-token"}


async def test_worker_replay_matches_clean_local_worker_run() -> None:
    state = create_state()
    original = await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="search_knowledge_base",
            input={"query": "AI governance policy", "limit": 2},
            actor="pytest-worker",
            tenant="healthcare",
            worker_pool="retrieval_heavy",
            enforce_sandbox=True,
        )
    )

    report = await state.worker_scaleout.replay_report(
        WorkerRunReplayRequest(actor="pytest-replay", run_ids=[original.run_id])
    )

    assert report.readiness_status == "ready"
    assert report.summary["comparison_count"] == 1
    assert report.summary["drift_count"] == 0
    comparison = report.comparisons[0]
    assert comparison.original_run_id == original.run_id
    assert comparison.replay_run_id != original.run_id
    assert comparison.status_match is True
    assert comparison.output_match is True
    assert comparison.queue_decision_match is True
    assert comparison.sandbox_decision_match is True
    assert comparison.timeline_stage_match is True
    assert comparison.drift_flags == []
    replay = next(run for run in state.worker_scaleout.runs if run.run_id == comparison.replay_run_id)
    assert replay.transparency["replay_of_run_id"] == original.run_id
    assert any(event.action == "worker_replay.report_generated" for event in state.audit.events)


async def test_worker_replay_preserves_sandbox_denied_checkpoint() -> None:
    state = create_state()
    original = await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="extract_entities",
            input={"text": "try to write a local file"},
            actor="pytest-worker",
            worker_pool="governance_review",
            policy_context=PolicyInvocationContext(action_class="filesystem_write"),
            enforce_sandbox=True,
        )
    )

    report = await state.worker_scaleout.replay_report(
        WorkerRunReplayRequest(actor="pytest-replay", run_ids=[original.run_id])
    )

    comparison = report.comparisons[0]
    assert original.status == "failed"
    assert comparison.status_match is True
    assert comparison.sandbox_decision_match is True
    assert comparison.timeline_stage_match is True
    assert comparison.drift_flags == []


async def test_worker_replay_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.worker_scaleout.replay_output_dir = tmp_path / "worker_replays"
    await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="classify_request",
            input={"request": "Security review needed for an enterprise AI workflow."},
            actor="pytest-worker",
            worker_pool="governance_review",
            enforce_sandbox=True,
        )
    )

    export = await state.worker_scaleout.replay_pack(
        WorkerRunReplayPackRequest(actor="pytest-replay", max_replays=1)
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "worker_run_replay_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "worker_run_replay" in bundle
    assert "step verification" in bundle["architecture_patterns"]
    assert "Worker Run Replay Pack" in markdown
    assert "Replay Comparisons" in markdown
    assert any(event.action == "worker_replay.pack_exported" for event in state.audit.events)


def test_worker_replay_endpoints_dashboard_artifacts_contract_and_demo(tmp_path: Path) -> None:
    state = create_state()
    state.worker_scaleout.replay_output_dir = tmp_path / "worker_replays"
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
            "tenant": "healthcare",
            "worker_pool": "retrieval_heavy",
            "enforce_sandbox": True,
        },
    )
    report_response = client.post(
        "/workers/replay-report",
        headers=HEADERS,
        json={"actor": "pytest-replay", "run_ids": [run_response.json()["run_id"]]},
    )
    pack_response = client.post(
        "/workers/replay-pack",
        headers=HEADERS,
        json={"actor": "pytest-replay", "max_replays": 1},
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert run_response.status_code == 200
    assert report_response.status_code == 200
    assert report_response.json()["summary"]["comparison_count"] == 1
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Worker Replay" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/workers/replay-report" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/worker_replays/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/worker_replays" for item in inventory.items)
    assert any(item["path"] == "/workers/replay-report" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /workers/replay-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
