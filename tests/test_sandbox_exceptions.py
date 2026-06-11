from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    SandboxExceptionDecisionRequest,
    SandboxExceptionPackRequest,
    SandboxExceptionSubmitRequest,
)

HEADERS = {"X-API-Key": "dev-local-token"}


def exception_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.sandbox_exceptions.output_dir = tmp_path / "sandbox_exceptions"
        state.artifacts.output_dir = tmp_path / "artifact_indexes"
    return state


def test_sandbox_exception_submission_preserves_denied_decision() -> None:
    state = exception_state()

    record = state.sandbox_exceptions.submit(
        SandboxExceptionSubmitRequest(
            skill_id="extract_entities",
            input={"text": "try to write a local file"},
            requested_by="pytest-platform-engineer",
            business_justification="Need policy owner evidence before changing sandbox rules.",
            action_class="filesystem_write",
        )
    )

    assert record.status == "pending"
    assert record.sandbox_decision.decision == "deny"
    assert record.sandbox_decision.risk_label == "critical"
    assert "human-in-the-loop" in record.governance_patterns
    assert any("does not bypass" in item for item in record.approval_conditions)
    assert any(event.action == "sandbox_exception.submitted" for event in state.audit.events)


def test_sandbox_exception_requires_independent_reviewer_for_approval() -> None:
    state = exception_state()
    record = state.sandbox_exceptions.submit(
        SandboxExceptionSubmitRequest(
            skill_id="extract_entities",
            input={"text": "try to spawn a process"},
            requested_by="pytest-requester",
            business_justification="Need security review for an elevated action.",
            action_class="process_spawn",
        )
    )

    try:
        state.sandbox_exceptions.decide(
            record.exception_id,
            SandboxExceptionDecisionRequest(
                reviewer="pytest-requester",
                decision="approve",
                notes="Approving my own exception should not be allowed.",
            ),
        )
    except ValueError as exc:
        assert "independent reviewer" in str(exc)
    else:
        raise AssertionError("Self-approval should fail")

    approved = state.sandbox_exceptions.decide(
        record.exception_id,
        SandboxExceptionDecisionRequest(
            reviewer="pytest-security-reviewer",
            decision="approve",
            notes="Approved as review evidence only; runtime sandbox must still deny execution.",
        ),
    )

    assert approved.status == "approved"
    assert approved.reviewer == "pytest-security-reviewer"
    assert state.sandbox_exceptions.queue().summary["approval_is_runtime_bypass"] is False
    assert any(event.action == "sandbox_exception.approved" for event in state.audit.events)


def test_sandbox_exception_endpoints_pack_dashboard_inventory_and_contract(tmp_path: Path) -> None:
    state = exception_state(tmp_path)
    main_module.state = state
    client = TestClient(app)

    submit_response = client.post(
        "/sandbox/exceptions",
        headers=HEADERS,
        json={
            "skill_id": "extract_entities",
            "input": {"text": "try to write files"},
            "requested_by": "pytest-platform-engineer",
            "business_justification": "Need security review before changing sandbox policy.",
            "action_class": "filesystem_write",
        },
    )
    exception_id = submit_response.json()["exception_id"]
    decision_response = client.post(
        f"/sandbox/exceptions/{exception_id}/decision",
        headers=HEADERS,
        json={
            "reviewer": "pytest-security-reviewer",
            "decision": "deny",
            "notes": "Deny by default until the action class is narrowed by the policy owner.",
        },
    )
    queue_response = client.get("/sandbox/exceptions", headers=HEADERS)
    pack_response = client.post(
        "/sandbox/exceptions/pack",
        headers=HEADERS,
        json={"actor": "pytest-security-reviewer"},
    )
    pack = state.sandbox_exceptions.pack(SandboxExceptionPackRequest(actor="pytest-reviewer"))
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert submit_response.status_code == 200
    assert submit_response.json()["sandbox_decision"]["decision"] == "deny"
    assert decision_response.status_code == 200
    assert decision_response.json()["status"] == "denied"
    assert queue_response.status_code == 200
    assert queue_response.json()["summary"]["denied_count"] == 1
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    bundle = json.loads(Path(pack.json_path).read_text(encoding="utf-8"))
    assert bundle["summary"]["approval_is_runtime_bypass"] is False
    assert any(view["label"] == "Sandbox Exceptions" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/sandbox/exceptions" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/sandbox_exceptions/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/sandbox_exceptions" for item in inventory.items)
    assert any(item["path"] == "/sandbox/exceptions" for item in api_contract.docs_api_coverage)
