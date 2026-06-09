import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.services import WorkflowTemplateService

HEADERS = {"X-API-Key": "dev-local-token"}


def fresh_client(review_dir: Path | None = None) -> TestClient:
    main_module.state = create_state()
    if review_dir:
        main_module.state.workflows = WorkflowTemplateService(main_module.state, review_dir=review_dir)
    return TestClient(app)


def review_template(template_id: str = "reviewed_support_pack") -> dict:
    return {
        "id": template_id,
        "name": "Reviewed Support Pack",
        "description": "Classify and summarize a support request after workflow review approval.",
        "ordered_skill_ids": ["classify_request", "summarize_document"],
        "required_role": "agent",
        "default_sensitivity": "internal",
        "expected_outputs": ["category", "summary"],
    }


def test_workflow_template_listing() -> None:
    client = fresh_client()

    response = client.get("/workflows/templates", headers=HEADERS)

    assert response.status_code == 200
    template_ids = {template["id"] for template in response.json()}
    assert {"support_triage", "rfp_answer_pack", "meeting_to_actions"} <= template_ids


def test_successful_workflow_simulation_runs_promoted_skills() -> None:
    client = fresh_client()

    response = client.post(
        "/workflows/meeting_to_actions/simulate",
        headers=HEADERS,
        json={
            "input_text": "Action: Priya Shah to follow up with Atlas Labs by 2026-06-15.",
            "role": "agent",
            "data_sensitivity": "internal",
            "environment": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["blocked_steps"] == []
    assert payload["selected_skills"] == [
        "summarize_document",
        "extract_entities",
        "generate_action_items",
    ]
    assert all(step["status"] == "succeeded" for step in payload["step_outputs"])
    assert "Meeting To Actions completed" in payload["final_output"]


def test_denied_confidential_workflow_stops_at_policy_gate() -> None:
    client = fresh_client()

    response = client.post(
        "/workflows/rfp_answer_pack/simulate",
        headers=HEADERS,
        json={
            "input_text": "Confidential RFP request about audit history.",
            "role": "agent",
            "data_sensitivity": "confidential",
            "environment": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_skills"] == []
    assert len(payload["blocked_steps"]) == 1
    blocked = payload["blocked_steps"][0]
    assert blocked["skill_id"] == "classify_request"
    assert blocked["status"] == "denied"
    assert "confidential-requires-admin-or-reviewer" in blocked["policy_decision"]["matched_rules"]
    assert "template-required-role" in blocked["policy_decision"]["matched_rules"]


def test_workflow_skips_disabled_or_unpromoted_skill_execution() -> None:
    client = fresh_client()
    main_module.state.registry.set_status("summarize_document", False, "pytest")

    response = client.post(
        "/workflows/meeting_to_actions/simulate",
        headers=HEADERS,
        json={
            "input_text": "Action: Devan to send the meeting notes.",
            "role": "agent",
            "data_sensitivity": "internal",
            "environment": "local",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_skills"] == []
    assert payload["blocked_steps"][0]["skill_id"] == "summarize_document"
    assert "skill-must-be-promoted" in payload["blocked_steps"][0]["policy_decision"]["matched_rules"]
    assert main_module.state.invocation_service.invocations == []


def test_workflow_trace_contains_step_policy_and_trace_ids() -> None:
    client = fresh_client()

    response = client.post(
        "/workflows/support_triage/simulate",
        headers=HEADERS,
        json={
            "input_text": "Support ticket: security review is blocking the RFP response.",
            "role": "agent",
            "data_sensitivity": "internal",
            "environment": "local",
        },
    )

    assert response.status_code == 200
    trace = response.json()["trace"]
    assert trace
    assert trace[0]["step_index"] == 1
    assert trace[0]["skill_id"] == "classify_request"
    assert trace[0]["policy_decision"] == "allow"
    assert trace[0]["trace_id"].startswith("trc_")
    assert "default-allow" in trace[0]["matched_rules"]


def test_submit_lists_review_and_excludes_pending_template(tmp_path: Path) -> None:
    client = fresh_client(tmp_path)

    submitted = client.post(
        "/workflows/templates/submit",
        headers=HEADERS,
        json=review_template(),
    )
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "in_review"
    assert body["validation"]["validation_status"] == "valid"

    reviews = client.get("/workflows/reviews", headers=HEADERS)
    assert reviews.status_code == 200
    review = next(item for item in reviews.json() if item["template_id"] == "reviewed_support_pack")
    assert review["validation"]["missing_skills"] == []
    assert review["validation"]["required_role"] == "agent"
    assert review["validation"]["sensitivity"] == "internal"

    templates = client.get("/workflows/templates", headers=HEADERS).json()
    assert "reviewed_support_pack" not in {template["id"] for template in templates}

    simulation = client.post(
        "/workflows/reviewed_support_pack/simulate",
        headers=HEADERS,
        json={"input_text": "Support request for a governed review."},
    )
    assert simulation.status_code == 404


def test_approved_template_becomes_listed_and_simulatable(tmp_path: Path) -> None:
    client = fresh_client(tmp_path)
    client.post("/workflows/templates/submit", headers=HEADERS, json=review_template())

    approved = client.post(
        "/workflows/reviewed_support_pack/approve",
        headers=HEADERS,
        json={"actor": "pytest-reviewer", "note": "Approved for local composition."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    templates = client.get("/workflows/templates", headers=HEADERS).json()
    assert "reviewed_support_pack" in {template["id"] for template in templates}

    simulation = client.post(
        "/workflows/reviewed_support_pack/simulate",
        headers=HEADERS,
        json={
            "input_text": "Support request: customer needs an audit summary.",
            "role": "agent",
            "data_sensitivity": "internal",
            "environment": "local",
        },
    )
    assert simulation.status_code == 200
    payload = simulation.json()
    assert payload["blocked_steps"] == []
    assert payload["selected_skills"] == ["classify_request", "summarize_document"]


def test_rejected_template_stays_excluded(tmp_path: Path) -> None:
    client = fresh_client(tmp_path)
    client.post(
        "/workflows/templates/submit",
        headers=HEADERS,
        json=review_template("rejected_support_pack"),
    )

    rejected = client.post(
        "/workflows/rejected_support_pack/reject",
        headers=HEADERS,
        json={"actor": "pytest-reviewer", "note": "Needs owner changes."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    templates = client.get("/workflows/templates", headers=HEADERS).json()
    assert "rejected_support_pack" not in {template["id"] for template in templates}

    simulation = client.post(
        "/workflows/rejected_support_pack/simulate",
        headers=HEADERS,
        json={"input_text": "Should not run."},
    )
    assert simulation.status_code == 404


def test_invalid_review_reports_missing_skill_and_cannot_be_approved(tmp_path: Path) -> None:
    client = fresh_client(tmp_path)
    template = review_template("invalid_review_pack")
    template["ordered_skill_ids"] = ["classify_request", "missing_enterprise_skill"]

    submitted = client.post("/workflows/templates/submit", headers=HEADERS, json=template)
    assert submitted.status_code == 200
    assert submitted.json()["validation"]["validation_status"] == "invalid"
    assert submitted.json()["validation"]["missing_skills"] == ["missing_enterprise_skill"]

    approved = client.post(
        "/workflows/invalid_review_pack/approve",
        headers=HEADERS,
        json={"actor": "pytest-reviewer"},
    )
    assert approved.status_code == 422


def test_review_evidence_export_writes_markdown_and_json(tmp_path: Path) -> None:
    client = fresh_client(tmp_path)
    client.post("/workflows/templates/submit", headers=HEADERS, json=review_template())
    client.post(
        "/workflows/reviewed_support_pack/approve",
        headers=HEADERS,
        json={"actor": "pytest-reviewer", "note": "Evidence ready."},
    )

    response = client.post(
        "/workflows/reviewed_support_pack/review-evidence",
        headers=HEADERS,
    )

    assert response.status_code == 200
    export = response.json()
    assert export["status"] == "approved"
    assert export["summary"]["validation_status"] == "valid"
    json_path = Path(export["json_path"])
    markdown_path = Path(export["markdown_path"])
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["template"]["id"] == "reviewed_support_pack"
    assert bundle["simulation_dry_run"]["blocked_steps"] == []
    assert bundle["approval_rejection"]["status"] == "approved"
    assert any(event["action"] == "workflow_template.approved" for event in bundle["audit_events"])
    assert "Workflow Template Review Evidence" in markdown_path.read_text(encoding="utf-8")
