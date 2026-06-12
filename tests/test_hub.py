from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import BUILTIN_MANIFESTS, create_state
from app.main import app

API_KEY = "dev-local-token"


@pytest.fixture()
def client() -> TestClient:
    main_module.state = create_state()
    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def test_health_and_auth(client: TestClient, auth_headers: dict[str, str]) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["provider_mode"] == "mock"
    assert "X-Trace-ID" in health.headers

    assert client.get("/skills").status_code == 401
    token = client.post("/auth/demo-token").json()
    assert token == {"token": API_KEY, "header": "X-API-Key"}

    skills = client.get("/skills", headers=auth_headers)
    assert skills.status_code == 200
    assert len(skills.json()) == len(BUILTIN_MANIFESTS)


def test_manifest_validation_registration_and_custom_invocation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    invalid = {
        "manifest": {
            "id": "bad skill",
            "name": "Bad",
            "version": "1.0.0",
            "description": "Invalid id and schemas",
            "input_schema": {"type": "object", "properties": {"text": {"type": "unknown"}}},
            "output_schema": {"type": "object", "properties": {}},
        }
    }
    validation = client.post("/skills/validate", json=invalid, headers=auth_headers)
    assert validation.status_code == 200
    assert validation.json()["valid"] is False

    custom_manifest = {
        "id": "draft_support_summary",
        "name": "Draft Support Summary",
        "version": "1.0.0",
        "description": "Mock manifest-backed skill for governed support summaries.",
        "provider": "mock",
        "enabled": True,
        "status": "draft",
        "tags": ["support", "custom"],
        "input_schema": {
            "type": "object",
            "properties": {"ticket": {"type": "string"}},
            "required": ["ticket"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"draft": {"type": "string"}, "confidence": {"type": "number"}},
            "required": ["draft", "confidence"],
        },
    }
    registered = client.post(
        "/skills/register", json={"manifest": custom_manifest}, headers=auth_headers
    )
    assert registered.status_code == 200
    assert registered.json()["id"] == "draft_support_summary"
    assert registered.json()["status"] == "draft"

    tools = client.get("/mcp/tools", headers=auth_headers).json()
    assert "draft_support_summary" not in {tool["name"] for tool in tools}

    blocked_mcp_call = client.post(
        "/mcp/tools/draft_support_summary/call",
        json={"input": {"ticket": "Customer needs a governed support reply."}},
        headers=auth_headers,
    )
    assert blocked_mcp_call.status_code == 200
    assert blocked_mcp_call.json()["status"] == "failed"

    blocked_promotion = client.post(
        "/skills/draft_support_summary/promote",
        json={"actor": "test-admin"},
        headers=auth_headers,
    )
    assert blocked_promotion.status_code == 422
    assert "marketplace_approval_record" in blocked_promotion.json()["detail"]["failed_check_ids"]

    approval = client.post(
        "/marketplace/approvals/submit",
        json={
            "skill_id": "draft_support_summary",
            "tenant_scenario_id": "internal_ops_local",
            "actor": "test-admin",
            "owner": "test-owner",
        },
        headers=auth_headers,
    )
    assert approval.status_code == 200
    decision = client.post(
        f"/marketplace/approvals/{approval.json()['approval_id']}/decision",
        json={"actor": "test-owner", "decision": "approve", "owner_signoff": True},
        headers=auth_headers,
    )
    assert decision.status_code == 200
    gate = client.get(
        "/marketplace/promotion-gate/draft_support_summary",
        headers=auth_headers,
    )
    assert gate.status_code == 200
    assert gate.json()["can_promote"] is True

    promoted = client.post(
        "/skills/draft_support_summary/promote",
        json={"actor": "test-admin"},
        headers=auth_headers,
    )
    assert promoted.status_code == 200
    assert promoted.json()["status"] == "promoted"
    assert promoted.json()["enabled"] is True

    tools = client.get("/mcp/tools", headers=auth_headers).json()
    assert "draft_support_summary" in {tool["name"] for tool in tools}

    invocation = client.post(
        "/mcp/tools/draft_support_summary/call",
        json={"input": {"ticket": "Customer needs a governed support reply."}},
        headers=auth_headers,
    )
    assert invocation.status_code == 200
    assert invocation.json()["status"] == "succeeded"
    assert invocation.json()["result"]["draft"]

    audit = client.get("/audit/events", headers=auth_headers).json()
    assert any(event["action"] == "skill.promoted" for event in audit)


