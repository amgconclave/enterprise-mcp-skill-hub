from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import SkillLineagePackRequest
from app.services import SkillLineageService

HEADERS = {"X-API-Key": "dev-local-token"}


def lineage_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.lineage = SkillLineageService(state, output_dir=tmp_path / "lineage")
    return state


def test_skill_lineage_report_maps_skills_to_governed_evidence() -> None:
    state = lineage_state()

    report = state.lineage.report()

    assert report.report_id == "skill_lineage_report_latest"
    assert report.readiness_status == "ready"
    assert report.summary["skill_count"] == 6
    assert report.summary["mcp_exposed_skill_count"] == 6
    assert report.summary["needs_review_count"] == 0
    assert report.summary["graph_edge_count"] > report.summary["skill_count"]
    assert all(record.manifest_hash for record in report.records)
    assert all(record.input_schema_hash and record.output_schema_hash for record in report.records)
    assert all(record.policy_controls for record in report.records)
    assert any(record.skill_id == "search_knowledge_base" and record.resource_uris for record in report.records)
    assert any("shared state" in pattern for pattern in report.governance_patterns)


def test_skill_lineage_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = lineage_state(tmp_path)

    export = state.lineage.pack(SkillLineagePackRequest(actor="pytest-lineage-reviewer"))

    assert export.pack_id == "skill_lineage_pack_latest"
    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert bundle["skill_lineage_report"]["summary"]["skill_count"] == 6
    assert "reviewer_checklist" in bundle
    assert "Skill Lineage Pack" in markdown
    assert "Governance Patterns" in markdown
    assert any(event.action == "lineage.pack_exported" for event in state.audit.events)


def test_skill_lineage_endpoints_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = lineage_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/lineage/report", headers=HEADERS)
    export = client.post(
        "/lineage/pack",
        json={"actor": "pytest-lineage-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["mcp_exposed_skill_count"] == 6
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Skill Lineage" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/lineage/report" for endpoint in smoke.endpoint_references)
    assert any(endpoint["path"] == "/lineage/pack" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/lineage/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/lineage" for item in inventory.items)
    assert any(item["path"] == "/lineage/report" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /lineage/pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
