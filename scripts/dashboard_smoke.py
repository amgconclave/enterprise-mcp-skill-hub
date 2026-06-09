from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import create_state  # noqa: E402


def main() -> int:
    state = create_state()
    smoke = state.ui_verification.dashboard_smoke()
    failed = [check for check in smoke.checks if check.status == "fail"]
    warned = [check for check in smoke.checks if check.status == "warn"]
    print("Dashboard Smoke")
    print(f"Status: {'PASS' if not failed else 'FAIL'} ({smoke.readiness_status})")
    print(
        "Checks: "
        f"{smoke.summary['pass_count']} pass, "
        f"{smoke.summary['warn_count']} warn, "
        f"{smoke.summary['fail_count']} fail"
    )
    print()
    print("Checked views:")
    for view in smoke.expected_views:
        print(f"- {view['label']}: {view['purpose']}")
    print()
    print("Checked endpoints:")
    for endpoint in smoke.endpoint_references:
        print(f"- {endpoint['method']} {endpoint['path']}: {endpoint['purpose']}")
    print()
    print("MCP proof surfaces:")
    for surface in smoke.mcp_proof_surfaces:
        print(f"- {surface['dashboard_label']}: {surface['proof']}")
    if warned:
        print()
        print("Warnings:")
        for check in warned:
            print(f"- {check.id}: {check.detail}")
    if failed:
        print()
        print("Failures:")
        for check in failed:
            print(f"- {check.id}: {check.detail}")
            if check.remediation:
                print(f"  Remediation: {check.remediation}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
