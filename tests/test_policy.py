from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import PolicyInvocationContext, PolicySimulationRequest

API_KEY = "dev-local-token"


@pytest.fixture()
def client() -> TestClient:
    main_module.state = create_state()
    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", "allow"),
        ("reviewer", "allow"),
        ("agent", "deny"),
        ("viewer", "deny"),
    ],
)
def test_policy_simulator_confidential_access_matrix(role: str, expected: str) -> None:
    state = create_state()

    result = state.policy.simulate(
        state.registry.get("search_knowledge_base"),
        PolicySimulationRequest(
            skill_id="search_knowledge_base",
            role=role,
            environment="local",
            data_sensitivity="confidential",
            requested_action="invoke",
        ),
    )

    assert result.decision == expected
    assert result.matched_rules
    if expected == "deny":
        assert "confidential-requires-admin-or-reviewer" in result.matched_rules


def test_policy_simulator_endpoint(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/policy/simulate",
        headers=auth_headers,
        json={
            "skill_id": "search_knowledge_base",
            "role": "reviewer",
            "environment": "local",
            "data_sensitivity": "confidential",
            "requested_action": "invoke",
        },
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "allow"
    assert "privileged-confidential-access" in response.json()["matched_rules"]


def test_enforced_fastapi_invocation_denies_agent_confidential_and_audits(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/skills/search_knowledge_base/invoke",
        headers={
            **auth_headers,
            "X-Policy-Enforce": "true",
            "X-Policy-Role": "agent",
            "X-Data-Sensitivity": "confidential",
            "X-Policy-Environment": "local",
        },
        json={"input": {"query": "confidential AI governance policy", "limit": 2}, "actor": "pytest-agent"},
    )

    assert response.status_code == 403
    assert "Policy denied" in response.json()["detail"]

    audit = client.get("/audit/events", headers=auth_headers).json()
    denied_events = [event for event in audit if event["action"] == "policy.denied"]
    assert denied_events
    assert denied_events[-1]["metadata"]["policy_decision"]["decision"] == "deny"


@pytest.mark.parametrize("role", ["admin", "reviewer"])
def test_enforced_fastapi_invocation_allows_privileged_confidential_roles(
    client: TestClient,
    auth_headers: dict[str, str],
    role: str,
) -> None:
    response = client.post(
        "/skills/search_knowledge_base/invoke",
        headers=auth_headers,
        json={
            "input": {"query": "confidential AI governance policy", "limit": 2},
            "actor": f"pytest-{role}",
            "policy_context": {
                "role": role,
                "environment": "local",
                "data_sensitivity": "confidential",
                "requested_action": "invoke",
                "enforce": True,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"


@pytest.mark.asyncio
async def test_enforced_mcp_call_denies_viewer_confidential_and_allows_admin() -> None:
    state = create_state()

    denied = await state.mcp.call_tool(
        "search_knowledge_base",
        {"query": "confidential AI governance policy", "limit": 2},
        "pytest-viewer",
        PolicyInvocationContext(
            role="viewer",
            environment="local",
            data_sensitivity="confidential",
            requested_action="invoke",
            enforce=True,
        ),
    )
    allowed = await state.mcp.call_tool(
        "search_knowledge_base",
        {"query": "confidential AI governance policy", "limit": 2},
        "pytest-admin",
        PolicyInvocationContext(
            role="admin",
            environment="local",
            data_sensitivity="confidential",
            requested_action="invoke",
            enforce=True,
        ),
    )

    assert denied["status"] == "failed"
    assert "Policy denied" in denied["error"]
    assert allowed["status"] == "succeeded"
    assert any(event.action == "policy.denied" for event in state.audit.events)


def test_governance_report_includes_policy_access_summary() -> None:
    state = create_state()

    report = state.governance.generate()
    record = next(skill for skill in report.skills if skill.skill_id == "search_knowledge_base")

    assert record.policy_access["admin"] == ["public", "internal", "confidential"]
    assert record.policy_access["reviewer"] == ["public", "internal", "confidential"]
    assert record.policy_access["agent"] == ["public", "internal"]
    assert record.policy_access["viewer"] == ["public"]
    assert "policy_agent_confidential_restricted" in record.risk_flags
    assert any(check.name == "Policy access control" for check in report.checks)
