from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    PolicyInvocationContext,
    TenantEntitlementMatrixRequest,
    TenantEntitlementPackRequest,
)

API_KEY = "dev-local-token"


@pytest.fixture()
def client() -> TestClient:
    main_module.state = create_state()
    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def test_entitlement_matrix_returns_allowed_and_denied_mcp_safe_tools() -> None:
    state = create_state()

    matrix = state.entitlements.matrix(
        TenantEntitlementMatrixRequest(
            tenant_id="healthcare",
            user_id="care-agent",
            role="agent",
            user_scopes=["skill.invoke", "tenant.healthcare"],
        )
    )

    assert matrix.summary["allowed_skill_count"] >= 1
    assert matrix.summary["denied_skill_count"] >= 1
    assert "search_knowledge_base" in matrix.mcp_safe_tool_names
    assert "translate_text" in matrix.denied_skill_ids
    assert all(decision.tenant_id == "healthcare" for decision in matrix.decisions)


def test_healthcare_agent_denied_translation_by_entitlement() -> None:
    state = create_state()

    decision = state.entitlements.decide(
        state.registry.get("translate_text"),
        PolicyInvocationContext(
            role="agent",
            tenant_id="healthcare",
            user_id="care-agent",
            user_scopes=["skill.invoke", "tenant.healthcare"],
            enforce_entitlements=True,
        ),
    )

    assert decision.decision == "deny"
    assert "healthcare:translate_text" in decision.matched_policies
    assert any("explicitly denied" in reason for reason in decision.reasons)


def test_enforced_fastapi_entitlement_denial_records_audit(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/skills/translate_text/invoke",
        headers={
            **auth_headers,
            "X-Entitlement-Enforce": "true",
            "X-Tenant-ID": "healthcare",
            "X-User-ID": "care-agent",
            "X-User-Scopes": "skill.invoke,tenant.healthcare",
            "X-Policy-Role": "agent",
        },
        json={
            "input": {"text": "Patient follow-up note", "target_language": "Spanish"},
            "actor": "care-agent",
        },
    )

    assert response.status_code == 403
    assert "Entitlement denied" in response.json()["detail"]

    audit = client.get("/audit/events", headers=auth_headers).json()
    denied_events = [event for event in audit if event["action"] == "entitlement.denied"]
    assert denied_events
    assert denied_events[-1]["metadata"]["entitlement_decision"]["decision"] == "deny"


def test_entitlement_api_evaluate_and_pack_export(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    evaluate = client.post(
        "/tenants/entitlements/evaluate",
        headers=auth_headers,
        json={
            "tenant_id": "healthcare",
            "user_id": "care-agent",
            "role": "agent",
            "environment": "local",
            "data_sensitivity": "internal",
            "user_scopes": ["skill.invoke", "tenant.healthcare"],
            "skill_ids": ["search_knowledge_base", "translate_text"],
        },
    )
    pack = client.post(
        "/tenants/entitlements/pack",
        headers=auth_headers,
        json={"actor": "pytest-entitlement-reviewer"},
    )

    assert evaluate.status_code == 200
    body = evaluate.json()
    assert body["summary"]["allowed_skill_count"] == 1
    assert body["summary"]["denied_skill_count"] == 1
    assert body["mcp_safe_tool_names"] == ["search_knowledge_base"]
    assert pack.status_code == 200
    assert pack.json()["summary"]["denied_skill_count"] >= 1


@pytest.mark.asyncio
async def test_mcp_call_enforces_entitlement_before_tool_execution() -> None:
    state = create_state()

    result = await state.mcp.call_tool(
        "translate_text",
        {"text": "Patient follow-up note", "target_language": "Spanish"},
        "care-agent",
        PolicyInvocationContext(
            role="agent",
            tenant_id="healthcare",
            user_id="care-agent",
            user_scopes=["skill.invoke", "tenant.healthcare"],
            enforce_entitlements=True,
        ),
    )

    assert result["status"] == "failed"
    assert "Entitlement denied" in result["error"]
    assert any(event.action == "entitlement.denied" for event in state.audit.events)


@pytest.mark.asyncio
async def test_entitlement_pack_export_writes_local_artifacts(tmp_path) -> None:
    state = create_state()
    state.entitlements.output_dir = tmp_path

    export = await state.entitlements.export_pack(
        TenantEntitlementPackRequest(actor="pytest-entitlement-reviewer")
    )

    assert export.readiness_status == "ready"
    assert (tmp_path / "tenant_entitlement_pack_latest.json").exists()
    assert (tmp_path / "tenant_entitlement_pack_latest.md").exists()
