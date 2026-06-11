from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.models import (
    GitPushPlanRequest,
    GitPushPlanResult,
    GitReadinessResult,
    JsonDict,
    RepositoryAutomationPackRequest,
    RepositoryAutomationPackResult,
    RepositoryAutomationPlanRequest,
    RepositoryAutomationPlanResult,
    RepositoryAutomationTask,
    SecurityReadinessStatus,
)
from app.utils import new_trace_id, utc_now


class GitReadinessService:
    READINESS_ID = "git_readiness_latest"
    PACK_ID = "git_push_plan_latest"
    AUTOMATION_PLAN_ID = "repo_automation_plan_latest"
    AUTOMATION_PACK_ID = "repo_automation_pack_latest"
    LARGE_FILE_BYTES = 1_000_000
    GENERATED_DIRECTORIES = [
        "data/evidence/",
        "data/releases/",
        "data/attestations/",
        "data/capacity/",
        "data/dependencies/",
        "data/incident_runbooks/",
        "data/tenant_sandboxes/",
        "data/portfolio_demo/",
        "data/portfolio_packs/",
        "data/launch_checklists/",
        "data/release_packs/",
        "data/audit_packs/",
        "data/privacy_packs/",
        "data/reviewer_packs/",
        "data/artifact_indexes/",
        "data/ui_verification/",
        "data/final_handoff/",
        "data/git_packs/",
        "data/repository_automation/",
        "data/conformance/",
        "data/governance/",
        "data/workflow_reviews/",
        ".local/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".venv/",
    ]

    def __init__(
        self,
        output_dir: Path | None = None,
        repo_root: Path | None = None,
        automation_output_dir: Path | None = None,
    ) -> None:
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]
        self.output_dir = output_dir or Path("data") / "git_packs"
        self.automation_output_dir = automation_output_dir or Path("data") / "repository_automation"

    def readiness(self) -> GitReadinessResult:
        git_repository = self._git_repository()
        status_entries = self._status_entries() if git_repository["detected"] else []
        worktree_summary = self._worktree_summary(status_entries)
        generated_dirs = self._generated_artifact_directories()
        changed_groups = self._changed_file_groups(status_entries)
        suspicious_files = self._suspicious_files(status_entries)
        required_checks = self._required_publish_checks(generated_dirs)
        failures = [check for check in required_checks if check["status"] == "fail"]
        warnings = [
            check for check in required_checks if check["status"] == "warn"
        ] + suspicious_files
        readiness_status = self._readiness_status(git_repository, worktree_summary, failures, warnings)
        score = self._score(git_repository, worktree_summary, failures, warnings)
        recommended_groups = self._recommended_commit_groups(status_entries)
        summary = {
            "local_only": True,
            "git_repo_detected": git_repository["detected"],
            "current_branch": git_repository["current_branch"],
            "dirty": worktree_summary["dirty"],
            "changed_path_count": worktree_summary["changed_path_count"],
            "untracked_count": worktree_summary["untracked_count"],
            "modified_count": worktree_summary["modified_count"],
            "ignored_count": worktree_summary["ignored_count"],
            "generated_directory_count": len(generated_dirs),
            "ignored_generated_directory_count": sum(1 for row in generated_dirs if row["ignored"]),
            "suspicious_file_count": len(suspicious_files),
            "required_check_fail_count": len(failures),
            "required_check_warn_count": len([check for check in required_checks if check["status"] == "warn"]),
            "recommended_commit_group_count": len(recommended_groups),
            "artifact_root": str(self.output_dir),
        }
        return GitReadinessResult(
            readiness_id=self.READINESS_ID,
            generated_at=utc_now(),
            readiness_status=readiness_status,
            score=score,
            summary=summary,
            git_repository=git_repository,
            worktree_summary=worktree_summary,
            generated_artifact_directories=generated_dirs,
            changed_file_groups=changed_groups,
            suspicious_files=suspicious_files,
            required_publish_checks=required_checks,
            dirty_worktree_guidance=self._dirty_worktree_guidance(worktree_summary),
            recommended_commit_groups=recommended_groups,
            mcp_publish_notes=self._mcp_publish_notes(),
            non_destructive_review_commands=self._non_destructive_review_commands(),
            limitations=self._limitations(),
        )

    def push_plan(self, request: GitPushPlanRequest | None = None) -> GitPushPlanResult:
        request = request or GitPushPlanRequest()
        readiness = self.readiness()
        bundle = {
            "pack_id": self.PACK_ID,
            "generated_at": utc_now().isoformat(),
            "actor": request.actor,
            "readiness_status": readiness.readiness_status,
            "score": readiness.score,
            "git_readiness": readiness.model_dump(mode="json"),
            "exact_non_destructive_review_commands": readiness.non_destructive_review_commands,
            "suggested_commit_grouping": readiness.recommended_commit_groups,
            "do_not_commit_generated_artifact_notes": self._do_not_commit_generated_artifact_notes(readiness),
            "pre_push_verification_checklist": self._pre_push_verification_checklist(),
            "mcp_command_verification": self._mcp_command_verification(),
            "repo_limitations": readiness.limitations,
            "recruiter_github_readme_publish_blurb": self._recruiter_github_readme_publish_blurb(readiness),
        }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"{self.PACK_ID}.json"
        markdown_path = self.output_dir / f"{self.PACK_ID}.md"
        json_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(self._markdown(bundle), encoding="utf-8")
        return GitPushPlanResult(
            pack_id=self.PACK_ID,
            generated_at=utc_now(),
            readiness_status=readiness.readiness_status,
            score=readiness.score,
            json_path=str(json_path.resolve()),
            markdown_path=str(markdown_path.resolve()),
            summary={
                "readiness_status": readiness.readiness_status,
                "score": readiness.score,
                "dirty": readiness.worktree_summary["dirty"],
                "changed_path_count": readiness.worktree_summary["changed_path_count"],
                "suspicious_file_count": len(readiness.suspicious_files),
                "recommended_commit_group_count": len(readiness.recommended_commit_groups),
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
        )

    def automation_plan(
        self,
        request: RepositoryAutomationPlanRequest | None = None,
    ) -> RepositoryAutomationPlanResult:
        request = request or RepositoryAutomationPlanRequest()
        readiness = self.readiness()
        automation_tasks = self._automation_tasks(readiness, request)
        blocked_mutation_count = sum(
            1
            for task in automation_tasks
            if task.action_class == "repo_mutation" and task.sandbox_decision == "deny"
        )
        readiness_status: SecurityReadinessStatus = readiness.readiness_status
        if blocked_mutation_count:
            readiness_status = "needs_review"
        if not readiness.git_repository["detected"]:
            readiness_status = "blocked"
        summary = {
            "local_only": True,
            "dry_run_only": True,
            "target_branch": request.target_branch,
            "include_mutating_commands": request.include_mutating_commands,
            "planned_task_count": len(automation_tasks),
            "blocked_mutation_count": blocked_mutation_count,
            "manual_approval_task_count": sum(
                1 for task in automation_tasks if task.manual_approval_required
            ),
            "changed_path_count": readiness.worktree_summary["changed_path_count"],
            "source_readiness_status": readiness.readiness_status,
            "artifact_root": str(self.automation_output_dir),
        }
        return RepositoryAutomationPlanResult(
            plan_id=self.AUTOMATION_PLAN_ID,
            generated_at=utc_now(),
            readiness_status=readiness_status,
            score=max(0, readiness.score - min(20, blocked_mutation_count * 5)),
            summary=summary,
            repository=readiness.git_repository,
            sandbox_policy=self._automation_sandbox_policy(),
            automation_tasks=automation_tasks,
            transparent_runbook=self._transparent_runbook(automation_tasks),
            local_proof_commands=self._automation_proof_commands(),
            limitations=self._automation_limitations(),
        )

    def automation_pack(
        self,
        request: RepositoryAutomationPackRequest | None = None,
    ) -> RepositoryAutomationPackResult:
        request = request or RepositoryAutomationPackRequest()
        plan = self.automation_plan(
            RepositoryAutomationPlanRequest(
                actor=request.actor,
                target_branch=request.target_branch,
                include_mutating_commands=False,
            )
        )
        bundle = {
            "pack_id": self.AUTOMATION_PACK_ID,
            "generated_at": utc_now().isoformat(),
            "actor": request.actor,
            "readiness_status": plan.readiness_status,
            "score": plan.score,
            "repository_automation_plan": plan.model_dump(mode="json"),
            "architecture_patterns": [
                "repository automation",
                "task sandbox",
                "run transparency",
                "structured outputs",
            ],
            "manual_approval_policy": self._manual_approval_policy(),
            "local_verification_commands": plan.local_proof_commands,
            "limitations": plan.limitations,
        }
        self.automation_output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.automation_output_dir / f"{self.AUTOMATION_PACK_ID}.json"
        markdown_path = self.automation_output_dir / f"{self.AUTOMATION_PACK_ID}.md"
        json_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(self._automation_markdown(bundle), encoding="utf-8")
        return RepositoryAutomationPackResult(
            pack_id=self.AUTOMATION_PACK_ID,
            generated_at=utc_now(),
            readiness_status=plan.readiness_status,
            score=plan.score,
            json_path=str(json_path.resolve()),
            markdown_path=str(markdown_path.resolve()),
            summary={
                "readiness_status": plan.readiness_status,
                "score": plan.score,
                "planned_task_count": len(plan.automation_tasks),
                "blocked_mutation_count": plan.summary["blocked_mutation_count"],
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
        )

    def _git_repository(self) -> JsonDict:
        inside = self._git(["rev-parse", "--is-inside-work-tree"])
        root = self._git(["rev-parse", "--show-toplevel"])
        branch = self._git(["branch", "--show-current"])
        detected = inside["returncode"] == 0 and inside["stdout"].strip().lower() == "true"
        return {
            "detected": detected,
            "repo_root": root["stdout"].strip() if root["returncode"] == 0 else str(self.repo_root),
            "current_branch": branch["stdout"].strip() or None,
            "detached_head": detected and not branch["stdout"].strip(),
            "inspection_errors": [
                item["stderr"].strip()
                for item in [inside, root, branch]
                if item["returncode"] != 0 and item["stderr"].strip()
            ],
        }

    def _status_entries(self) -> list[JsonDict]:
        result = self._git(["status", "--porcelain=v1", "--ignored"])
        entries = []
        for line in result["stdout"].splitlines():
            if len(line) < 4:
                continue
            code = line[:2]
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            entries.append(
                {
                    "code": code,
                    "path": path.replace("\\", "/"),
                    "category": self._status_category(code),
                    "tracked": code not in {"??", "!!"},
                }
            )
        return entries

    def _worktree_summary(self, entries: list[JsonDict]) -> JsonDict:
        paths = [entry["path"] for entry in entries if entry["category"] != "ignored"]
        tracked = [entry for entry in entries if entry["tracked"] and entry["category"] != "ignored"]
        untracked = [entry for entry in entries if entry["category"] == "untracked"]
        ignored = [entry for entry in entries if entry["category"] == "ignored"]
        modified = [entry for entry in entries if "M" in entry["code"]]
        deleted = [entry for entry in entries if "D" in entry["code"]]
        renamed = [entry for entry in entries if "R" in entry["code"]]
        added = [entry for entry in entries if "A" in entry["code"]]
        return {
            "dirty": bool(paths),
            "changed_path_count": len(paths),
            "tracked_changed_count": len(tracked),
            "untracked_count": len(untracked),
            "modified_count": len(modified),
            "deleted_count": len(deleted),
            "renamed_count": len(renamed),
            "added_count": len(added),
            "ignored_count": len(ignored),
            "tracked_changed_paths": [entry["path"] for entry in tracked],
            "untracked_paths": [entry["path"] for entry in untracked],
            "ignored_paths_sample": [entry["path"] for entry in ignored[:25]],
            "status_entries": entries,
        }

    def _generated_artifact_directories(self) -> list[JsonDict]:
        gitignore_text = self._read_text(Path(".gitignore"))
        rows = []
        for directory in self.GENERATED_DIRECTORIES:
            path = self.repo_root / directory.rstrip("/")
            ignored = self._check_ignored(directory)
            rows.append(
                {
                    "directory": directory,
                    "exists": path.exists(),
                    "ignored": ignored,
                    "gitignore_mentioned": directory in gitignore_text,
                    "should_stay_ignored": True,
                    "note": "Generated, cache, or local-only output; regenerate locally instead of committing.",
                }
            )
        return rows

    def _changed_file_groups(self, entries: list[JsonDict]) -> JsonDict:
        changed_paths = [entry["path"] for entry in entries if entry["category"] != "ignored"]
        return {
            "source_files_changed": self._filter_paths(changed_paths, ["app/"]),
            "doc_files_changed": self._filter_paths(changed_paths, ["README.md", "docs/"]),
            "test_files_changed": self._filter_paths(changed_paths, ["tests/"]),
            "dashboard_files_changed": self._filter_paths(changed_paths, ["dashboard/"]),
            "script_files_changed": self._filter_paths(changed_paths, ["scripts/"]),
            "sample_data_files_changed": self._filter_paths(changed_paths, ["sample_data/"]),
            "config_ci_files_changed": self._filter_paths(
                changed_paths,
                [".github/", ".gitignore", ".env.example", "Makefile", "pyproject.toml", "requirements"],
            ),
            "generated_or_local_files_changed": [
                path for path in changed_paths if self._is_under_any(path, self.GENERATED_DIRECTORIES)
            ],
        }

    def _suspicious_files(self, entries: list[JsonDict]) -> list[JsonDict]:
        suspicious = []
        for entry in entries:
            if entry["category"] == "ignored":
                continue
            path = entry["path"]
            full_path = self.repo_root / path
            reasons = []
            size = full_path.stat().st_size if full_path.exists() and full_path.is_file() else 0
            if size >= self.LARGE_FILE_BYTES:
                reasons.append(f"large_file_{size}_bytes")
            if self._is_under_any(path, self.GENERATED_DIRECTORIES):
                reasons.append("generated_or_local_artifact_path")
            if full_path.suffix.lower() in {".pyc", ".sqlite3", ".db", ".log", ".zip", ".tar", ".gz"}:
                reasons.append("generated_or_binary_like_extension")
            if reasons:
                suspicious.append(
                    {
                        "path": path,
                        "status_code": entry["code"],
                        "size_bytes": size,
                        "reasons": reasons,
                        "review_action": "Inspect before staging; commit only if this is intentional source evidence.",
                    }
                )
        return suspicious

    def _required_publish_checks(self, generated_dirs: list[JsonDict]) -> list[JsonDict]:
        workflows = sorted((self.repo_root / ".github" / "workflows").glob("*.y*ml"))
        readme_text = self._read_text(Path("README.md"))
        checks = [
            {
                "id": "github_actions_workflow_presence",
                "status": "pass" if workflows else "fail",
                "title": "GitHub Actions workflow presence",
                "detail": f"Found {len(workflows)} workflow file(s).",
                "evidence": [str(path.relative_to(self.repo_root)) for path in workflows],
            },
            {
                "id": "readme_final_handoff_mention",
                "status": "pass" if "Final Handoff" in readme_text and "data/final_handoff/" in readme_text else "warn",
                "title": "README final handoff mention",
                "detail": "README mentions Final Handoff and generated final_handoff artifacts."
                if "Final Handoff" in readme_text and "data/final_handoff/" in readme_text
                else "README should mention Final Handoff and data/final_handoff/ before publishing.",
                "evidence": ["README.md"],
            },
            {
                "id": "env_example_present",
                "status": "pass" if (self.repo_root / ".env.example").exists() else "fail",
                "title": ".env.example present",
                "detail": "Safe local/mock environment example is present."
                if (self.repo_root / ".env.example").exists()
                else ".env.example is missing.",
                "evidence": [".env.example"] if (self.repo_root / ".env.example").exists() else [],
            },
        ]
        missing_ignored = [row["directory"] for row in generated_dirs if not row["ignored"]]
        checks.append(
            {
                "id": "generated_artifact_directories_ignored",
                "status": "pass" if not missing_ignored else "fail",
                "title": "Generated artifact directories stay ignored",
                "detail": "All generated artifact/cache directories are ignored."
                if not missing_ignored
                else f"Missing ignore coverage: {', '.join(missing_ignored)}",
                "evidence": [row["directory"] for row in generated_dirs if row["ignored"]],
            }
        )
        return checks

    def _dirty_worktree_guidance(self, summary: JsonDict) -> list[str]:
        if not summary["dirty"]:
            return [
                "Worktree appears clean from read-only git status inspection.",
                "Run verification commands before staging or pushing future changes.",
            ]
        return [
            "Worktree is dirty; inspect `git status --porcelain` before staging anything.",
            "Do not sweep unrelated user or agent changes into a commit group.",
            "Keep generated `data/` artifacts ignored and regenerate them locally for review.",
            "Stage source, tests, dashboard, docs, and config groups intentionally after verification passes.",
        ]

    def _recommended_commit_groups(self, entries: list[JsonDict]) -> list[JsonDict]:
        paths = [entry["path"] for entry in entries if entry["category"] != "ignored"]
        group_defs = [
            ("git_readiness_api_service", "Git readiness API/service/models", ["app/"]),
            ("git_readiness_tests", "Git readiness and dashboard tests", ["tests/"]),
            ("git_readiness_dashboard", "Streamlit Git Readiness dashboard", ["dashboard/"]),
            ("git_readiness_docs", "README and docs updates", ["README.md", "docs/"]),
            ("local_scripts_and_config", "Local scripts, sample data, and config", ["scripts/", "sample_data/", ".github/", ".gitignore", "Makefile"]),
        ]
        groups = []
        used: set[str] = set()
        for group_id, title, prefixes in group_defs:
            matched = self._filter_paths(paths, prefixes)
            if matched:
                used.update(matched)
                groups.append(
                    {
                        "id": group_id,
                        "title": title,
                        "paths": matched,
                        "review_note": "Review these paths together; do not stage generated artifacts with this group.",
                    }
                )
        leftovers = sorted(set(paths) - used)
        if leftovers:
            groups.append(
                {
                    "id": "manual_review",
                    "title": "Manual review before staging",
                    "paths": leftovers,
                    "review_note": "These paths did not match the standard commit groups; inspect ownership first.",
                }
            )
        return groups

    def _mcp_publish_notes(self) -> list[str]:
        return [
            "Run `python -m app.mcp_server tools` to confirm promoted skills expose as MCP tools.",
            "Run `python -m app.mcp_server resources` to confirm policy/product/workflow resources are discoverable.",
            "Run `python -m app.mcp_server prompts` to confirm prompt templates remain visible.",
            "Git readiness does not call GitHub APIs or publish anything; it is a local reviewer gate.",
            "Generated GitHub Push Readiness + Branch Hygiene Pack files live under ignored `data/git_packs/`.",
            "Generated Repository Automation Plan files live under ignored `data/repository_automation/`.",
        ]

    def _non_destructive_review_commands(self) -> list[str]:
        return [
            "git rev-parse --is-inside-work-tree",
            "git rev-parse --show-toplevel",
            "git branch --show-current",
            "git status --porcelain=v1 --ignored",
            "git ls-files",
            "git check-ignore data/git_packs/",
            "git check-ignore data/final_handoff/",
            "python -m pytest -q",
            "python -m ruff check app tests dashboard",
            "python -m app.evals.run_eval",
            "python -m app.evals.run_eval --validate-only",
            "python -m app.evals.run_conformance",
            "python scripts\\dashboard_smoke.py",
            "python -m app.demo",
            "python -m app.mcp_server tools",
            "python -m app.mcp_server resources",
            "python -m app.mcp_server prompts",
            'rg "git/readiness|git/push-plan|GitHub Push Readiness|git_packs|Branch Hygiene|Git Readiness" app dashboard docs README.md tests scripts sample_data',
            "Get-ChildItem -Recurse -File data\\git_packs -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime",
            "Invoke-RestMethod http://localhost:8000/repository/automation-plan -Headers $headers",
            "Invoke-RestMethod http://localhost:8000/repository/automation-pack -Method POST -Headers $headers",
        ]

    def _do_not_commit_generated_artifact_notes(self, readiness: GitReadinessResult) -> list[str]:
        return [
            f"`{row['directory']}` should stay ignored and regenerable locally."
            for row in readiness.generated_artifact_directories
            if row["should_stay_ignored"]
        ]

    def _pre_push_verification_checklist(self) -> list[JsonDict]:
        return [
            {"command": "python -m pytest -q", "required": True, "purpose": "Run all local tests."},
            {"command": "python -m ruff check app tests dashboard", "required": True, "purpose": "Run lint."},
            {"command": "python -m app.evals.run_eval", "required": True, "purpose": "Run golden evals."},
            {"command": "python -m app.evals.run_eval --validate-only", "required": True, "purpose": "Validate manifests only."},
            {"command": "python -m app.evals.run_conformance", "required": True, "purpose": "Run MCP conformance."},
            {"command": "python scripts\\dashboard_smoke.py", "required": True, "purpose": "Verify dashboard source wiring."},
            {"command": "python -m app.demo", "required": True, "purpose": "Print demo and pack paths."},
        ]

    def _mcp_command_verification(self) -> list[JsonDict]:
        return [
            {"command": "python -m app.mcp_server tools", "expected": "Lists promoted local/mock MCP tools."},
            {"command": "python -m app.mcp_server resources", "expected": "Lists local MCP resources."},
            {"command": "python -m app.mcp_server prompts", "expected": "Lists reusable MCP prompts."},
        ]

    def _automation_tasks(
        self,
        readiness: GitReadinessResult,
        request: RepositoryAutomationPlanRequest,
    ) -> list[RepositoryAutomationTask]:
        groups = readiness.recommended_commit_groups
        if not groups:
            return [
                self._automation_task(
                    task_id="clean_worktree_publish_gate",
                    title="Clean worktree publish gate",
                    changed_paths=[],
                    action_class="unknown",
                    sandbox_decision="allow",
                    reasons=[
                        "No changed source paths were detected.",
                        "Run verification and inspect branch state before any human-driven publish action.",
                    ],
                    commands=[
                        "git status --porcelain=v1 --ignored",
                        "python -m pytest -q",
                        "python -m ruff check app tests dashboard",
                    ],
                    required_checks=[
                        "python -m app.evals.run_conformance",
                        "python -m app.mcp_server tools",
                    ],
                )
            ]

        tasks = []
        for index, group in enumerate(groups, start=1):
            changed_paths = list(group["paths"])
            commands = [
                "git status --porcelain=v1 --ignored",
                *[f"git diff -- {path}" for path in changed_paths[:5]],
                "python -m pytest -q",
                "python -m ruff check app tests dashboard",
            ]
            if request.include_mutating_commands:
                commands.extend(
                    [
                        "# Mutation commands intentionally remain comments in the dry-run plan.",
                        f"# git add {' '.join(changed_paths[:8])}",
                        f"# git commit -m \"{group['title']}\"",
                    ]
                )
            tasks.append(
                self._automation_task(
                    task_id=f"review_group_{index}_{group['id']}",
                    title=f"Review and approval plan for {group['title']}",
                    changed_paths=changed_paths,
                    action_class="repo_mutation",
                    sandbox_decision="deny",
                    reasons=[
                        "Repository mutation is blocked by the local task sandbox.",
                        "The plan may generate review commands, but staging, committing, pushing, checkout, reset, clean, and remote changes require a human outside this service.",
                        group["review_note"],
                    ],
                    commands=commands,
                    required_checks=[
                        "python -m app.evals.run_eval",
                        "python -m app.evals.run_eval --validate-only",
                        "python -m app.evals.run_conformance",
                        "python -m app.demo",
                        "python -m app.mcp_server tools",
                        "python -m app.mcp_server resources",
                        "python -m app.mcp_server prompts",
                    ],
                )
            )
        return tasks

    def _automation_task(
        self,
        task_id: str,
        title: str,
        changed_paths: list[str],
        action_class: str,
        sandbox_decision: str,
        reasons: list[str],
        commands: list[str],
        required_checks: list[str],
    ) -> RepositoryAutomationTask:
        return RepositoryAutomationTask(
            task_id=task_id,
            title=title,
            action_class=action_class,
            sandbox_decision=sandbox_decision,
            dry_run_only=True,
            changed_paths=changed_paths,
            planned_commands=commands,
            required_checks=required_checks,
            reasons=reasons,
            timeline=[
                {
                    "stage": "queued",
                    "status": "ready",
                    "message": "Repository automation task was planned from read-only git state.",
                },
                {
                    "stage": "sandbox_preflight",
                    "status": sandbox_decision,
                    "message": "Local sandbox permits read-only planning and blocks direct repo mutation."
                    if sandbox_decision == "deny"
                    else "Local sandbox permits read-only readiness inspection.",
                },
                {
                    "stage": "manual_review",
                    "status": "required",
                    "message": "A human must run any mutation command after verification and ownership review.",
                },
            ],
            manual_approval_required=True,
        )

    def _automation_sandbox_policy(self) -> JsonDict:
        return {
            "policy_id": "repository_automation_sandbox_v1",
            "dry_run_planning_allowed": True,
            "blocked_action_classes": [
                "repo_mutation",
                "filesystem_write",
                "process_spawn",
                "secret_access",
                "external_network",
            ],
            "blocked_commands": [
                "git add",
                "git commit",
                "git push",
                "git pull",
                "git reset",
                "git checkout",
                "git clean",
                "gh repo create",
                "gh pr create",
            ],
            "allowed_read_only_commands": [
                "git status",
                "git diff",
                "git branch --show-current",
                "git rev-parse",
                "git check-ignore",
                "rg",
                "python -m pytest -q",
                "python -m ruff check app tests dashboard",
            ],
        }

    def _transparent_runbook(self, tasks: list[RepositoryAutomationTask]) -> list[JsonDict]:
        return [
            {
                "step": index,
                "task_id": task.task_id,
                "title": task.title,
                "sandbox_decision": task.sandbox_decision,
                "dry_run_only": task.dry_run_only,
                "changed_path_count": len(task.changed_paths),
                "first_command": task.planned_commands[0] if task.planned_commands else None,
            }
            for index, task in enumerate(tasks, start=1)
        ]

    def _manual_approval_policy(self) -> JsonDict:
        return {
            "required": True,
            "owner": "repository maintainer",
            "rules": [
                "Inspect `git status --porcelain` and `git diff` before staging.",
                "Run the complete verification suite before any push.",
                "Keep ignored generated artifacts out of commits.",
                "Confirm terminal GitHub authentication separately with `gh auth status` before any future PR or push workflow.",
            ],
        }

    def _automation_proof_commands(self) -> list[str]:
        return [
            "python -m pytest -q",
            "python -m ruff check app tests dashboard",
            "python -m app.evals.run_eval",
            "python -m app.evals.run_eval --validate-only",
            "python -m app.evals.run_conformance",
            "python scripts\\dashboard_smoke.py",
            "python -m app.demo",
            "python -m app.mcp_server tools",
            "python -m app.mcp_server resources",
            "python -m app.mcp_server prompts",
            "Invoke-RestMethod http://localhost:8000/repository/automation-plan -Headers $headers",
            "Invoke-RestMethod http://localhost:8000/repository/automation-pack -Method POST -Headers $headers",
            "Get-ChildItem -Recurse -File data\\repository_automation -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime",
        ]

    def _automation_limitations(self) -> list[str]:
        return [
            "Repository automation is intentionally dry-run only and never stages, commits, pushes, pulls, checks out, resets, cleans, or changes remotes.",
            "Mutating commands are represented as blocked plan metadata, not executed commands.",
            "The planner derives tasks from local git status heuristics; maintainers still decide final ownership and commit boundaries.",
            "GitHub CLI and network operations remain outside this service and must be run manually only when explicitly intended.",
        ]

    def _automation_markdown(self, bundle: JsonDict) -> str:
        plan = bundle["repository_automation_plan"]
        lines = [
            "# Repository Automation Dry-Run Pack",
            "",
            f"- Pack ID: `{bundle['pack_id']}`",
            f"- Generated at: `{bundle['generated_at']}`",
            f"- Actor: `{bundle['actor']}`",
            f"- Readiness: `{bundle['readiness_status']}`",
            f"- Score: `{bundle['score']}`",
            f"- Planned tasks: `{plan['summary']['planned_task_count']}`",
            f"- Blocked mutations: `{plan['summary']['blocked_mutation_count']}`",
            "",
            "## Architecture Patterns",
            "",
            *[f"- {pattern}" for pattern in bundle["architecture_patterns"]],
            "",
            "## Sandbox Policy",
            "",
            *[f"- `{key}`: `{value}`" for key, value in plan["sandbox_policy"].items()],
            "",
            "## Automation Tasks",
            "",
            *[
                f"- `{task['task_id']}` {task['title']}: decision `{task['sandbox_decision']}`, paths `{len(task['changed_paths'])}`"
                for task in plan["automation_tasks"]
            ],
            "",
            "## Transparent Runbook",
            "",
            *[
                f"- Step {item['step']}: `{item['task_id']}` -> `{item['sandbox_decision']}`"
                for item in plan["transparent_runbook"]
            ],
            "",
            "## Manual Approval Policy",
            "",
            *[f"- {rule}" for rule in bundle["manual_approval_policy"]["rules"]],
            "",
            "## Local Verification Commands",
            "",
            *[f"- `{command}`" for command in bundle["local_verification_commands"]],
            "",
            "## Limitations",
            "",
            *[f"- {note}" for note in bundle["limitations"]],
            "",
        ]
        return "\n".join(lines)

    def _recruiter_github_readme_publish_blurb(self, readiness: GitReadinessResult) -> str:
        return (
            "GitHub Push Readiness + Branch Hygiene: this repo includes local-only endpoints "
            "`GET /git/readiness` and `POST /git/push-plan` that inspect branch/worktree hygiene, "
            f"recommend {len(readiness.recommended_commit_groups)} commit group(s), flag generated artifacts, "
            "and write ignored Markdown/JSON proof under `data/git_packs/` without staging, pushing, or calling GitHub."
        )

    def _limitations(self) -> list[str]:
        return [
            "Git readiness uses read-only local git commands and does not stage, commit, push, reset, clean, checkout, or call GitHub APIs.",
            "The service classifies changed paths heuristically; humans still choose the final commit boundaries.",
            "Command results are not cached as pass/fail proof; run the listed verification commands before publishing.",
            "Ignored generated artifacts are intentionally omitted from source control and should be regenerated locally.",
        ]

    def _readiness_status(
        self,
        git_repository: JsonDict,
        worktree_summary: JsonDict,
        failures: list[JsonDict],
        warnings: list[JsonDict],
    ) -> SecurityReadinessStatus:
        if not git_repository["detected"] or failures:
            return "blocked"
        if worktree_summary["dirty"] or warnings:
            return "needs_review"
        return "ready"

    def _score(
        self,
        git_repository: JsonDict,
        worktree_summary: JsonDict,
        failures: list[JsonDict],
        warnings: list[JsonDict],
    ) -> int:
        score = 100
        if not git_repository["detected"]:
            score -= 60
        score -= min(45, len(failures) * 18)
        score -= min(20, len(warnings) * 4)
        if worktree_summary["dirty"]:
            score -= min(20, max(4, worktree_summary["changed_path_count"] // 2))
        return max(0, min(100, score))

    def _status_category(self, code: str) -> str:
        if code == "??":
            return "untracked"
        if code == "!!":
            return "ignored"
        if "D" in code:
            return "deleted"
        if "R" in code:
            return "renamed"
        if "A" in code:
            return "added"
        if "M" in code:
            return "modified"
        return "changed"

    def _check_ignored(self, directory: str) -> bool:
        result = self._git(["check-ignore", directory])
        return result["returncode"] == 0

    def _git(self, args: list[str]) -> JsonDict:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"returncode": 1, "stdout": "", "stderr": str(exc)}
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": "git " + " ".join(args),
            "trace_id": new_trace_id(),
        }

    def _filter_paths(self, paths: list[str], prefixes: list[str]) -> list[str]:
        return sorted(
            path
            for path in paths
            if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)
        )

    def _is_under_any(self, path: str, directories: list[str]) -> bool:
        return any(path.startswith(directory.rstrip("/") + "/") for directory in directories)

    def _read_text(self, path: Path) -> str:
        full_path = self.repo_root / path
        if not full_path.exists() or not full_path.is_file():
            return ""
        return full_path.read_text(encoding="utf-8", errors="ignore")

    def _markdown(self, bundle: JsonDict) -> str:
        readiness = bundle["git_readiness"]
        lines = [
            "# GitHub Push Readiness + Branch Hygiene Pack",
            "",
            f"- Pack ID: `{bundle['pack_id']}`",
            f"- Generated at: `{bundle['generated_at']}`",
            f"- Actor: `{bundle['actor']}`",
            f"- Readiness: `{bundle['readiness_status']}`",
            f"- Score: `{bundle['score']}`",
            f"- Branch: `{readiness['git_repository']['current_branch']}`",
            "",
            "## Worktree Summary",
            "",
            *[f"- `{key}`: `{value}`" for key, value in readiness["worktree_summary"].items() if key != "status_entries"],
            "",
            "## Exact Non-Destructive Review Commands",
            "",
            *[f"- `{command}`" for command in bundle["exact_non_destructive_review_commands"]],
            "",
            "## Suggested Commit Grouping",
            "",
            *[
                f"- {group['title']}: `{', '.join(group['paths'])}`"
                for group in bundle["suggested_commit_grouping"]
            ],
            "",
            "## Do Not Commit Generated Artifacts",
            "",
            *[f"- {note}" for note in bundle["do_not_commit_generated_artifact_notes"]],
            "",
            "## Pre-Push Verification Checklist",
            "",
            *[
                f"- `{item['command']}` - {item['purpose']}"
                for item in bundle["pre_push_verification_checklist"]
            ],
            "",
            "## MCP Command Verification",
            "",
            *[
                f"- `{item['command']}` - {item['expected']}"
                for item in bundle["mcp_command_verification"]
            ],
            "",
            "## Required Publish Checks",
            "",
            *[
                f"- `{check['status']}` {check['title']}: {check['detail']}"
                for check in readiness["required_publish_checks"]
            ],
            "",
            "## Suspicious Files",
            "",
            *(
                [
                    f"- `{item['path']}`: {', '.join(item['reasons'])}"
                    for item in readiness["suspicious_files"]
                ]
                or ["- none"]
            ),
            "",
            "## Recruiter/GitHub README Publish Blurb",
            "",
            bundle["recruiter_github_readme_publish_blurb"],
            "",
            "## Repo Limitations",
            "",
            *[f"- {note}" for note in bundle["repo_limitations"]],
            "",
        ]
        return "\n".join(lines)
