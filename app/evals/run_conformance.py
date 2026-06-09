from __future__ import annotations

import asyncio
import json

from app.bootstrap import create_state


async def run() -> dict:
    state = create_state()
    report = await state.conformance.generate()
    payload = report.model_dump(mode="json")
    payload["summary"] = "PASS" if report.status == "pass" else "FAIL"
    return payload


def main() -> None:
    result = asyncio.run(run())
    print(f"Conformance: {result['summary']}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
