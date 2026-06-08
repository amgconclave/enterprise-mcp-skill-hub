from __future__ import annotations

import argparse
import asyncio
import json
import time

from app.bootstrap import BUILTIN_MANIFESTS, create_state


async def run(validate_only: bool = False) -> dict:
    state = create_state()
    checked = len(BUILTIN_MANIFESTS) + 1
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
    passed = (
        valid == len(BUILTIN_MANIFESTS)
        and not invalid_result.valid
        and len(enabled_tool_names) == len(BUILTIN_MANIFESTS) - 1
        and disabled_excluded
        and len(agent_run.selected_skills) >= 2
        and (validate_only or success_count == len(BUILTIN_MANIFESTS))
    )
    return {
        "manifests_checked": checked,
        "valid_manifest_count": valid,
        "invalid_manifest_rejection_count": 0 if invalid_result.valid else 1,
        "enabled_mcp_tool_count": len(enabled_tool_names),
        "disabled_skill_exclusion_result": disabled_excluded,
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
