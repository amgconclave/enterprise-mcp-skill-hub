from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import FinalHandoffPackRequest
from app.services import FinalHandoffService

HEADERS = {"X-API-Key": "dev-local-token"}


def final_state(tmp_path: Path):
    state = create_state()
    state.final_handoff = FinalHandoffService(state, output_dir=tmp_path / "final_handoff")
    return state


def test_final_audit_returns_readme_consistency_checks(tmp_path: Path) -> None:
    state = final_state(tmp_path)

    audit = state.final_handoff.final_audit()

    check_ids = {check.id for check in audit.checks}
    assert audit.audit_id == "final_readme_consistency_audit_latest"
    assert audit.readiness_status in {"ready", "needs_review", "blocked"}
    assert 0 <= audit.score <= 100
    assert {
        "readme_endpoint_mcp_mentions",
        "docs_api_coverage",
        "architecture_evaluation_coverage",
        "demo_output_claims",
        "scripts_present",
        "dashboard_smoke_script_present",
        "generated_artifact_directory_docs",
        "mcp_tools_resources_prompts_clarity",
        "local_mock_limitation_clarity",
        "azure_openai_optional_notes",
    } <= check_ids
    assert audit.endpoint_inventory_summary["final_endpoints_present"]["/handoff/final-audit"]
    assert audit.endpoint_inventory_summary["final_endpoints_present"]["/handoff/final-pack"]
    assert audit.mcp_inventory_summary["tool_count"] == 6
    assert audit.mcp_inventory_summary["resource_count"] >= 1
    assert audit.mcp_inventory_summary["prompt_count"] >= 1
    assert audit.artifact_inventory_summary["final_handoff_ignored"]
    assert any("handoff/final-pack" in command for command in audit.verification_commands)


def test_final_handoff_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = final_state(tmp_path)

    export = asyncio.run(
        state.final_handoff.final_pack(
            FinalHandoffPackRequest(actor="pytest-final-reviewer")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "final_handoff_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "final_audit" in bundle
    assert "exact_clone_run_commands" in bundle
    assert "end_to_end_verification_order" in bundle
    assert "endpoint_inventory_summary" in bundle
    assert "mcp_inventory_summary" in bundle
    assert "artifact_inventory_summary" in bundle
    assert "dashboard_smoke_summary" in bundle
    assert "eval_conformance_proof_summary" in bundle
    assert "recruiter_facing_final_readme_blurb" in bundle
    assert any(command.startswith("git clone") for command in bundle["exact_clone_run_commands"])
    assert "Final Handoff Pack" in markdown
    assert "Final Audit Results" in markdown
    assert "Recruiter-Facing Final README Blurb" in markdown


def test_final_handoff_endpoints_return_audit_and_pack(tmp_path: Path) -> None:
    main_module.state = final_state(tmp_path)
    client = TestClient(app)

    audit = client.get("/handoff/final-audit", headers=HEADERS)
    export = client.post(
        "/handoff/final-pack",
        json={"actor": "pytest-final-reviewer"},
        headers=HEADERS,
    )

    assert audit.status_code == 200
    assert audit.json()["audit_id"] == "final_readme_consistency_audit_latest"
    assert audit.json()["endpoint_inventory_summary"]["final_endpoints_present"]["/handoff/final-pack"]
    assert export.status_code == 200
    assert export.json()["pack_id"] == "final_handoff_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
