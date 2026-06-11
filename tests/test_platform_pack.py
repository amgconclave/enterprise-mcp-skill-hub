from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import GovernedSkillPlatformPackRequest

HEADERS = {"X-API-Key": "dev-local-token"}


async def test_platform_pack_aggregates_governed_runtime_controls() -> None:
    state = create_state()

    report = await state.platform_pack.report(actor="pytest-platform-owner")

    assert report.pack_id == "governed_skill_platform_pack_latest"
    assert report.readiness_status in {"ready", "needs_review"}
    assert {"durable workflows", "human-in-the-loop", "governance", "provider flexibility"} <= set(
        report.architecture_patterns
    )
    control_ids = {control["id"] for control in report.capability_controls}
    assert {"tool_registry", "durable_workflows", "human_in_the_loop", "provider_flexibility"} <= control_ids
    assert report.workflow_durability["template_source"].endswith("workflow_templates.json")
    assert report.human_review_queue["approval_endpoint"] == "POST /workflows/{template_id}/approve"
    assert report.provider_flexibility["network_calls_performed"] == 0
    assert len(report.tool_governance["mcp_tool_names"]) >= 6
    assert "estimated_cost" in report.cost_and_trace_governance
    assert report.handoff_readiness["evidence_artifacts"]


async def test_platform_pack_export_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.platform_pack.output_dir = tmp_path / "platform_packs"

    export = await state.platform_pack.export(
        GovernedSkillPlatformPackRequest(actor="pytest-platform-owner")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "governed_skill_platform_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "platform_pack" in bundle
    assert "capability_controls" in bundle
    assert "Governed Skill Platform Pack" in markdown
    assert any(event.action == "platform.pack_exported" for event in state.audit.events)


def test_platform_pack_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.platform_pack.output_dir = tmp_path / "platform_packs"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/platform/pack", headers=HEADERS)
    export = client.post(
        "/platform/pack/export",
        json={"actor": "pytest-platform-owner"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["mcp_tool_count"] >= 6
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Platform Pack" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/platform/pack" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/platform_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/platform_packs" for item in inventory.items)
    assert any(item["path"] == "/platform/pack" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /platform/pack/export"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
