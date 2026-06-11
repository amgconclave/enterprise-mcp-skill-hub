from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import AgentSocietyEvalRequest
from app.services import AgentSocietyEvaluationService

HEADERS = {"X-API-Key": "dev-local-token"}


def society_eval_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.agent_society_eval = AgentSocietyEvaluationService(
            state,
            output_dir=tmp_path / "agent_society_evals",
        )
    return state


async def test_agent_society_eval_scores_roles_memory_tools_and_policy_gate() -> None:
    state = society_eval_state()

    report = await state.agent_society_eval.report(
        AgentSocietyEvalRequest(actor="pytest-agent-society")
    )

    assert report.readiness_status == "ready"
    assert report.summary["score"] == 100.0
    assert report.summary["evaluated_run_count"] == 2
    assert report.summary["observed_role_count"] == 5
    assert report.summary["memory_entry_count"] >= 4
    assert report.summary["policy_denial_count"] == 1
    assert {"role-playing agents", "memory", "agent society evaluation"} <= set(
        report.architecture_patterns
    )
    assert all(row["status"] == "pass" for row in report.role_scorecard)
    assert all(row["status"] == "pass" for row in report.memory_checks)
    assert all(row["status"] == "pass" for row in report.policy_gate_checks)
    assert any(event.action == "agents.society_eval_run" for event in state.audit.events)


async def test_agent_society_eval_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = society_eval_state(tmp_path)

    export = await state.agent_society_eval.pack(
        AgentSocietyEvalRequest(actor="pytest-agent-society")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "agent_society_eval_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "agent_society_eval" in bundle
    assert "role-playing agents" in bundle["architecture_patterns"]
    assert "Agent Society Evaluation Pack" in markdown
    assert "Policy Gate Checks" in markdown
    assert any(event.action == "agents.society_eval_pack_exported" for event in state.audit.events)


def test_agent_society_eval_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    original_state = main_module.state
    state = society_eval_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    try:
        report_response = client.get("/agents/society-eval", headers=HEADERS)
        pack_response = client.post(
            "/agents/society-eval-pack",
            headers=HEADERS,
            json={"actor": "pytest-agent-society"},
        )
        smoke = state.ui_verification.dashboard_smoke()
        inventory = state.artifacts.inventory()
        api_contract = state.api_contracts.contract_audit()
    finally:
        main_module.state = original_state

    assert report_response.status_code == 200
    assert report_response.json()["summary"]["score"] == 100.0
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Agent Society Evaluation" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/agents/society-eval" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/agent_society_evals/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/agent_society_evals" for item in inventory.items)
    assert any(item["path"] == "/agents/society-eval-pack" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /agents/society-eval-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
