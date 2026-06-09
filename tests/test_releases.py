from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import SkillManifest
from app.services import ReleaseService

HEADERS = {"X-API-Key": "dev-local-token"}


def release_service(state, tmp_path: Path) -> ReleaseService:
    return ReleaseService(
        state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )


def test_release_preview_diff_uses_generated_baseline(tmp_path: Path) -> None:
    state = create_state()
    state.releases = release_service(state, tmp_path)

    preview = asyncio.run(state.releases.preview("pytest-release-manager"))

    assert preview.snapshot_source == "generated_baseline"
    assert preview.readiness_status == "ready"
    assert {"generate_action_items", "translate_text"} <= {item.id for item in preview.skills_added}
    assert {"classify_request", "summarize_document"} <= {item.id for item in preview.skills_changed}
    assert "meeting_to_actions" in {item.id for item in preview.workflow_templates_added}
    assert "support_triage" in {item.id for item in preview.workflow_templates_changed}
    assert "resource://skill-catalog" in preview.mcp_capabilities.affected_resources
    assert "resource://workflow-templates" in preview.mcp_capabilities.affected_resources
    assert any("python -m pytest -q" in command for command in preview.recommended_regression_tests)


def test_release_export_writes_markdown_json_and_snapshot(tmp_path: Path) -> None:
    state = create_state()
    state.releases = release_service(state, tmp_path)

    export = asyncio.run(state.releases.export("pytest-release-manager"))

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    snapshot_path = Path(export.snapshot_path)
    assert json_path.exists()
    assert markdown_path.exists()
    assert snapshot_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["readiness_status"] == export.readiness_status
    assert len(bundle["interviewer_talking_points"]) == 5
    assert "jd_skills_demonstrated" in bundle
    assert "python -m app.mcp_server prompts" in bundle["local_verification_commands"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Governed Skill/Workflow Release Notes" in markdown
    assert "Release readiness" in markdown
    assert "Interviewer Talking Points" in markdown
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["snapshot_kind"] == "release_catalog"


def test_release_endpoints_return_preview_and_export(tmp_path: Path) -> None:
    main_module.state = create_state()
    main_module.state.releases = release_service(main_module.state, tmp_path)
    client = TestClient(app)

    preview = client.post("/releases/preview", headers=HEADERS)
    export = client.post("/releases/export", headers=HEADERS)

    assert preview.status_code == 200
    assert preview.json()["summary"]["promoted_skill_count"] == 6
    assert preview.json()["mcp_capabilities"]["tools"]
    assert export.status_code == 200
    assert Path(export.json()["markdown_path"]).exists()
    assert Path(export.json()["json_path"]).exists()


def test_disabled_and_draft_skills_are_excluded_from_release_readiness(tmp_path: Path) -> None:
    state = create_state()
    state.registry.set_status("translate_text", False, "pytest")
    draft = SkillManifest(
        id="draft_release_candidate",
        name="Draft Release Candidate",
        version="1.0.0",
        description="Draft skill that should not affect release readiness.",
        provider="mock",
        enabled=True,
        status="draft",
        tags=["release"],
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )
    state.registry.register(draft, "pytest")
    state.releases = release_service(state, tmp_path)

    preview = asyncio.run(state.releases.preview("pytest-release-manager"))

    assert preview.readiness_status == "ready"
    assert "translate_text" not in {item.current["id"] for item in preview.skills_added if item.current}
    assert "draft_release_candidate" not in {item.current["id"] for item in preview.skills_added if item.current}
    assert "translate_text" in {item["id"] for item in preview.excluded_skills["disabled"]}
    assert "draft_release_candidate" in {item["id"] for item in preview.excluded_skills["draft"]}
