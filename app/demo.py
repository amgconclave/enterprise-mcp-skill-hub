from __future__ import annotations

import asyncio
import json

from app.bootstrap import create_state


async def main() -> None:
    state = create_state()
    prompt = (
        "Summarize this support meeting, classify the request, search approved policy context, "
        "and create action items. Priya Shah from Atlas Labs needs a security review by 2026-06-15."
    )
    result = await state.agent.run(prompt)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
