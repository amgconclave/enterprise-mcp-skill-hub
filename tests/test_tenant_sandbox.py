import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state, schema
from app.main import app
from app.models import SkillManifest, TenantPolicySimulationRequest
from app.services import TenantPolicySandboxService

HEADERS = {"X-API-Key": "dev-local-token"}


def fresh_client(tmp_path: Path | None = None) -> TestClient:
    main_module.state = create_state()
    if tmp_path:
        main_module.state.tenant_sandbox = TenantPolicySandboxService(
            main_module.state,
            output_dir=tmp_path,
        )
    return TestClient(app)


def test_tenant_specific_differences_for_confidential_agent() -> None:
    state = create_state()

    healthcare = state.tenant_sandbox.simulate(
        TenantPolicySimulationRequest(
            tenant="healthcare",
            role="agent",
            environment="local",
            data_sensitivity="confidential",
        )
    )
    internal_demo = state.tenant_sandbox.simulate(
        TenantPolicySimulationRequest(
            tenant="internal_demo",
            role="reviewer",
            environment="local",
            data_sensitivity="confidential",
        )
    )

    healthcare_blocked = {skill.id for skill in healthcare.blocked_skills}
    demo_review = {skill.id for skill in internal_demo.review_required_skills}
    assert "search_knowledge_base" in healthcare_blocked
    assert "search_knowledge_base" in demo_review
    assert "search_knowledge_base" not in {skill.id for skill in internal_demo.blocked_skills}
    assert healthcare.readiness_status == "blocked"
    assert internal_demo.readiness_status == "needs_review"


def test_policy_simulate_endpoint_returns_mcp_impact_and_guardrails() -> None:
    client = fresh_client()

    response = client.post(
        "/tenants/policy-simulate",
        headers=HEADERS,
        json={
            "tenant": "fintech",
            "role": "agent",
            "environment": "production",
            "data_sensitivity": "confidential",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["tenant"] == "fintech"
    assert payload["readiness_status"] in {"blocked", "needs_review"}
    assert "search_knowledge_base" in payload["impacted_mcp_tools"]
    assert "resource://policy/ai-governance" in payload["impacted_mcp_resources"]
    assert payload["recommended_tenant_guardrails"]


def test_blocked_and_review_required_cases_are_separated() -> None:
    state = create_state()

    result = state.tenant_sandbox.simulate(
        TenantPolicySimulationRequest(
            tenant="fintech",
            role="agent",
            environment="production",
            data_sensitivity="confidential",
        )
    )

    blocked = {skill.id for skill in result.blocked_skills}
    review = {skill.id for skill in result.review_required_skills}
    assert "translate_text" in blocked
    assert "search_knowledge_base" in review
    assert blocked.isdisjoint(review)
    assert any(workflow.id == "rfp_answer_pack" for workflow in result.blocked_workflows)


def test_sandbox_export_writes_markdown_and_json(tmp_path: Path) -> None:
    client = fresh_client(tmp_path)

    response = client.post(
        "/tenants/sandbox-export",
        headers=HEADERS,
        json={
            "actor": "pytest-tenant-reviewer",
            "scenarios": [
                {
                    "tenant": "public_sector",
                    "role": "agent",
                    "environment": "production",
                    "data_sensitivity": "internal",
                }
            ],
        },
    )

    assert response.status_code == 200
    export = response.json()
    json_path = Path(export["json_path"])
    markdown_path = Path(export["markdown_path"])
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["tenant_policy_matrix"]
    assert bundle["scenario_results"][0]["scenario"]["tenant"] == "public_sector"
    assert bundle["blocked_review_actions"]
    assert bundle["mcp_impact"]["tools"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Tenant Policy Sandbox" in markdown
    assert "JD Skills Demonstrated" in markdown
    assert "Interviewer Talking Points" in markdown


def test_disabled_and_draft_skills_are_excluded_from_decisions() -> None:
    state = create_state()
    state.registry.set_status("translate_text", False, "pytest")
    state.registry.register(
        SkillManifest(
            id="draft_tenant_skill",
            name="Draft Tenant Skill",
            version="0.1.0",
            description="Draft skill that must stay hidden from tenant sandbox decisions.",
            status="draft",
            input_schema=schema({"text": {"type": "string"}}, ["text"]),
            output_schema=schema({"result": {"type": "string"}}, ["result"]),
        ),
        actor="pytest",
    )

    result = state.tenant_sandbox.simulate(
        TenantPolicySimulationRequest(
            tenant="internal_demo",
            role="admin",
            environment="local",
            data_sensitivity="public",
        )
    )

    decided_ids = {
        item.id
        for item in (
            result.allowed_skills
            + result.blocked_skills
            + result.review_required_skills
        )
    }
    assert "translate_text" not in decided_ids
    assert "draft_tenant_skill" not in decided_ids
    assert "translate_text" in {item["id"] for item in result.excluded_skills["disabled"]}
    assert "draft_tenant_skill" in {item["id"] for item in result.excluded_skills["draft"]}
