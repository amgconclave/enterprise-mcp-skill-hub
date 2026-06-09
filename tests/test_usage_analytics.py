from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import UsageChargebackPackRequest
from app.services import SkillUsageAnalyticsService

HEADERS = {"X-API-Key": "dev-local-token"}


def usage_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.usage = SkillUsageAnalyticsService(state, output_dir=tmp_path / "usage_packs")
    return state


def test_usage_analytics_covers_skills_tenants_budgets_and_anomalies() -> None:
    state = usage_state()

    analytics = state.usage.analytics()

    assert analytics.coverage_summary["all_built_in_skills_covered"]
    assert analytics.coverage_summary["tenant_environment_count"] >= 4
    assert analytics.coverage_summary["has_high_latency_anomaly"]
    assert analytics.coverage_summary["has_budget_warning"]
    assert analytics.coverage_summary["has_disabled_skill_blocked_event"]
    assert analytics.summary["estimated_cost"] > 0
    assert "blocked" in analytics.usage_by_status
    assert "not_exposed" in analytics.usage_by_mcp_exposure
    assert any(row["skill_id"] == "search_knowledge_base" for row in analytics.usage_by_skill)
    assert any(row["tenant"] == "fintech" and row["status"] == "warning" for row in analytics.budget_status)
    assert any(item["type"] == "high_latency" for item in analytics.anomalies)
    assert any(item["type"] == "budget_warning" for item in analytics.anomalies)


def test_usage_analytics_includes_existing_disabled_skill_history() -> None:
    state = usage_state()
    state.registry.set_status("translate_text", False, "pytest")

    invocation = asyncio.run(
        state.invocation_service.invoke(
            "translate_text",
            {"text": "hello", "target_language": "French"},
            "pytest-agent",
        )
    )
    analytics = state.usage.analytics()

    assert invocation.status == "failed"
    assert any(event["trace_id"] == invocation.trace_id for event in analytics.disabled_skill_blocked_events)
    assert analytics.summary["disabled_skill_blocked_event_count"] >= 2


def test_chargeback_pack_writes_markdown_json_and_cost_allocation(tmp_path: Path) -> None:
    state = usage_state(tmp_path)

    export = state.usage.chargeback_pack(
        UsageChargebackPackRequest(actor="pytest-finops-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "chargeback_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "usage_tables" in bundle
    assert "cost_allocation" in bundle
    assert "budget_anomaly_flags" in bundle
    assert "recommended_controls" in bundle
    assert "reviewer_checklist" in bundle
    assert "local_proof_commands" in bundle
    assert "Skill Usage Analytics + Cost Chargeback Pack" in markdown
    assert "Cost Allocation" in markdown
    assert "Local Proof Commands" in markdown


def test_usage_endpoints_return_analytics_and_chargeback_pack(tmp_path: Path) -> None:
    main_module.state = usage_state(tmp_path)
    client = TestClient(app)

    analytics = client.get("/usage/analytics", headers=HEADERS)
    export = client.post(
        "/usage/chargeback-pack",
        json={"actor": "pytest-finops-reviewer"},
        headers=HEADERS,
    )

    assert analytics.status_code == 200
    assert analytics.json()["coverage_summary"]["all_built_in_skills_covered"]
    assert analytics.json()["disabled_skill_blocked_events"]
    assert export.status_code == 200
    assert export.json()["pack_id"] == "chargeback_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()


def test_usage_wired_into_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = usage_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"

    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()
    matrix = asyncio.run(state.smoke.smoke_matrix())

    assert any(view["label"] == "Skill Usage Analytics" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/usage/analytics" for endpoint in smoke.endpoint_references)
    assert any(endpoint["path"] == "/usage/chargeback-pack" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/usage_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/usage_packs" for item in inventory.items)
    assert any(item["path"] == "/usage/chargeback-pack" for item in api_contract.docs_api_coverage)
    assert any(endpoint.path == "/usage/analytics" for endpoint in matrix.endpoint_matrix)
