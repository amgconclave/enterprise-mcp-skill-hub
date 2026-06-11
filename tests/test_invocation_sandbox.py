from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    InvocationSandboxEvaluateRequest,
    PolicyInvocationContext,
)

HEADERS = {"X-API-Key": "dev-local-token"}


def sandbox_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.invocation_sandbox.output_dir = tmp_path / "sandbox_policies"
    return state


def test_sandbox_allows_normal_mock_skill_and_labels_retrieval_risk() -> None:
    state = sandbox_state()

    decision = state.invocation_sandbox.evaluate(
        InvocationSandboxEvaluateRequest(
            skill_id="search_knowledge_base",
            input={"query": "AI governance policy", "limit": 2},
            actor="pytest-sandbox",
            action_class="skill_invocation",
            endpoint="mcp:tool/search_knowledge_base",
            enforce=True,
        )
    )

    assert decision.decision == "allow"
    assert decision.risk_label == "medium"
    assert "mock_tool_sandbox_enforced" in decision.matched_rules
    assert "retrieval_tool_context_boundary" in decision.matched_rules
    assert any(event.action == "sandbox.evaluated" for event in state.audit.events)


def test_sandbox_blocks_action_classes_and_payload_limit() -> None:
    state = sandbox_state()

    action_decision = state.invocation_sandbox.evaluate(
        InvocationSandboxEvaluateRequest(
            skill_id="extract_entities",
            input={"text": "write a file"},
            action_class="filesystem_write",
        )
    )
    oversized_decision = state.invocation_sandbox.evaluate(
        InvocationSandboxEvaluateRequest(
            skill_id="summarize_document",
            input={"text": "local " * 1200},
            action_class="skill_invocation",
        )
    )

    assert action_decision.decision == "deny"
    assert action_decision.risk_label == "critical"
    assert "action_class_blocked" in action_decision.matched_rules
    assert oversized_decision.decision == "deny"
    assert "payload_bytes_exceeded" in oversized_decision.matched_rules


def test_enforced_sandbox_blocks_invocation_before_execution() -> None:
    state = sandbox_state()

    invocation = asyncio.run(
        state.invocation_service.invoke(
            "extract_entities",
            {"text": "try to write a local file"},
            "pytest-sandbox",
            PolicyInvocationContext(
                enforce_sandbox=True,
                action_class="filesystem_write",
                endpoint="mcp:tool/extract_entities",
            ),
        )
    )

    assert invocation.status == "failed"
    assert invocation.error
    assert invocation.error.startswith("Sandbox denied")
    assert invocation.output is None
    assert invocation.sandbox_decision is not None
    assert any(event.action == "sandbox.denied" for event in state.audit.events)


def test_sandbox_endpoints_pack_dashboard_inventory_and_contract(tmp_path: Path) -> None:
    state = sandbox_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report_response = client.get("/sandbox/policy", headers=HEADERS)
    evaluate_response = client.post(
        "/sandbox/evaluate",
        headers=HEADERS,
        json={
            "skill_id": "extract_entities",
            "input": {"text": "try to spawn a process"},
            "action_class": "process_spawn",
            "endpoint": "fastapi:/skills/extract_entities/invoke",
            "enforce": True,
        },
    )
    invoke_response = client.post(
        "/skills/extract_entities/invoke",
        headers={
            **HEADERS,
            "X-Sandbox-Enforce": "true",
            "X-Action-Class": "filesystem_write",
            "X-Sandbox-Endpoint": "fastapi:/skills/extract_entities/invoke",
        },
        json={"input": {"text": "try to write files"}},
    )
    pack_response = client.post(
        "/sandbox/policy-pack",
        headers=HEADERS,
        json={"actor": "pytest-sandbox-reviewer"},
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report_response.status_code == 200
    assert report_response.json()["limits"]["max_payload_bytes"] == 4096
    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["decision"] == "deny"
    assert invoke_response.status_code == 403
    assert "Sandbox denied" in invoke_response.json()["detail"]
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    bundle = json.loads(Path(pack_response.json()["json_path"]).read_text(encoding="utf-8"))
    assert "policy_report" in bundle
    assert bundle["blocked_action_classes"]
    assert any(view["label"] == "Invocation Sandbox" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/sandbox/policy" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/sandbox_policies/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/sandbox_policies" for item in inventory.items)
    assert any(item["path"] == "/sandbox/policy" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /sandbox/policy-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
