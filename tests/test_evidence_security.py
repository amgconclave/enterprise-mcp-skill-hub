from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.services import EvidenceBundleService

HEADERS = {"X-API-Key": "dev-local-token"}


def test_security_review_summary_fields_include_denials() -> None:
    main_module.state = create_state()
    client = TestClient(app)
    denied = client.post(
        "/skills/classify_request/invoke",
        headers=HEADERS,
        json={
            "input": {"request": "Classify this confidential security review request."},
            "policy_context": {
                "role": "viewer",
                "environment": "local",
                "data_sensitivity": "confidential",
                "requested_action": "invoke",
                "enforce": True,
            },
        },
    )

    response = client.get("/security/review-summary", headers=HEADERS)

    assert denied.status_code == 403
    assert response.status_code == 200
    body = response.json()
    assert {
        "generated_at",
        "readiness_status",
        "policy_denial_count",
        "promoted_skill_count",
        "conformance_pass_count",
        "high_risk_flags",
        "recommended_actions",
    }.issubset(body)
    assert body["policy_denial_count"] == 1
    assert body["promoted_skill_count"] == 6
    assert body["conformance_pass_count"] == 6
    assert body["readiness_status"] == "needs_review"
    assert "policy_denials_recorded" in body["high_risk_flags"]


def test_evidence_export_writes_json_and_markdown_contents(tmp_path: Path) -> None:
    main_module.state = create_state()
    main_module.state.evidence = EvidenceBundleService(main_module.state, tmp_path)
    client = TestClient(app)
    client.patch(
        "/skills/translate_text/status",
        headers=HEADERS,
        json={"enabled": False, "actor": "pytest"},
    )
    client.post(
        "/skills/register",
        headers=HEADERS,
        json={
            "manifest": {
                "id": "draft_security_packet",
                "name": "Draft Security Packet",
                "version": "1.0.0",
                "description": "Draft-only security review helper.",
                "provider": "mock",
                "enabled": True,
                "status": "draft",
                "tags": ["security", "review"],
                "input_schema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                },
            }
        },
    )
    client.post(
        "/skills/classify_request/invoke",
        headers=HEADERS,
        json={
            "input": {"request": "Classify this confidential security review request."},
            "policy_context": {
                "role": "viewer",
                "environment": "local",
                "data_sensitivity": "confidential",
                "requested_action": "invoke",
                "enforce": True,
            },
        },
    )

    response = client.post("/evidence/export", headers=HEADERS)

    assert response.status_code == 200
    export = response.json()
    json_path = Path(export["json_path"])
    markdown_path = Path(export["markdown_path"])
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert bundle["governance_report"]["skills_registered"] == 7
    assert bundle["conformance_report"]["promoted_skill_count"] == 5
    assert bundle["policy_summary"]["denied_count"] > 0
    assert "classify_request" in {skill["id"] for skill in bundle["promoted_skills"]}
    assert "translate_text" in {skill["id"] for skill in bundle["excluded_skills"]["disabled"]}
    assert "draft_security_packet" in {skill["id"] for skill in bundle["excluded_skills"]["draft"]}
    assert bundle["denied_policy_attempts"][0]["skill_id"] == "classify_request"
    assert bundle["mcp_summary"]["tool_count"] == 5
    assert bundle["mcp_summary"]["resource_count"] >= 4
    assert bundle["mcp_summary"]["prompt_count"] == 4
    assert "workflow_composition" in bundle["mcp_summary"]["prompts"]
    assert bundle["recommended_next_controls"]
    assert "# Security Evidence Bundle" in markdown
    assert "## MCP Exposure" in markdown
