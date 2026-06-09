from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state, schema
from app.main import app
from app.models import MarketplaceRolloutPackRequest, SkillManifest
from app.services import SkillMarketplaceGovernanceService

HEADERS = {"X-API-Key": "dev-local-token"}


def marketplace_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.marketplace = SkillMarketplaceGovernanceService(
            state,
            output_dir=tmp_path / "marketplace_packs",
        )
    return state


def test_catalog_returns_rollout_governance_for_all_tenant_scenarios() -> None:
    state = marketplace_state()

    catalog = asyncio.run(state.marketplace.catalog())

    scenario_ids = {scenario["id"] for scenario in catalog.tenant_scenarios}
    assert scenario_ids == {
        "internal_ops_local",
        "regulated_healthcare_prod",
        "fintech_confidential_prod",
        "public_sector_restricted_prod",
    }
    assert catalog.coverage_summary["listing_count"] >= 6
    assert catalog.coverage_summary["blocked_rollout_count"] >= 1
    assert catalog.coverage_summary["review_required_rollout_count"] >= 1
    assert any(listing.skill_id == "translate_text" for listing in catalog.listings)
    assert any(row["tenant"] == "fintech" for row in catalog.blocked_rollouts)
    assert any(row["tenant"] == "healthcare" for row in catalog.review_required_rollouts)


def test_catalog_includes_draft_disabled_usage_and_version_notes() -> None:
    state = marketplace_state()
    state.registry.set_status("translate_text", False, "pytest")
    state.registry.register(
        SkillManifest(
            id="draft_marketplace_skill",
            name="Draft Marketplace Skill",
            version="0.1.0",
            description="Draft skill that needs marketplace approval.",
            status="draft",
            input_schema=schema({"text": {"type": "string"}}, ["text"]),
            output_schema=schema({"result": {"type": "string"}}, ["result"]),
        ),
        actor="pytest",
    )
    asyncio.run(
        state.invocation_service.invoke(
            "classify_request",
            {"request": "Marketplace rollout approval needs a policy review."},
            "pytest",
        )
    )

    catalog = asyncio.run(state.marketplace.catalog())
    by_skill = {listing.skill_id: listing for listing in catalog.listings}

    assert by_skill["translate_text"].listing_status == "disabled"
    assert by_skill["translate_text"].required_review_state == "disabled_block"
    assert by_skill["translate_text"].mcp_exposure_state["mcp_exposed"] is False
    assert by_skill["draft_marketplace_skill"].listing_status == "draft"
    assert by_skill["draft_marketplace_skill"].required_review_state == "approval_required"
    assert by_skill["classify_request"].usage_signals["invocation_count"] == 1
    assert by_skill["classify_request"].version_comparison_notes
    assert catalog.disabled_skill_blocks


def test_disabled_skill_cannot_roll_out_or_invoke() -> None:
    state = marketplace_state()
    state.registry.set_status("translate_text", False, "pytest")

    catalog = asyncio.run(state.marketplace.catalog())
    invocation = asyncio.run(
        state.invocation_service.invoke(
            "translate_text",
            {"text": "hello", "target_language": "French"},
            "pytest",
        )
    )
    mcp_call = asyncio.run(
        state.mcp.call_tool(
            "translate_text",
            {"text": "hello", "target_language": "French"},
            "pytest",
        )
    )

    assert invocation.status == "failed"
    assert invocation.error == "Skill is disabled."
    assert mcp_call["status"] == "failed"
    assert any(row["skill_id"] == "translate_text" for row in catalog.disabled_skill_blocks)


def test_rollout_pack_writes_reviewer_artifacts(tmp_path: Path) -> None:
    state = marketplace_state(tmp_path)

    export = asyncio.run(
        state.marketplace.rollout_pack(
            MarketplaceRolloutPackRequest(actor="pytest-marketplace-reviewer")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "rollout_approval_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "rollout_recommendations" in bundle
    assert "tenant_policy_decisions" in bundle
    assert "disabled_skill_blocks" in bundle
    assert "version_comparison_notes" in bundle
    assert "local_proof_commands" in bundle
    assert "Skill Marketplace Tenant Rollout Approval Pack" in markdown
    assert "Local Proof Commands" in markdown


def test_marketplace_endpoints_return_catalog_and_pack(tmp_path: Path) -> None:
    main_module.state = marketplace_state(tmp_path)
    client = TestClient(app)

    catalog = client.get("/marketplace/catalog", headers=HEADERS)
    export = client.post(
        "/marketplace/rollout-pack",
        json={"actor": "pytest-marketplace-reviewer"},
        headers=HEADERS,
    )

    assert catalog.status_code == 200
    assert catalog.json()["coverage_summary"]["tenant_scenario_count"] == 4
    assert catalog.json()["blocked_rollouts"]
    assert catalog.json()["review_required_rollouts"]
    assert export.status_code == 200
    assert export.json()["pack_id"] == "rollout_approval_pack_latest"
    assert Path(export.json()["json_path"]).exists()


def test_dashboard_smoke_artifact_inventory_and_api_contract_wire_marketplace(tmp_path: Path) -> None:
    state = marketplace_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"

    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert any(view["label"] == "Skill Marketplace" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/marketplace/catalog" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/marketplace_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/marketplace_packs" for item in inventory.items)
    assert any(
        item["path"] == "/marketplace/rollout-pack"
        for item in api_contract.docs_api_coverage
    )
