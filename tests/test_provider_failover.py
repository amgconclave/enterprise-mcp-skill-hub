from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    ProviderFailoverDrillRequest,
    ProviderFailoverPackRequest,
    ProviderFailoverScenario,
)

HEADERS = {"X-API-Key": "dev-local-token"}


def test_provider_failover_drill_simulates_mock_fallback_without_network() -> None:
    state = create_state()

    result = state.provider_failover.drill(
        ProviderFailoverDrillRequest(
            actor="pytest-provider-drill",
            scenarios=[
                ProviderFailoverScenario(
                    skill_id="summarize_document",
                    requested_provider="openai",
                    failure_mode="missing_credentials",
                    actor="pytest-provider-drill",
                ),
                ProviderFailoverScenario(
                    skill_id="search_knowledge_base",
                    requested_provider="azure_openai",
                    failure_mode="rate_limited",
                    actor="pytest-provider-drill",
                ),
            ],
        )
    )

    assert result.drill_id == "provider_failover_drill_latest"
    assert result.readiness_status in {"ready", "needs_review"}
    assert result.summary["network_calls_performed"] == 0
    assert result.summary["fallback_decision_count"] == 2
    assert result.summary["estimated_cost_delta"] == 0.0
    assert {"provider flexibility", "governance", "agent cost tracking"} <= set(
        result.architecture_patterns
    )
    assert all(decision.selected_provider == "mock" for decision in result.decisions)
    assert all(decision.reviewer_required for decision in result.decisions)
    assert all(decision.replay_command for decision in result.decisions)
    assert any(event.action == "provider_failover.drill_run" for event in state.audit.events)


def test_provider_failover_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.provider_failover.output_dir = tmp_path / "provider_failover"

    export = state.provider_failover.pack(ProviderFailoverPackRequest(actor="pytest-provider-drill"))

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "provider_failover_drill_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert "provider_failover_drill" in bundle
    assert "reviewer_checklist" in bundle
    assert "Provider Failover Drill Pack" in markdown_path.read_text(encoding="utf-8")
    assert any(event.action == "provider_failover.pack_exported" for event in state.audit.events)


def test_provider_failover_endpoints_dashboard_artifacts_contract_and_demo(tmp_path: Path) -> None:
    state = create_state()
    state.provider_failover.output_dir = tmp_path / "provider_failover"
    main_module.state = state
    client = TestClient(app)

    drill_response = client.post(
        "/providers/failover-drill",
        json={"actor": "pytest-provider-drill"},
        headers=HEADERS,
    )
    pack_response = client.post(
        "/providers/failover-pack",
        json={"actor": "pytest-provider-drill"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert drill_response.status_code == 200
    assert drill_response.json()["summary"]["network_calls_performed"] == 0
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Provider Failover" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/providers/failover-drill" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/provider_failover/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/provider_failover" for item in inventory.items)
    assert any(item["path"] == "/providers/failover-drill" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /providers/failover-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
