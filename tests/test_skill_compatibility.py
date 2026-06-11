from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state, schema
from app.main import app
from app.models import SkillCompatibilityPackRequest, SkillManifest
from app.services import SkillVersionCompatibilityService

HEADERS = {"X-API-Key": "dev-local-token"}


def compatibility_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.compatibility = SkillVersionCompatibilityService(
            state,
            output_dir=tmp_path / "compatibility_packs",
        )
    return state


def test_compatibility_report_checks_semver_and_mcp_exposure() -> None:
    state = compatibility_state()

    report = state.compatibility.report()
    by_skill = {record.skill_id: record for record in report.records}

    assert report.readiness_status in {"ready", "needs_review"}
    assert report.coverage_summary["skill_count"] >= 6
    assert report.coverage_summary["semantic_version_valid_count"] == report.coverage_summary["skill_count"]
    assert by_skill["summarize_document"].semantic_version_valid is True
    assert by_skill["summarize_document"].version_delta == "initial"
    assert by_skill["summarize_document"].mcp_exposure_state["mcp_exposed"] is True
    assert by_skill["summarize_document"].migration_recommendations


def test_compatibility_report_flags_major_version_and_deprecated_skill() -> None:
    state = compatibility_state()
    original = state.registry.get("classify_request")
    state.registry.register(
        original.model_copy(
            update={
                "version": "2.0.0",
                "description": f"{original.description} Deprecated compatibility route.",
                "tags": [*original.tags, "deprecated"],
            }
        ),
        actor="pytest-compatibility",
    )
    state.registry.register(
        SkillManifest(
            id="bad_version_skill",
            name="Bad Version Skill",
            version="v1",
            description="Invalid SemVer candidate.",
            status="validated",
            input_schema=schema({"text": {"type": "string"}}, ["text"]),
            output_schema=schema({"result": {"type": "string"}}, ["result"]),
        ),
        actor="pytest-compatibility",
    )

    report = state.compatibility.report()
    by_skill = {record.skill_id: record for record in report.records}

    assert by_skill["classify_request"].version_delta == "major"
    assert by_skill["classify_request"].deprecated is True
    assert by_skill["classify_request"].compatibility_status == "deprecated"
    assert by_skill["classify_request"].migration_recommendations
    assert by_skill["bad_version_skill"].semantic_version_valid is False
    assert by_skill["bad_version_skill"].compatibility_status == "incompatible"
    assert any(item["skill_id"] == "classify_request" for item in report.deprecated_skill_warnings)
    assert report.readiness_status == "blocked"


def test_compatibility_pack_writes_reviewer_artifacts(tmp_path: Path) -> None:
    state = compatibility_state(tmp_path)

    export = state.compatibility.pack(
        SkillCompatibilityPackRequest(actor="pytest-compatibility-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "compatibility_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "compatibility_report" in bundle
    assert "semantic_version_policy" in bundle
    assert "reviewer_checklist" in bundle
    assert "local_proof_commands" in bundle
    assert "Skill Version Compatibility Pack" in markdown
    assert "Migration Recommendations" in markdown


def test_compatibility_endpoints_return_report_record_and_pack(tmp_path: Path) -> None:
    main_module.state = compatibility_state(tmp_path)
    client = TestClient(app)

    report = client.get("/skills/compatibility", headers=HEADERS)
    record = client.get("/skills/summarize_document/compatibility", headers=HEADERS)
    export = client.post(
        "/skills/compatibility-pack",
        json={"actor": "pytest-compatibility-reviewer"},
        headers=HEADERS,
    )

    assert report.status_code == 200
    assert report.json()["coverage_summary"]["skill_count"] >= 6
    assert record.status_code == 200
    assert record.json()["skill_id"] == "summarize_document"
    assert export.status_code == 200
    assert export.json()["pack_id"] == "compatibility_pack_latest"
    assert Path(export.json()["json_path"]).exists()


def test_dashboard_smoke_artifact_inventory_and_api_contract_wire_compatibility(
    tmp_path: Path,
) -> None:
    state = compatibility_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"

    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert any(view["label"] == "Skill Compatibility" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/skills/compatibility" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/compatibility_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/compatibility_packs" for item in inventory.items)
    assert any(
        item["path"] == "/skills/compatibility-pack"
        for item in api_contract.docs_api_coverage
    )
    assert any(
        item["producer_endpoint"] == "POST /skills/compatibility-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
