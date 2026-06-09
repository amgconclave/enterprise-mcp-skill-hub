from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import ProviderFallbackPackRequest
from app.services import ProviderReadinessService

HEADERS = {"X-API-Key": "dev-local-token"}


def provider_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.provider_readiness = ProviderReadinessService(
            state,
            output_dir=tmp_path / "provider_packs",
        )
    return state


def test_provider_readiness_keeps_mock_default_and_static_external_checks() -> None:
    state = provider_state()

    report = state.provider_readiness.readiness(actor="pytest-provider-reviewer")
    checks_by_provider = {check["provider"]: check for check in report.provider_checks}

    assert report.current_provider["name"] == "mock"
    assert report.current_provider["network_call_required_for_report"] is False
    assert report.summary["network_calls_performed"] == 0
    assert report.readiness_status in {"ready", "needs_review"}
    assert checks_by_provider["mock"]["status"] == "pass"
    assert {"mock", "openai", "azure_openai"} <= set(checks_by_provider)
    assert all(check["credential_presence"] in {"not_required", "present", "absent"} for check in report.provider_checks)
    assert any(row["provider"] == "openai" for row in report.fallback_matrix)
    assert any(event.action == "provider_readiness.report_run" for event in state.audit.events)


def test_provider_fallback_pack_exports_audit_backed_artifacts(tmp_path: Path) -> None:
    state = provider_state(tmp_path)

    export = state.provider_readiness.fallback_pack(
        ProviderFallbackPackRequest(actor="pytest-provider-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "provider_fallback_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "provider_readiness" in bundle
    assert "fallback_policy" in bundle
    assert bundle["summary"]["audit_event_count"] >= 1
    assert "Provider Readiness + Fallback Pack" in markdown
    assert "Fallback Matrix" in markdown


def test_provider_endpoints_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = provider_state(tmp_path)
    main_module.state = state
    client = TestClient(app)

    readiness = client.get("/providers/readiness", headers=HEADERS)
    export = client.post(
        "/providers/fallback-pack",
        json={"actor": "pytest-provider-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert readiness.status_code == 200
    assert readiness.json()["current_provider"]["name"] == "mock"
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Provider Readiness" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/providers/readiness" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/provider_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/provider_packs" for item in inventory.items)
    assert any(item["path"] == "/providers/readiness" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /providers/fallback-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
