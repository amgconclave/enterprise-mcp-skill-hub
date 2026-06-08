import pytest

from app.bootstrap import create_state


@pytest.mark.asyncio
async def test_builtin_skill_invocation_records_metrics_and_audit() -> None:
    state = create_state()

    invocation = await state.invocation_service.invoke(
        "classify_request",
        {"request": "Security outage is blocking the RFP."},
        "pytest",
    )

    assert invocation.status == "succeeded"
    assert invocation.output is not None
    assert invocation.output["category"] == "incident"
    assert invocation.trace_id
    assert state.metrics.summary().invocation_count == 1
    assert any(event.trace_id == invocation.trace_id for event in state.audit.events)


@pytest.mark.asyncio
async def test_disabled_skill_is_excluded_and_not_invokable() -> None:
    state = create_state()
    state.registry.set_status("translate_text", False, "pytest")

    tool_names = [tool.name for tool in state.mcp.list_tools()]
    invocation = await state.invocation_service.invoke(
        "translate_text",
        {"text": "Hello", "target_language": "German"},
        "pytest",
    )

    assert "translate_text" not in tool_names
    assert invocation.status == "failed"
    assert invocation.error == "Skill is disabled."


def test_resources_and_prompts_are_discoverable() -> None:
    state = create_state()

    resources = state.mcp.list_resources()
    prompts = state.mcp.list_prompts()
    catalog = state.mcp.read_resource("resource://skill-catalog")

    assert any(resource.uri == "resource://policy/ai-governance" for resource in resources)
    assert any(prompt.id == "support_reply" for prompt in prompts)
    assert "summarize_document" in catalog.content


@pytest.mark.asyncio
async def test_agent_selects_multiple_skills_for_compound_task() -> None:
    state = create_state()

    run = await state.agent.run(
        "Summarize the RFP policy context and create action items for Priya Shah.",
        "pytest",
    )

    assert len(run.selected_skills) >= 2
    assert "classify_request" in run.selected_skills
    assert "generate_action_items" in run.selected_skills
