from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    CapacityForecastRequest,
    CapacityGuardrails,
    CapacityGuardrailsRequest,
    CapacityPlanExportRequest,
    SkillManifest,
)
from app.services import CapacityPlanningService

HEADERS = {"X-API-Key": "dev-local-token"}


def capacity_service(state, tmp_path: Path) -> CapacityPlanningService:
    return CapacityPlanningService(state, output_dir=tmp_path / "capacity")


def test_capacity_forecast_shape_and_workflow_demand(tmp_path: Path) -> None:
    state = create_state()
    state.capacity = capacity_service(state, tmp_path)

    forecast = asyncio.run(state.capacity.forecast(CapacityForecastRequest(actor="pytest-capacity")))

    assert forecast.readiness_status in {"ready", "needs_review", "blocked"}
    assert forecast.summary["promoted_skill_count"] == 6
    assert forecast.summary["total_forecasted_invocations"] > 0
    assert "search_knowledge_base" in {skill.skill_id for skill in forecast.per_skill}
    assert forecast.top_workflows
    assert forecast.recommended_rate_limits["classify_request"] >= 1
    assert forecast.mcp_tools_affected == sorted(forecast.mcp_tools_affected)
    assert forecast.release_evidence["approved_workflow_template_count"] >= 3
    assert "counts_by_action" in forecast.audit_evidence


def test_capacity_guardrail_defaults_and_validation(tmp_path: Path) -> None:
    state = create_state()
    state.capacity = capacity_service(state, tmp_path)

    defaulted = state.capacity.guardrails(CapacityGuardrailsRequest(write_config=True))
    assert defaulted.status == "defaulted"
    assert defaulted.config_path is not None
    assert Path(defaulted.config_path).exists()
    assert "summarize_document" in defaulted.guardrails.per_skill_quotas

    invalid = state.capacity.guardrails(
        CapacityGuardrailsRequest(
            guardrails=CapacityGuardrails(
                max_invocations_per_minute=0,
                max_tokens_per_day=-1,
                max_latency_p95_ms=0,
                per_skill_quotas={"missing_skill": -2},
                fallback_behavior="queue",
                policy_actions=["teleport"],
            )
        )
    )
    assert invalid.status == "invalid"
    assert any("max_invocations_per_minute" in error for error in invalid.validation_errors)
    assert any("missing_skill" in error for error in invalid.validation_errors)
    assert any("Unknown policy actions" in error for error in invalid.validation_errors)


def test_capacity_risk_flags_with_strict_quota_and_token_budget(tmp_path: Path) -> None:
    state = create_state()
    state.capacity = capacity_service(state, tmp_path)
    state.capacity.default_guardrails = lambda: CapacityGuardrails(
        max_invocations_per_minute=5,
        max_tokens_per_day=10,
        max_latency_p95_ms=200.0,
        per_skill_quotas={skill.id: 1 for skill in state.registry.mcp_exposed()},
        fallback_behavior="deny",
        policy_actions=["throttle", "alert"],
    )

    forecast = asyncio.run(
        state.capacity.forecast(
            CapacityForecastRequest(
                actor="pytest-capacity",
                forecast_days=30,
                traffic_multiplier=5.0,
            )
        )
    )

    assert forecast.readiness_status == "blocked"
    assert "token_budget_exceeds_guardrail" in forecast.bottleneck_risk_flags
    assert any("quota_pressure" in flag for flag in forecast.bottleneck_risk_flags)
    assert any("latency_p95_exceeds_guardrail" in flag for flag in forecast.bottleneck_risk_flags)


def test_capacity_plan_export_writes_json_and_markdown(tmp_path: Path) -> None:
    state = create_state()
    state.capacity = capacity_service(state, tmp_path)

    export = asyncio.run(
        state.capacity.plan_export(CapacityPlanExportRequest(actor="pytest-capacity"))
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["plan_id"] == "capacity_plan_latest"
    assert len(bundle["interviewer_talking_points"]) == 5
    assert "jd_skills_demonstrated" in bundle
    assert "python -m app.demo" in bundle["local_verification_commands"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Capacity Plan" in markdown
    assert "Capacity readiness" in markdown
    assert "MCP Tools Affected" in markdown


def test_capacity_endpoints_return_forecast_guardrails_and_export(tmp_path: Path) -> None:
    main_module.state = create_state()
    main_module.state.capacity = capacity_service(main_module.state, tmp_path)
    client = TestClient(app)

    forecast = client.post("/capacity/forecast", headers=HEADERS, json={"forecast_days": 14})
    guardrails = client.post("/capacity/guardrails", headers=HEADERS, json={"write_config": True})
    export = client.post("/capacity/plan-export", headers=HEADERS)

    assert forecast.status_code == 200
    assert forecast.json()["summary"]["forecast_days"] == 14
    assert forecast.json()["per_skill"]
    assert guardrails.status_code == 200
    assert guardrails.json()["status"] == "defaulted"
    assert Path(guardrails.json()["config_path"]).exists()
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()


def test_capacity_excludes_disabled_and_draft_skills(tmp_path: Path) -> None:
    state = create_state()
    state.registry.set_status("translate_text", False, "pytest")
    draft = SkillManifest(
        id="draft_capacity_candidate",
        name="Draft Capacity Candidate",
        version="1.0.0",
        description="Draft skill that should not affect capacity planning.",
        provider="mock",
        enabled=True,
        status="draft",
        tags=["capacity"],
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )
    state.registry.register(draft, "pytest")
    state.capacity = capacity_service(state, tmp_path)

    forecast = asyncio.run(state.capacity.forecast(CapacityForecastRequest(actor="pytest-capacity")))

    skill_ids = {skill.skill_id for skill in forecast.per_skill}
    assert "translate_text" not in skill_ids
    assert "draft_capacity_candidate" not in skill_ids
    assert "translate_text" in {skill["id"] for skill in forecast.excluded_skills["disabled"]}
    assert "draft_capacity_candidate" in {skill["id"] for skill in forecast.excluded_skills["draft"]}
