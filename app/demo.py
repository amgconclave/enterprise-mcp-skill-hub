from __future__ import annotations

import asyncio
import json

from app.bootstrap import create_state
from app.models import PolicySimulationRequest


async def main() -> None:
    state = create_state()
    prompt = (
        "Summarize this support meeting, classify the request, search approved policy context, "
        "and create action items. Priya Shah from Atlas Labs needs a security review by 2026-06-15."
    )
    result = await state.agent.run(prompt)
    allowed = state.policy.simulate(
        state.registry.get("search_knowledge_base"),
        PolicySimulationRequest(
            skill_id="search_knowledge_base",
            role="reviewer",
            environment="local",
            data_sensitivity="confidential",
            requested_action="invoke",
        ),
    )
    denied = state.policy.simulate(
        state.registry.get("search_knowledge_base"),
        PolicySimulationRequest(
            skill_id="search_knowledge_base",
            role="agent",
            environment="local",
            data_sensitivity="confidential",
            requested_action="invoke",
        ),
    )
    print(
        json.dumps(
            {
                "agent_run": result.model_dump(mode="json"),
                "policy_simulations": {
                    "allowed_reviewer_confidential": allowed.model_dump(mode="json"),
                    "denied_agent_confidential": denied.model_dump(mode="json"),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