@pytest.mark.parametrize(
    ("skill_id", "payload", "required_key"),
    [
        ("summarize_document", {"text": "Atlas Labs needs audit logs. Governance matters."}, "summary"),
        ("extract_entities", {"text": "Priya Shah from Atlas Labs flagged MCP risk."}, "people"),
        ("translate_text", {"text": "Hello agent.", "target_language": "Spanish"}, "translated_text"),
        ("classify_request", {"request": "Security outage is blocking an RFP."}, "category"),
        ("generate_action_items", {"text": "Action: Priya to follow up by 2026-06-15."}, "action_items"),
        ("search_knowledge_base", {"query": "AI governance policy", "limit": 2}, "results"),
    ],
)
def test_each_builtin_skill_invokes_in_mock_mode(
    client: TestClient,
    auth_headers: dict[str, str],
    skill_id: str,
    payload: dict,
    required_key: str,
) -> None:
    response = client.post(
        f"/skills/{skill_id}/invoke", json={"input": payload}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert required_key in body["output"]
    assert body["trace_id"].startswith("trc_")


def test_disabled_skill_not_listed_or_invokable(client: TestClient, auth_headers: dict[str, str]) -> None:
    disabled = client.patch(
        "/skills/translate_text/status",
        json={"enabled": False, "actor": "test-admin"},
        headers=auth_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    tools = client.get("/mcp/tools", headers=auth_headers).json()
    assert "translate_text" not in {tool["name"] for tool in tools}

    invocation = client.post(
        "/skills/translate_text/invoke",
        json={"input": {"text": "Hello", "target_language": "French"}},
        headers=auth_headers,
    )
    assert invocation.status_code == 422
    assert "disabled" in invocation.json()["detail"].lower()

    mcp_call = client.post(
        "/mcp/tools/translate_text/call",
        json={"input": {"text": "Hello", "target_language": "French"}},
        headers=auth_headers,
    )
    assert mcp_call.status_code == 200
    assert mcp_call.json()["status"] == "failed"


def test_mcp_resources_prompts_and_skill_catalog(client: TestClient, auth_headers: dict[str, str]) -> None:
    resources = client.get("/mcp/resources", headers=auth_headers)
    assert resources.status_code == 200
    resource_uris = {resource["uri"] for resource in resources.json()}
    assert {
        "resource://policy/ai-governance",
        "resource://product/skill-hub",
        "resource://skill-catalog",
    }.issubset(resource_uris)

    resource = client.get(
        "/mcp/resources/read",
        params={"uri": "resource://policy/ai-governance"},
        headers=auth_headers,
    )
    assert resource.status_code == 200
    assert "Approved skills" in resource.json()["content"]

    prompts = client.get("/mcp/prompts", headers=auth_headers)
    assert prompts.status_code == 200
    prompt_ids = {prompt["id"] for prompt in prompts.json()}
    assert {"support_reply", "rfp_answer", "meeting_summary", "workflow_composition"} == prompt_ids


def test_demo_agent_selects_multiple_governed_skills_and_records_metrics(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/agents/run",
        json={
            "prompt": (
                "Summarize this RFP meeting, search approved AI governance policy, "
                "and create action items for Priya Shah from Atlas Labs."
            )
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    run = response.json()
    assert len(run["selected_skills"]) >= 2
    assert "classify_request" in run["selected_skills"]
    assert "search_knowledge_base" in run["selected_skills"]

    metrics = client.get("/metrics/usage", headers=auth_headers).json()
    assert metrics["invocation_count"] >= 2
    assert metrics["input_tokens"] > 0
    assert metrics["by_skill"]["classify_request"] >= 1

    audit = client.get("/audit/events", headers=auth_headers).json()
    assert any(event["action"] == "skill.invoked" for event in audit)

    history = client.get("/invocations", headers=auth_headers).json()
    assert len(history) >= 2
