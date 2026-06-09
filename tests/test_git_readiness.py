from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.git_readiness import GitReadinessService
from app.main import app
from app.models import GitPushPlanRequest

HEADERS = {"X-API-Key": "dev-local-token"}


def git_state(tmp_path: Path):
    state = create_state()
    state.git_readiness = GitReadinessService(output_dir=tmp_path / "git_packs")
    return state


def test_git_readiness_returns_local_branch_hygiene_status(tmp_path: Path) -> None:
    state = git_state(tmp_path)

    readiness = state.git_readiness.readiness()

    assert readiness.readiness_id == "git_readiness_latest"
    assert readiness.git_repository["detected"] is True
    assert "current_branch" in readiness.git_repository
    assert readiness.summary["git_repo_detected"] is True
    assert "tracked_changed_count" in readiness.worktree_summary
    assert any(row["directory"] == "data/git_packs/" for row in readiness.generated_artifact_directories)
    assert any(row["directory"] == "data/git_packs/" and row["ignored"] for row in readiness.generated_artifact_directories)
    assert any(check["id"] == "github_actions_workflow_presence" for check in readiness.required_publish_checks)
    assert any(check["id"] == "readme_final_handoff_mention" for check in readiness.required_publish_checks)
    assert any(command == "git status --porcelain=v1 --ignored" for command in readiness.non_destructive_review_commands)
    assert any("python -m app.mcp_server tools" in note for note in readiness.mcp_publish_notes)
    assert "source_files_changed" in readiness.changed_file_groups


def test_git_push_plan_writes_markdown_and_json(tmp_path: Path) -> None:
    state = git_state(tmp_path)

    export = state.git_readiness.push_plan(GitPushPlanRequest(actor="pytest-github-reviewer"))

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "git_push_plan_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "git_readiness" in bundle
    assert "exact_non_destructive_review_commands" in bundle
    assert "suggested_commit_grouping" in bundle
    assert "pre_push_verification_checklist" in bundle
    assert "mcp_command_verification" in bundle
    assert "recruiter_github_readme_publish_blurb" in bundle
    assert "GitHub Push Readiness + Branch Hygiene Pack" in markdown
    assert "Exact Non-Destructive Review Commands" in markdown
    assert "Recruiter/GitHub README Publish Blurb" in markdown


def test_git_readiness_endpoints_return_status_and_pack(tmp_path: Path) -> None:
    main_module.state = git_state(tmp_path)
    client = TestClient(app)

    readiness = client.get("/git/readiness", headers=HEADERS)
    export = client.post(
        "/git/push-plan",
        json={"actor": "pytest-github-reviewer"},
        headers=HEADERS,
    )

    assert readiness.status_code == 200
    assert readiness.json()["readiness_id"] == "git_readiness_latest"
    assert readiness.json()["git_repository"]["detected"] is True
    assert export.status_code == 200
    assert export.json()["pack_id"] == "git_push_plan_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
