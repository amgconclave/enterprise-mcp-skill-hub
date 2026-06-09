from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import LaunchChecklistRequest
from app.services import SmokeMatrixService

HEADERS = {"X-API-Key": "dev-local-token"}


def smoke_state(tmp_path: Path):
    state = create_state()
    state.smoke = SmokeMatrixService(state, output_dir=tmp_path / "launch_checklists")
    return state


def test_smoke_matrix_covers_interview_api_surfaces(tmp_path: Path) -> None:
    state = smoke_state(tmp_path)

    matrix = asyncio.run(state.smoke.smoke_matrix())

    areas = {endpoint.area for endpoint in matrix.endpoint_matrix}
    paths = {endpoint.path for endpoint in matrix.endpoint_matrix}
    assert {
        "auth/health",
        "skills",
        "mcp",
        "governance",
        "workflows",
        "releases",
        "capacity",
        "tenant policy",
        "incidents",
        "enterprise readiness",
        "ops",
    } <= areas
    assert "/ops/smoke-matrix" in paths
    assert "/ops/launch-checklist" in paths
    assert any(endpoint.expected_status == 401 for endpoint in matrix.endpoint_matrix)
    assert matrix.readiness_summary["mcp_tool_count"] == 6
    assert matrix.readiness_summary["local_only"] is True
    assert any("launch_checklists" in item["json_path"] for item in matrix.artifact_expectations)
    assert any("ops/smoke-matrix" in command for command in matrix.verification_commands)


def test_launch_checklist_writes_json_and_markdown(tmp_path: Path) -> None:
    state = smoke_state(tmp_path)

    export = asyncio.run(
        state.smoke.launch_checklist(
            LaunchChecklistRequest(actor="pytest-launch-reviewer")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["checklist_id"] == "launch_checklist_latest"
    assert "api_smoke_matrix" in bundle
    assert len(bundle["interviewer_talking_points"]) == 5
    assert any("python -m app.demo" in command for command in bundle["run_commands"])
    assert any("python -m app.evals.run_conformance" in command for command in bundle["eval_commands"])
    assert any(item["path"] == "/ops/launch-checklist" for item in bundle["api_smoke_matrix"]["endpoint_matrix"])
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Launch Checklist" in markdown
    assert "API Smoke Matrix" in markdown
    assert "Smoke readiness" in markdown
    assert "JD Skills Demonstrated" in markdown


def test_ops_endpoints_return_smoke_matrix_and_launch_checklist(tmp_path: Path) -> None:
    main_module.state = smoke_state(tmp_path)
    client = TestClient(app)

    smoke = client.get("/ops/smoke-matrix", headers=HEADERS)
    export = client.post("/ops/launch-checklist", headers=HEADERS)

    assert smoke.status_code == 200
    assert smoke.json()["endpoint_matrix"]
    assert smoke.json()["readiness_summary"]["sections_covered"]
    assert export.status_code == 200
    assert export.json()["checklist_id"] == "launch_checklist_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
