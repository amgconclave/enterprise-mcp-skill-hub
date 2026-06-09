from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import ReviewerWalkthroughPackRequest
from app.services import ReviewerQuickstartService

HEADERS = {"X-API-Key": "dev-local-token"}


def reviewer_state(tmp_path: Path):
    state = create_state()
    state.reviewer = ReviewerQuickstartService(state, output_dir=tmp_path / "reviewer_packs")
    return state


def test_reviewer_quickstart_returns_copy_ready_walkthrough(tmp_path: Path) -> None:
    state = reviewer_state(tmp_path)

    quickstart = asyncio.run(state.reviewer.quickstart())

    assert quickstart.quickstart_id == "reviewer_quickstart_latest"
    assert quickstart.readiness_status in {"ready", "needs_review", "blocked"}
    assert any("requirements-dev.txt" in command for command in quickstart.setup_commands)
    assert quickstart.one_command_demo["command"] == "python -m app.demo"
    assert "python -m pytest -q" in quickstart.verification_commands
    assert any(step["path"] == "/reviewer/quickstart" for step in quickstart.endpoint_walkthrough)
    assert any(step["path"] == "/reviewer/walkthrough-pack" for step in quickstart.endpoint_walkthrough)
    assert any(step["command"] == "python -m app.mcp_server tools" for step in quickstart.mcp_command_walkthrough)
    assert any("reviewer_packs" in item["json_path"] for item in quickstart.artifact_proof_map)
    assert any("reviewer_quickstart_count" in item["expected"] for item in quickstart.expected_outputs)
    assert quickstart.summary["quickstart_item_count"] >= 10
    assert quickstart.summary["local_only"] is True


def test_reviewer_walkthrough_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = reviewer_state(tmp_path)

    export = asyncio.run(
        state.reviewer.walkthrough_pack(
            ReviewerWalkthroughPackRequest(actor="pytest-github-reviewer")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["pack_id"] == "walkthrough_pack_latest"
    assert "reviewer_quickstart" in bundle
    assert "recruiter_friendly_story" in bundle
    assert "engineer_deep_dive_path" in bundle
    assert "command_checklist" in bundle
    assert "api_mcp_proof_tour" in bundle
    assert "artifacts_to_inspect" in bundle
    assert "limitations" in bundle
    assert "github_readme_blurb" in bundle
    assert "proof tour" in bundle["github_readme_blurb"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Reviewer Walkthrough Pack" in markdown
    assert "API/MCP Proof Tour" in markdown
    assert "GitHub README Blurb" in markdown


def test_reviewer_endpoints_return_quickstart_and_pack(tmp_path: Path) -> None:
    main_module.state = reviewer_state(tmp_path)
    client = TestClient(app)

    quickstart = client.get("/reviewer/quickstart", headers=HEADERS)
    export = client.post("/reviewer/walkthrough-pack", headers=HEADERS)

    assert quickstart.status_code == 200
    assert quickstart.json()["quickstart_id"] == "reviewer_quickstart_latest"
    assert quickstart.json()["summary"]["quickstart_item_count"] >= 10
    assert export.status_code == 200
    assert export.json()["pack_id"] == "walkthrough_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
