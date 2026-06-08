from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.services import PersistenceService


def test_governance_report_endpoint() -> None:
    main_module.state = create_state()
    client = TestClient(app)

    response = client.get("/governance/report", headers={"X-API-Key": "dev-local-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["skills_registered"] == 6
    assert body["enabled_tools"] == 6
    assert body["status"] == "pass"
    assert body["lifecycle_counts"]["promoted"] == 6
    assert len(body["skills"]) == 6
    assert {
        "skill_id",
        "version",
        "enabled",
        "status",
        "schema_valid",
        "last_invocation",
        "invocation_count",
        "failure_count",
        "provider",
        "tags",
        "risk_flags",
        "policy_access",
        "mcp_exposed",
        "mcp_exposure_status",
    }.issubset(body["skills"][0])
    assert {check["name"] for check in body["checks"]} >= {
        "Manifest coverage",
        "MCP discovery",
        "Schema validity",
        "Promotion lifecycle",
        "Resources and prompts",
        "Policy access control",
    }


def test_local_snapshot_persists_runtime_state(tmp_path: Path) -> None:
    state = create_state()
    state.persistence = PersistenceService(tmp_path / "snapshot.json")

    snapshot = state.persistence.save(state)
    loaded = state.persistence.load()

    assert snapshot.skills == 6
    assert loaded["exists"] is True
    assert len(loaded["snapshot"]["skills"]) == 6
    assert "governance_report" in loaded["snapshot"]


def test_governance_report_flags_draft_skill() -> None:
    state = create_state()
    draft_manifest = state.registry.get("classify_request").model_copy(update={"status": "draft"})
    state.registry.register(draft_manifest, actor="pytest")

    report = state.governance.generate()
    record = next(skill for skill in report.skills if skill.skill_id == "classify_request")

    assert report.status == "warn"
    assert record.schema_valid is True
    assert record.mcp_exposed is False
    assert record.mcp_exposure_status == "not_exposed"
    assert "not_promoted" in record.risk_flags
