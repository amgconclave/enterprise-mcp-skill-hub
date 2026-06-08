from __future__ import annotations

import argparse
import asyncio
import json

from app.bootstrap import create_state


async def main() -> None:
    parser = argparse.ArgumentParser(description="MCP-compatible local inspector for the skill hub.")
    parser.add_argument("command", choices=["tools", "resources", "prompts", "call"])
    parser.add_argument("--name", help="Tool name for call.")
    parser.add_argument("--arguments", default="{}", help="JSON arguments for call.")
    args = parser.parse_args()

    state = create_state()
    if args.command == "tools":
        payload = [tool.model_dump(mode="json") for tool in state.mcp.list_tools()]
    elif args.command == "resources":
        payload = [resource.model_dump(mode="json") for resource in state.mcp.list_resources()]
    elif args.command == "prompts":
        payload = [prompt.model_dump(mode="json") for prompt in state.mcp.list_prompts()]
    else:
        if not args.name:
            raise SystemExit("--name is required for call")
        payload = await state.mcp.call_tool(args.name, json.loads(args.arguments), "cli-mcp-client")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
