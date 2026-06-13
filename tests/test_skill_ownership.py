from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import SkillOwnershipPackRequest

HEADERS = {"X-API-Key": "dev-local-token"}


def ownership_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.ownership.output_dir = tmp_path / "ownership_packs"
        state.artifacts.output_dir = tmp_path / "artifact_indexes"
    return state


def test_skill_ownership_matrix_maps_manifest_owners_and_escalation_routes() -> None:
    state = ownership_state()

    matrix = state.ownership.matrix(actor="pytest-ownership-reviewer")
    by_skill = {record.skill_id: record for record in matrix.records}

    assert matrix.matrix_id == "skill_ownership_matrix_latest"
    assert matrix.readiness_status in {"ready", "needs_review"}
    assert matrix.summary["skill_count"] >= 6
    assert matrix.summary["owner_count"] >= 6
    assert matrix.summary["coverage_gap_count"] == 0
    assert by_skill["search_knowledge_base"].owner == "knowledge-retrieval-owner"
    assert by_skill["search_knowledge_base"].risk_tier == "high"
    assert by_skill["search_knowledge_base"].support_tier == "tier_1"
    assert by_skill["classify_request"].escalation_channel == "#mcp-routing-skills"
    assert any(route["owner_team"] == "Knowledge Platform" for route in matrix.escalation_routes)
    assert {"governance", "human-in-the-loop", "handoffs", "tool governance"} <= set(
        matrix.architecture_patterns
    )


def test_skill_ownership_pack_writes_reviewer_artifacts(tmp_path: Path) -> None:
    state = ownership_state(tmp_path)

    export = state.ownership.pack(
        SkillOwnershipPackRequest(actor="pytest-ownership-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "skill_ownership_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "ownership_matrix" in bundle
    assert "owner_roster" in bundle
    assert "escalation_routes" in bundle
    assert "handoff_plan" in bundle
    assert "Skill Ownership And Escalation Pack" in markdown
    assert any(event.action == "ownership.pack_exported" for event in state.audit.events)


def test_ownership_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = ownership_state(tmp_path)
    main_module.state = state
    client = TestClient(app)

    matrix = client.get("/ownership/matrix", headers=HEADERS)
    export = client.post(
        "/ownership/pack",
        json={"actor": "pytest-ownership-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert matrix.status_code == 200
    assert matrix.json()["summary"]["owner_count"] >= 6
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Skill Ownership" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/ownership/matrix" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/ownership_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/ownership_packs" for item in inventory.items)
    assert any(item["path"] == "/ownership/matrix" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /ownership/pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
