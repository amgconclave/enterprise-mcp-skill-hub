from __future__ import annotations

import argparse
import asyncio
import json

from app.bootstrap import create_state
from app.models import PolicyInvocationContext


async def main() -> None:
    parser = argparse.ArgumentParser(description="MCP-compatible local inspector for the skill hub.")
    parser.add_argument("command", choices=["tools", "resources", "prompts", "call"])
    parser.add_argument("--name", help="Tool name for call.")
    parser.add_argument("--arguments", default="{}", help="JSON arguments for call.")
    parser.add_argument("--role", choices=["admin", "reviewer", "agent", "viewer"], help="Policy role for call.")
    parser.add_argument("--environment", default="local", help="Policy environment for call.")
    parser.add_argument(
        "--data-sensitivity",
        choices=["public", "internal", "confidential"],
        default="internal",
        help="Policy data sensitivity for call.",
    )
    parser.add_argument("--enforce-policy", action="store_true", help="Enforce local policy before calling a tool.")
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
        policy_context = None
        if args.enforce_policy or args.role:
            policy_context = PolicyInvocationContext(
                role=args.role or "agent",
                environment=args.environment,
                data_sensitivity=args.data_sensitivity,
                requested_action="invoke",
                enforce=args.enforce_policy,
            )
        payload = await state.mcp.call_tool(
            args.name,
            json.loads(args.arguments),
            "cli-mcp-client",
            policy_context,
        )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
