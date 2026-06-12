from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import EvalRegressionPackRequest
from app.services import EvalRegressionGateService

HEADERS = {"X-API-Key": "dev-local-token"}


def regression_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.eval_regression = EvalRegressionGateService(
            state,
            output_dir=tmp_path / "eval_regression",
        )
        state.artifacts.output_dir = tmp_path / "artifact_indexes"
    return state


def test_eval_regression_gate_composes_local_quality_signals() -> None:
    state = regression_state()

    gate = asyncio.run(state.eval_regression.gate())

    assert gate.gate_id == "eval_regression_gate_latest"
    assert gate.golden_eval.total_cases >= 4
    assert gate.golden_eval.failed_cases == 0
    assert gate.conformance_status == "pass"
    assert len(gate.state_observations) >= 5
    assert {"state observation", "bounded action loop", "step verification"}.issubset(
        set(gate.architecture_patterns)
    )
    assert any(step["name"] == "export_reviewer_pack" for step in gate.bounded_remediation_steps)
    assert any("/evals/regression-pack" in command for command in gate.local_proof_commands)


def test_eval_regression_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = regression_state(tmp_path)

    export = asyncio.run(
        state.eval_regression.pack(EvalRegressionPackRequest(actor="pytest-eval-reviewer"))
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "eval_regression_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "eval_regression_gate" in bundle
    assert "reviewer_checklist" in bundle
    assert "Eval Regression Gate Pack" in markdown
    assert "Bounded Remediation Steps" in markdown
    assert any(event.action == "eval.regression_pack_exported" for event in state.audit.events)


def test_eval_regression_endpoints_dashboard_inventory_and_contract(tmp_path: Path) -> None:
    state = regression_state(tmp_path)
    main_module.state = state
    client = TestClient(app)

    gate = client.get("/evals/regression-gate", headers=HEADERS)
    export = client.post(
        "/evals/regression-pack",
        json={"actor": "pytest-eval-reviewer"},
        headers=HEADERS,
    )
    dashboard_smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()
    smoke_matrix = asyncio.run(state.smoke.smoke_matrix())

    assert gate.status_code == 200
    assert gate.json()["gate_id"] == "eval_regression_gate_latest"
    assert export.status_code == 200
    assert export.json()["pack_id"] == "eval_regression_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Eval Regression Gate" for view in dashboard_smoke.expected_views)
    assert any(
        endpoint["path"] == "/evals/regression-gate"
        for endpoint in dashboard_smoke.endpoint_references
    )
    assert any(tab["artifact_dir"] == "data/eval_regression/" for tab in dashboard_smoke.generated_artifact_tabs)
    assert any(item.directory == "data/eval_regression" for item in inventory.items)
    assert any(item["path"] == "/evals/regression-gate" for item in api_contract.docs_api_coverage)
    assert any(endpoint.path == "/evals/regression-pack" for endpoint in smoke_matrix.endpoint_matrix)
