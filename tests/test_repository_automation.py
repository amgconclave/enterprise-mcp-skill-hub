from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.git_readiness import GitReadinessService
from app.main import app
from app.models import (
    GitReadinessResult,
    RepositoryAutomationPackRequest,
    RepositoryAutomationPlanRequest,
)
from app.utils import utc_now

HEADERS = {"X-API-Key": "dev-local-token"}


def synthetic_dirty_readiness() -> GitReadinessResult:
    return GitReadinessResult(
        readiness_id="git_readiness_latest",
        generated_at=utc_now(),
        readiness_status="needs_review",
        score=88,
        summary={"local_only": True},
        git_repository={
            "detected": True,
            "repo_root": "C:/repo",
            "current_branch": "main",
            "detached_head": False,
            "inspection_errors": [],
        },
        worktree_summary={
            "dirty": True,
            "changed_path_count": 2,
            "tracked_changed_count": 2,
            "untracked_count": 0,
            "modified_count": 2,
            "deleted_count": 0,
            "renamed_count": 0,
            "added_count": 0,
            "ignored_count": 0,
            "tracked_changed_paths": ["app/main.py", "tests/test_repository_automation.py"],
            "untracked_paths": [],
            "ignored_paths_sample": [],
            "status_entries": [],
        },
        generated_artifact_directories=[],
        changed_file_groups={"source_files_changed": ["app/main.py"]},
        suspicious_files=[],
        required_publish_checks=[],
        dirty_worktree_guidance=[],
        recommended_commit_groups=[
            {
                "id": "repo_automation_api_service",
                "title": "Repository automation API/service/models",
                "paths": ["app/main.py", "app/git_readiness.py"],
                "review_note": "Review repository automation changes together.",
            }
        ],
        mcp_publish_notes=[],
        non_destructive_review_commands=[],
        limitations=[],
    )


def test_repository_automation_plan_blocks_mutation_and_keeps_commands_dry_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = GitReadinessService(automation_output_dir=tmp_path / "repository_automation")
    monkeypatch.setattr(service, "readiness", synthetic_dirty_readiness)

    plan = service.automation_plan(
        RepositoryAutomationPlanRequest(actor="pytest-repo-reviewer")
    )

    assert plan.plan_id == "repo_automation_plan_latest"
    assert plan.readiness_status == "needs_review"
    assert plan.summary["dry_run_only"] is True
    assert plan.summary["blocked_mutation_count"] == 1
    assert plan.sandbox_policy["dry_run_planning_allowed"] is True
    assert "repo_mutation" in plan.sandbox_policy["blocked_action_classes"]
    assert len(plan.automation_tasks) == 1
    task = plan.automation_tasks[0]
    assert task.action_class == "repo_mutation"
    assert task.sandbox_decision == "deny"
    assert task.dry_run_only is True
    assert all(not command.startswith("git add") for command in task.planned_commands)
    assert [event["stage"] for event in task.timeline] == [
        "queued",
        "sandbox_preflight",
        "manual_review",
    ]


def test_repository_automation_pack_writes_markdown_and_json(monkeypatch, tmp_path: Path) -> None:
    service = GitReadinessService(automation_output_dir=tmp_path / "repository_automation")
    monkeypatch.setattr(service, "readiness", synthetic_dirty_readiness)

    export = service.automation_pack(
        RepositoryAutomationPackRequest(actor="pytest-repo-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "repo_automation_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "repository_automation_plan" in bundle
    assert "repository automation" in bundle["architecture_patterns"]
    assert "Repository Automation Dry-Run Pack" in markdown
    assert "Blocked mutations" in markdown


def test_repository_automation_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.git_readiness.automation_output_dir = tmp_path / "repository_automation"
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    plan_response = client.get("/repository/automation-plan", headers=HEADERS)
    pack_response = client.post(
        "/repository/automation-pack",
        json={"actor": "pytest-repo-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert plan_response.status_code == 200
    assert plan_response.json()["plan_id"] == "repo_automation_plan_latest"
    assert plan_response.json()["summary"]["dry_run_only"] is True
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Repository Automation" for view in smoke.expected_views)
    assert any(
        endpoint["path"] == "/repository/automation-plan"
        for endpoint in smoke.endpoint_references
    )
    assert any(
        tab["artifact_dir"] == "data/repository_automation/"
        for tab in smoke.generated_artifact_tabs
    )
    assert any(item.directory == "data/repository_automation" for item in inventory.items)
    assert any(
        item["path"] == "/repository/automation-plan"
        for item in api_contract.docs_api_coverage
    )
    assert any(
        item["producer_endpoint"] == "POST /repository/automation-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
