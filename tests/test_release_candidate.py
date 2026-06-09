from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import ReleasePublishPackRequest
from app.services import ReleaseCandidateService

HEADERS = {"X-API-Key": "dev-local-token"}


def release_candidate_state(tmp_path: Path):
    state = create_state()
    state.release_candidate = ReleaseCandidateService(state, output_dir=tmp_path / "release_packs")
    return state


def test_release_quality_gate_returns_structured_publish_readiness(tmp_path: Path) -> None:
    state = release_candidate_state(tmp_path)

    gate = asyncio.run(state.release_candidate.quality_gate())

    assert gate.gate_id == "release_candidate_quality_gate_latest"
    assert gate.status in {"ready", "needs_review", "blocked"}
    assert 0 <= gate.score <= 100
    assert {"ci", "docs", "tests", "eval", "demo", "mcp", "release"} <= set(gate.coverage)
    assert gate.publish_readiness["status"] == gate.status
    assert gate.summary["local_only"] is True
    assert any(item["path"] == "/release/quality-gate" for item in gate.endpoint_inventory)
    assert any(item["path"] == "/release/publish-pack" for item in gate.endpoint_inventory)
    assert gate.mcp_capability_inventory["tool_count"] == 6
    assert any("python -m pytest -q" == item["command"] for item in gate.verification_checklist)
    assert any("release_packs" in item["json_path"] for item in gate.artifact_coverage)


def test_release_publish_pack_writes_json_and_markdown(tmp_path: Path) -> None:
    state = release_candidate_state(tmp_path)

    export = asyncio.run(
        state.release_candidate.publish_pack(
            ReleasePublishPackRequest(actor="pytest-release-publisher")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["pack_id"] == "publish_pack_latest"
    assert "quality_gate" in bundle
    assert "setup_commands" in bundle
    assert "demo_commands" in bundle
    assert "expected_outputs" in bundle
    assert "endpoint_inventory" in bundle
    assert "mcp_capability_inventory" in bundle
    assert "artifact_inventory" in bundle
    assert "screenshots_manual_verification" in bundle
    assert "github_repo_checklist" in bundle
    assert "commit_push_readiness_notes" in bundle
    assert "recruiter_review_notes" in bundle
    assert "known_limitations" in bundle
    assert any(command == "python -m app.demo" for command in bundle["verification_commands"])
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Release Candidate Publish Pack" in markdown
    assert "Verification Commands" in markdown
    assert "GitHub Repo Checklist" in markdown
    assert "Known Limitations" in markdown


def test_release_candidate_endpoints_return_gate_and_pack(tmp_path: Path) -> None:
    main_module.state = release_candidate_state(tmp_path)
    client = TestClient(app)

    gate = client.get("/release/quality-gate", headers=HEADERS)
    export = client.post("/release/publish-pack", headers=HEADERS)

    assert gate.status_code == 200
    assert gate.json()["gate_id"] == "release_candidate_quality_gate_latest"
    assert gate.json()["mcp_capability_inventory"]["tool_count"] == 6
    assert export.status_code == 200
    assert export.json()["pack_id"] == "publish_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
