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
    assert {check["name"] for check in body["checks"]} >= {
        "Manifest coverage",
        "MCP discovery",
        "Resources and prompts",
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
