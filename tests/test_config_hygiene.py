from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import ConfigHygienePackRequest
from app.services import ConfigHygieneService

HEADERS = {"X-API-Key": "dev-local-token"}


def config_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.config_hygiene = ConfigHygieneService(state, output_dir=tmp_path / "config_hygiene")
    return state


def test_config_hygiene_report_redacts_secret_values_and_keeps_mock_provider_ready() -> None:
    state = config_state()

    report = state.config_hygiene.report()
    by_variable = {variable.name: variable for variable in report.variables}

    assert report.summary["secret_value_exported"] is False
    assert report.provider_gate["provider"] == "mock"
    assert report.provider_gate["status"] == "ready"
    assert by_variable["API_KEY"].exported_value in {
        "default-local-demo-token",
        "[PRESENT_REDACTED]",
    }
    assert by_variable["OPENAI_API_KEY"].required_for == "optional_openai_provider"
    assert "data/config_hygiene/" in {check["marker"] for check in report.gitignore_checks}
    assert any("python -m pytest -q" in command for command in report.local_proof_commands)


def test_config_hygiene_pack_exports_redacted_reviewer_artifacts(tmp_path: Path) -> None:
    state = config_state(tmp_path)

    export = state.config_hygiene.pack(
        ConfigHygienePackRequest(actor="pytest-config-reviewer")
    )

    assert export.pack_id == "config_hygiene_pack_latest"
    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert bundle["config_hygiene_report"]["summary"]["secret_value_exported"] is False
    assert "governance_patterns" in bundle
    assert "Config Hygiene + Secret Rotation Pack" in markdown
    assert "[PRESENT_REDACTED]" in markdown or "default-local-demo-token" in markdown
    assert any(event.action == "config_hygiene.pack_exported" for event in state.audit.events)


def test_config_hygiene_endpoints_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = config_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/config/hygiene", headers=HEADERS)
    export = client.post(
        "/config/hygiene-pack",
        json={"actor": "pytest-config-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["secret_value_exported"] is False
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Config Hygiene" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/config/hygiene" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/config_hygiene/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/config_hygiene" for item in inventory.items)
    assert any(item["path"] == "/config/hygiene" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /config/hygiene-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
