from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    PolicyInvocationContext,
    TenantEntitlementAccessReviewPackRequest,
    TenantEntitlementAccessReviewRequest,
    TenantEntitlementChangePackRequest,
    TenantEntitlementChangePreviewRequest,
    TenantEntitlementMatrixRequest,
    TenantEntitlementPackRequest,
    TenantEntitlementReviewPackRequest,
    TenantSkillEntitlementPolicy,
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


def test_entitlement_coverage_flags_wildcard_review_rows() -> None:
    state = create_state()

    coverage = state.entitlements.coverage()

    assert coverage.readiness_status == "needs_review"
    assert coverage.summary["promoted_skill_count"] >= 6
    assert coverage.summary["exact_policy_count"] >= 3
    assert coverage.summary["wildcard_policy_count"] >= 1
    assert coverage.review_required
    assert any(record.coverage_status == "wildcard_policy" for record in coverage.review_required)


def test_entitlement_access_review_flags_privileged_rows_and_safe_break_glass() -> None:
    state = create_state()

    review = state.entitlements.access_review(
        TenantEntitlementAccessReviewRequest(actor="pytest-entitlement-access-reviewer", max_steps=4)
    )

    assert review.review_id == "tenant_entitlement_access_review_latest"
    assert review.readiness_status == "needs_review"
    assert review.summary["privileged_policy_count"] >= 1
    assert review.summary["break_glass_override_count"] == 0
    assert len(review.bounded_steps) == 4
    assert any(row["uses_wildcard_policy"] for row in review.privileged_access_rows)
    assert all(
        scenario["decision"] == "deny"
        for scenario in review.break_glass_drill["scenarios"]
    )
    assert any("state observation" in pattern for pattern in review.patterns_used)
    assert any("bounded action loop" in pattern for pattern in review.patterns_used)
    assert any("step verification" in pattern for pattern in review.patterns_used)


def test_entitlement_change_preview_compares_before_after_without_mutating_policy() -> None:
    state = create_state()
    before_policy_count = len(state.entitlements.policies)

    preview = state.entitlements.preview_change(
        TenantEntitlementChangePreviewRequest(
            actor="pytest-entitlement-change-reviewer",
            proposed_policy=TenantSkillEntitlementPolicy(
                tenant_id="healthcare",
                skill_id="translate_text",
                allowed_roles=["admin", "reviewer", "agent"],
                denied_roles=["viewer"],
                required_scopes=["skill.invoke", "tenant.healthcare", "phi.review"],
                allowed_environments=["local", "dev", "test"],
                allowed_data_sensitivities=["public", "internal"],
                reason="Preview reviewer-scoped healthcare translation access.",
            ),
            scenario=TenantEntitlementMatrixRequest(
                tenant_id="healthcare",
                user_id="care-agent",
                role="agent",
                user_scopes=["skill.invoke", "tenant.healthcare", "phi.review"],
                skill_ids=["translate_text", "search_knowledge_base"],
            ),
        )
    )

    assert preview.readiness_status == "needs_review"
    assert preview.blast_radius["allowed_added"] == ["translate_text"]
    assert preview.before.denied_skill_ids == ["translate_text"]
    assert "translate_text" in preview.after.mcp_safe_tool_names
    assert any(row["change_type"] == "allow_added" for row in preview.changed_decisions)
    assert any(check["id"] == "no_live_policy_mutation" for check in preview.guardrail_checks)
    assert len(state.entitlements.policies) == before_policy_count
    live_decision = state.entitlements.decide(
        state.registry.get("translate_text"),
        PolicyInvocationContext(
            role="agent",
            tenant_id="healthcare",
            user_id="care-agent",
            user_scopes=["skill.invoke", "tenant.healthcare", "phi.review"],
            enforce_entitlements=True,
        ),
    )
    assert live_decision.decision == "deny"


def test_entitlement_change_preview_blocks_broad_production_agent_policy() -> None:
    state = create_state()

    preview = state.entitlements.preview_change(
        TenantEntitlementChangePreviewRequest(
            proposed_policy=TenantSkillEntitlementPolicy(
                tenant_id="fintech",
                skill_id="*",
                allowed_roles=["admin", "reviewer", "agent"],
                denied_roles=["viewer"],
                required_scopes=["skill.invoke", "tenant.fintech"],
                allowed_environments=["local", "production"],
                allowed_data_sensitivities=["public", "internal", "confidential"],
                reason="Unsafe broad production policy for guardrail proof.",
            ),
            scenario=TenantEntitlementMatrixRequest(
                tenant_id="fintech",
                user_id="risk-agent",
                role="agent",
                environment="production",
                user_scopes=["skill.invoke", "tenant.fintech"],
            ),
        )
    )

    assert preview.readiness_status == "blocked"
    assert any(
        check["id"] == "production_agent_block" and check["status"] == "fail"
        for check in preview.guardrail_checks
    )
    assert any("human-in-the-loop" in pattern for pattern in preview.patterns_used)


