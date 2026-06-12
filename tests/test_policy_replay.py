from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import PolicyInvocationContext, PolicyReplayPackRequest
from app.services import PolicyReplayDriftService

HEADERS = {"X-API-Key": "dev-local-token"}


def policy_replay_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.policy_replay = PolicyReplayDriftService(
            state,
            output_dir=tmp_path / "policy_replay",
        )
        state.artifacts.output_dir = tmp_path / "artifact_indexes"
    return state


def test_policy_replay_report_runs_fresh_clone_baseline_scenarios() -> None:
    state = policy_replay_state()

    report = state.policy_replay.report(actor="pytest-policy-reviewer")
    record_ids = {record.record_id for record in report.records}

    assert report.report_id == "policy_replay_drift_latest"
    assert report.readiness_status == "ready"
    assert report.summary["baseline_scenario_count"] >= 3
    assert report.summary["drift_count"] == 0
    assert "baseline-agent-internal-allow" in record_ids
    assert "baseline-viewer-confidential-deny" in record_ids
    assert {"durable workflows", "human-in-the-loop", "governance"}.issubset(
        set(report.architecture_patterns)
    )
    assert any(event.action == "policy_replay.report_generated" for event in state.audit.events)


async def test_policy_replay_compares_historical_policy_decisions() -> None:
    state = policy_replay_state()

    denied = await state.invocation_service.invoke(
        "summarize_document",
        {"text": "Confidential board update."},
        "pytest-policy-denial",
        PolicyInvocationContext(role="viewer", data_sensitivity="confidential", enforce=True),
    )
    await state.invocation_service.invoke(
        "extract_entities",
        {"text": "Atlas Labs asked Priya Shah for a policy review."},
        "pytest-policy-needs-evidence",
        PolicyInvocationContext(role="agent", data_sensitivity="internal", enforce=False),
    )

    report = state.policy_replay.report(actor="pytest-policy-reviewer")
    by_id = {record.invocation_id: record for record in report.records if record.invocation_id}

    assert denied.id in by_id
    assert by_id[denied.id].original_decision == "deny"
    assert by_id[denied.id].replay_decision == "deny"
    assert by_id[denied.id].status == "stable"
    assert report.summary["historical_record_count"] == 2
    assert report.summary["needs_evidence_count"] == 1
    assert report.readiness_status == "needs_review"
    assert any(item["status"] == "evidence_required" for item in report.approval_queue)


def test_policy_replay_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = policy_replay_state(tmp_path)

    export = state.policy_replay.pack(PolicyReplayPackRequest(actor="pytest-policy-reviewer"))

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "policy_replay_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "policy_replay_report" in bundle
    assert "reviewer_checklist" in bundle
    assert "Policy Replay Drift Pack" in markdown
    assert "Bounded Review Steps" in markdown
    assert any(event.action == "policy_replay.pack_exported" for event in state.audit.events)


def test_policy_replay_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = policy_replay_state(tmp_path)
    main_module.state = state
    client = TestClient(app)

    report = client.get("/policy/replay-drift", headers=HEADERS)
    export = client.post(
        "/policy/replay-pack",
        json={"actor": "pytest-policy-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["baseline_scenario_count"] >= 3
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Policy Replay" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/policy/replay-drift" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/policy_replay/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/policy_replay" for item in inventory.items)
    assert any(item["path"] == "/policy/replay-drift" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /policy/replay-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
