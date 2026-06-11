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
    parser.add_argument("--tenant-id", default="internal_demo", help="Tenant id for entitlement checks.")
    parser.add_argument("--user-id", default="cli-mcp-client", help="User id for entitlement checks.")
    parser.add_argument(
        "--user-scopes",
        default="skill.invoke",
        help="Comma-separated user scopes for entitlement checks.",
    )
    parser.add_argument(
        "--enforce-entitlements",
        action="store_true",
        help="Enforce tenant/user skill entitlements before calling a tool.",
    )
    parser.add_argument("--enforce-sandbox", action="store_true", help="Enforce invocation sandbox limits.")
    parser.add_argument(
        "--action-class",
        choices=[
            "skill_invocation",
            "resource_access",
            "prompt_render",
            "external_network",
            "filesystem_write",
            "process_spawn",
            "secret_access",
            "repo_mutation",
            "unknown",
        ],
        default="skill_invocation",
        help="Sandbox action class for the tool call.",
    )
    parser.add_argument("--sandbox-endpoint", help="Endpoint label for sandbox audit evidence.")
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
        if args.enforce_policy or args.enforce_entitlements or args.enforce_sandbox or args.role:
            policy_context = PolicyInvocationContext(
                role=args.role or "agent",
                environment=args.environment,
                data_sensitivity=args.data_sensitivity,
                requested_action="invoke",
                enforce=args.enforce_policy,
                tenant_id=args.tenant_id,
                user_id=args.user_id,
                user_scopes=[scope.strip() for scope in args.user_scopes.split(",") if scope.strip()],
                enforce_entitlements=args.enforce_entitlements,
                enforce_sandbox=args.enforce_sandbox,
                action_class=args.action_class,
                endpoint=args.sandbox_endpoint or f"mcp:tool/{args.name}",
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