def test_entitlement_coverage_api_and_review_pack(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    coverage = client.get("/tenants/entitlements/coverage", headers=auth_headers)
    pack = client.post(
        "/tenants/entitlements/review-pack",
        headers=auth_headers,
        json={"actor": "pytest-entitlement-reviewer"},
    )

    assert coverage.status_code == 200
    assert coverage.json()["summary"]["review_required_count"] >= 1
    assert pack.status_code == 200
    assert pack.json()["summary"]["wildcard_policy_count"] >= 1


def test_entitlement_access_review_api_and_pack(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    review = client.get("/tenants/entitlements/access-review", headers=auth_headers)
    pack = client.post(
        "/tenants/entitlements/access-review-pack",
        headers=auth_headers,
        json={"actor": "pytest-entitlement-access-reviewer"},
    )

    assert review.status_code == 200
    assert review.json()["summary"]["break_glass_override_count"] == 0
    assert review.json()["break_glass_drill"]["mcp_safe_default"]
    assert pack.status_code == 200
    assert pack.json()["pack_id"] == "tenant_entitlement_access_review_latest"
    assert pack.json()["summary"]["privileged_policy_count"] >= 1


def test_entitlement_change_preview_api_and_pack(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    payload = {
        "actor": "pytest-entitlement-change-reviewer",
        "proposed_policy": {
            "tenant_id": "healthcare",
            "skill_id": "translate_text",
            "allowed_roles": ["admin", "reviewer", "agent"],
            "denied_roles": ["viewer"],
            "required_scopes": ["skill.invoke", "tenant.healthcare", "phi.review"],
            "allowed_environments": ["local", "dev", "test"],
            "allowed_data_sensitivities": ["public", "internal"],
            "reason": "Preview reviewer-scoped healthcare translation access.",
        },
        "scenario": {
            "tenant_id": "healthcare",
            "user_id": "care-agent",
            "role": "agent",
            "user_scopes": ["skill.invoke", "tenant.healthcare", "phi.review"],
            "skill_ids": ["translate_text"],
        },
    }

    preview = client.post(
        "/tenants/entitlements/change-preview",
        headers=auth_headers,
        json=payload,
    )
    pack = client.post(
        "/tenants/entitlements/change-pack",
        headers=auth_headers,
        json=payload,
    )

    assert preview.status_code == 200
    assert preview.json()["blast_radius"]["allowed_added"] == ["translate_text"]
    assert pack.status_code == 200
    assert pack.json()["pack_id"] == "tenant_entitlement_change_preview_latest"
    assert pack.json()["summary"]["allowed_added_count"] == 1


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
    coverage = state.entitlements.coverage()
    denied_record = next(
        record
        for record in coverage.records
        if record.tenant_id == "healthcare" and record.skill_id == "translate_text"
    )
    assert denied_record.denied_audit_count == 1
    assert coverage.denied_audit_events[0]["skill_id"] == "translate_text"


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


@pytest.mark.asyncio
async def test_entitlement_review_pack_export_writes_local_artifacts(tmp_path) -> None:
    state = create_state()
    state.entitlements.output_dir = tmp_path

    export = await state.entitlements.export_review_pack(
        TenantEntitlementReviewPackRequest(actor="pytest-entitlement-reviewer")
    )

    assert export.readiness_status == "needs_review"
    assert export.summary["review_required_count"] >= 1
    assert (tmp_path / "tenant_entitlement_review_pack_latest.json").exists()
    assert (tmp_path / "tenant_entitlement_review_pack_latest.md").exists()


@pytest.mark.asyncio
async def test_entitlement_access_review_pack_export_writes_local_artifacts(tmp_path) -> None:
    state = create_state()
    state.entitlements.output_dir = tmp_path

    export = await state.entitlements.export_access_review_pack(
        TenantEntitlementAccessReviewPackRequest(actor="pytest-entitlement-access-reviewer")
    )

    assert export.readiness_status == "needs_review"
    assert export.summary["break_glass_override_count"] == 0
    assert (tmp_path / "tenant_entitlement_access_review_latest.json").exists()
    assert (tmp_path / "tenant_entitlement_access_review_latest.md").exists()


@pytest.mark.asyncio
async def test_entitlement_change_pack_export_writes_local_artifacts(tmp_path) -> None:
    state = create_state()
    state.entitlements.output_dir = tmp_path

    export = await state.entitlements.export_change_pack(
        TenantEntitlementChangePackRequest(actor="pytest-entitlement-change-reviewer")
    )

    assert export.readiness_status == "needs_review"
    assert (tmp_path / "tenant_entitlement_change_preview_latest.json").exists()
    assert (tmp_path / "tenant_entitlement_change_preview_latest.md").exists()


def test_entitlement_access_review_is_wired_to_dashboard_and_artifact_inventory() -> None:
    state = create_state()

    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()

    assert any(endpoint["path"] == "/tenants/entitlements/access-review" for endpoint in smoke.endpoint_references)
    assert any(
        endpoint["path"] == "/tenants/entitlements/access-review-pack"
        for endpoint in smoke.endpoint_references
    )
    assert any(
        item.producer_endpoint == "POST /tenants/entitlements/access-review-pack"
        for item in inventory.items
    )
    assert any(
        endpoint["path"] == "/tenants/entitlements/change-preview"
        for endpoint in smoke.endpoint_references
    )
    assert any(
        endpoint["path"] == "/tenants/entitlements/change-pack"
        for endpoint in smoke.endpoint_references
    )
    assert any(
        item.producer_endpoint == "POST /tenants/entitlements/change-pack"
        for item in inventory.items
    )
