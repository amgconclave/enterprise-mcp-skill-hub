from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import AuditPackRequest
from app.services import CiDoctorService

HEADERS = {"X-API-Key": "dev-local-token"}


def ci_doctor_state(tmp_path: Path):
    state = create_state()
    state.ci_doctor = CiDoctorService(state, output_dir=tmp_path / "audit_packs")
    return state


def test_ci_doctor_returns_structured_local_audit_checks(tmp_path: Path) -> None:
    state = ci_doctor_state(tmp_path)

    doctor = asyncio.run(state.ci_doctor.ci_doctor())

    check_ids = {check.id for check in doctor.checks}
    command_ids = {check.id for check in doctor.command_checks}
    assert doctor.doctor_id == "ci_doctor_latest"
    assert doctor.readiness_status in {"ready", "needs_review", "blocked"}
    assert 0 <= doctor.score <= 100
    assert {
        "github_actions_workflows",
        "docker_compose",
        "env_example",
        "readme_required_sections",
        "docs_presence",
        "generated_artifact_ignores",
        "dependency_files",
        "local_mock_provider_notes",
        "secret_scan_summary",
    } <= check_ids
    assert {
        "command_pytest",
        "command_ruff",
        "command_eval",
        "command_eval_validate_only",
        "command_conformance",
        "command_demo",
        "command_mcp_tools",
        "command_mcp_resources",
        "command_mcp_prompts",
    } <= command_ids
    assert "pyproject.toml" in {item["path"] for item in doctor.dependency_inventory["files"]}
    assert "requirements.txt" in {item["path"] for item in doctor.dependency_inventory["files"]}
    assert doctor.secret_scan_summary["scanner"] == "local_regex_secret_scan"
    assert any(
        "data/audit_packs/" in check.evidence
        for check in doctor.checks
        if check.id == "generated_artifact_ignores"
    )


def test_audit_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = ci_doctor_state(tmp_path)

    export = asyncio.run(
        state.ci_doctor.audit_pack(
            AuditPackRequest(actor="pytest-ci-doctor")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["pack_id"] == "audit_pack_latest"
    assert "ci_doctor" in bundle
    assert "dependency_inventory" in bundle
    assert "secret_scan_summary" in bundle
    assert "local_verification_commands" in bundle
    assert "publish_safety_checklist" in bundle
    assert "remediation_notes" in bundle
    assert "recruiter_interviewer_explanation" in bundle
    assert any("ops/ci-doctor" in command for command in bundle["local_verification_commands"])
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Local CI Doctor Audit Pack" in markdown
    assert "Secret Scan Summary" in markdown
    assert "Publish-Safety Checklist" in markdown


def test_ci_doctor_endpoints_return_doctor_and_audit_pack(tmp_path: Path) -> None:
    main_module.state = ci_doctor_state(tmp_path)
    client = TestClient(app)

    doctor = client.get("/ops/ci-doctor", headers=HEADERS)
    export = client.post("/ops/audit-pack", headers=HEADERS)

    assert doctor.status_code == 200
    assert doctor.json()["doctor_id"] == "ci_doctor_latest"
    assert doctor.json()["dependency_inventory"]["files"]
    assert export.status_code == 200
    assert export.json()["pack_id"] == "audit_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
