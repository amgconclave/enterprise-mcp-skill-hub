from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import create_state  # noqa: E402


def main() -> int:
    state = create_state()
    readiness = state.runtime_demo.readiness()
    failed_dependencies = [
        check
        for check in readiness.dependency_checks
        if check["required"] and check["status"] == "fail"
    ]

    print("Runtime Demo Readiness")
    print(f"Status: {readiness.readiness_status.upper()}")
    print(
        "Summary: "
        f"{readiness.summary['mcp_tool_count']} tools, "
        f"{readiness.summary['mcp_resource_count']} resources, "
        f"{readiness.summary['mcp_prompt_count']} prompts"
    )
    print()
    print("Start commands:")
    for item in readiness.start_commands:
        print(f"- {item['step']}. {item['service']}: {item['command']}")
    print()
    print("Dependency checks:")
    for check in readiness.dependency_checks:
        print(f"- {check['status'].upper()} {check['name']}: {check['detail']}")
    print()
    print("Port checks:")
    for check in readiness.port_checks:
        print(f"- {check['status'].upper()} {check['service']}:{check['port']} - {check['detail']}")
    print()
    print("Health and smoke URLs:")
    for item in readiness.health_urls + readiness.smoke_urls:
        label = item.get("service") or item.get("name")
        target = item.get("url") or item.get("path")
        print(f"- {label}: {target}")
    print()
    print("MCP CLI verification order:")
    for item in readiness.mcp_verification_commands:
        print(f"- {item['step']}. {item['command']}")
    print()
    print("Machine-readable summary:")
    print(json.dumps(readiness.summary, indent=2, sort_keys=True))
    return 1 if failed_dependencies else 0


if __name__ == "__main__":
    raise SystemExit(main())
