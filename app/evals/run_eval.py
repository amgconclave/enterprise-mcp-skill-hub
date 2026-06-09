from __future__ import annotations

import argparse
import asyncio
import json
import time

from app.bootstrap import BUILTIN_MANIFESTS, create_state
from app.evals.golden import GoldenEvalRunner
from app.models import SkillManifest, TenantPolicySimulationRequest, TenantSandboxExportRequest


async def run(validate_only: bool = False) -> dict:
    state = create_state()
    checked = len(BUILTIN_MANIFESTS) + 2
    valid = sum(
        1 for manifest in BUILTIN_MANIFESTS if state.validator.validate_manifest(manifest.model_dump(mode="json")).valid
    )
    invalid_result = state.validator.validate_manifest(
        {"id": "bad skill", "name": "Bad", "version": "1", "description": "bad", "input_schema": {}, "output_schema": {}}
    )
    disabled = state.registry.set_status("translate_text", False, "eval")
    enabled_tool_names = [tool.name for tool in state.mcp.list_tools()]
    disabled_excluded = disabled.id not in enabled_tool_names
    state.registry.set_status("translate_text", True, "eval")
    draft_manifest = SkillManifest(
        id="draft_support_summary",
        name="Draft Support Summary",
        version="1.0.0",
        description="Draft manifest used to validate promotion governance.",
        provider="mock",
        enabled=True,
        tags=["support", "governance"],
        input_schema={
            "type": "object",
            "properties": {"ticket": {"type": "string"}},
            "required": ["ticket"],
        },
        output_schema={
            "type": "object",
            "properties": {"draft": {"type": "string"}, "confidence": {"type": "number"}},
            "required": ["draft", "confidence"],
        },
    )
    draft_validation = state.validator.validate_manifest(draft_manifest.model_dump(mode="json"))
    state.registry.register(draft_manifest, "eval")
    draft_excluded = draft_manifest.id not in {tool.name for tool in state.mcp.list_tools()}
    draft_mcp_call = await state.mcp.call_tool(
        draft_manifest.id,
        {"ticket": "Customer needs a governed support reply."},
        "eval",
    )
    promoted = state.registry.promote(draft_manifest.id, "eval")
    promoted_included = promoted.id in {tool.name for tool in state.mcp.list_tools()}
    promotion_audited = any(
        event.action == "skill.promoted" and event.resource_id == draft_manifest.id
        for event in state.audit.events
    )

    success_count = 0
    started = time.perf_counter()
    if not validate_only:
        samples = {
            "summarize_document": {"text": "Atlas Labs wants a governed AI skill layer. It needs audit logs."},
            "extract_entities": {"text": "Priya Shah at Atlas Labs raised a risk for MCP on 2026-06-15."},
            "translate_text": {"text": "Hello enterprise agent.", "target_language": "Spanish"},
            "classify_request": {"request": "Security outage is blocking the RFP response."},
            "generate_action_items": {"text": "Action: Priya to follow up by 2026-06-15."},
            "search_knowledge_base": {"query": "AI governance policy", "limit": 2},
        }
        for skill_id, payload in samples.items():
            invocation = await state.invocation_service.invoke(skill_id, payload, "eval")
            success_count += invocation.status == "succeeded"
        agent_run = await state.agent.run("Summarize the RFP policy context and create action items.")
    else:
        agent_run = await state.agent.run("Summarize the RFP policy context and create action items.")
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    summary = state.metrics.summary()
    governance_report = state.governance.generate()
    golden_result = await GoldenEvalRunner(state).run()
    capacity_forecast = await state.capacity.forecast()
    capacity_guardrails = state.capacity.guardrails()
    capacity_export = await state.capacity.plan_export()
    tenant_simulation = state.tenant_sandbox.simulate(
        TenantPolicySimulationRequest(
            tenant="healthcare",
            role="reviewer",
            environment="production",
            data_sensitivity="confidential",
        )
    )
    tenant_export = state.tenant_sandbox.export(
        TenantSandboxExportRequest(actor="eval-tenant-policy-reviewer")
    )
    passed = (
        valid == len(BUILTIN_MANIFESTS)
        and not invalid_result.valid
        and len(enabled_tool_names) == len(BUILTIN_MANIFESTS) - 1
        and disabled_excluded
        and draft_validation.valid
        and draft_excluded
        and draft_mcp_call["status"] == "failed"
        and promoted_included
        and promotion_audited
        and governance_report.status == "pass"
        and golden_result.failed_cases == 0
        and capacity_forecast.per_skill
        and capacity_guardrails.status == "defaulted"
        and capacity_export.readiness_status in {"ready", "needs_review", "blocked"}
        and tenant_simulation.impacted_mcp_tools
        and tenant_export.readiness_status in {"ready", "needs_review", "blocked"}
        and len(agent_run.selected_skills) >= 2
        and (validate_only or success_count == len(BUILTIN_MANIFESTS))
    )
    return {
        "manifests_checked": checked,
        "valid_manifest_count": valid,
        "invalid_manifest_rejection_count": 0 if invalid_result.valid else 1,
        "enabled_mcp_tool_count": len(enabled_tool_names),
        "disabled_skill_exclusion_result": disabled_excluded,
        "draft_manifest_validation_result": draft_validation.valid,
        "draft_skill_exclusion_result": draft_excluded and draft_mcp_call["status"] == "failed",
        "promotion_inclusion_result": promoted_included,
        "promotion_audit_event_result": promotion_audited,
        "governance_report_status": governance_report.status,
        "governance_report_skill_count": len(governance_report.skills),
        "golden_eval_score": golden_result.score,
        "golden_eval_passed_cases": golden_result.passed_cases,
        "golden_eval_failed_cases": golden_result.failed_cases,
        "capacity_forecast_readiness": capacity_forecast.readiness_status,
        "capacity_forecast_skill_count": len(capacity_forecast.per_skill),
        "capacity_guardrails_status": capacity_guardrails.status,
        "capacity_plan_json_path": capacity_export.json_path,
        "tenant_sandbox_readiness": tenant_export.readiness_status,
        "tenant_sandbox_json_path": tenant_export.json_path,
        "tenant_sandbox_impacted_tool_count": len(tenant_simulation.impacted_mcp_tools),
        "built_in_skill_invocation_success_count": success_count,
        "demo_agent_selected_skill_count": len(agent_run.selected_skills),
        "average_invocation_latency": summary.average_latency_ms or elapsed_ms,
        "token_usage": {"input": summary.input_tokens, "output": summary.output_tokens},
        "estimated_cost": summary.estimated_cost,
        "summary": "PASS" if passed else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.validate_only)), indent=2))


if __name__ == "__main__":
    main()
