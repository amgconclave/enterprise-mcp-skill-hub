from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.models import (
    ApiContractAuditResult,
    ApiContractCheck,
    ApiContractDriftPackRequest,
    ApiContractDriftPackResult,
    ApiReviewerCollectionRequest,
    ApiReviewerCollectionResult,
    CiDoctorCheckStatus,
    InvokeSkillRequest,
    JsonDict,
    SecurityReadinessStatus,
    SkillInvocation,
)
from app.utils import new_trace_id, utc_now


class ApiContractService:
    AUDIT_ID = "api_contract_audit_latest"
    COLLECTION_ID = "reviewer_collection_latest"
    DRIFT_PACK_ID = "contract_drift_pack_latest"

    IMPORTANT_ENDPOINTS = [
        ("POST", "/auth/demo-token"),
        ("GET", "/health"),
        ("GET", "/skills"),
        ("POST", "/skills/{skill_id}/invoke"),
        ("GET", "/mcp/tools"),
        ("GET", "/mcp/resources"),
        ("GET", "/mcp/prompts"),
        ("GET", "/marketplace/catalog"),
        ("POST", "/marketplace/rollout-pack"),
        ("GET", "/skills/compatibility"),
        ("GET", "/skills/{skill_id}/compatibility"),
        ("POST", "/skills/compatibility-pack"),
        ("GET", "/usage/analytics"),
        ("POST", "/usage/chargeback-pack"),
        ("GET", "/reliability/skills"),
        ("PATCH", "/reliability/circuit-breakers/{skill_id}"),
        ("POST", "/reliability/pack"),
        ("GET", "/slo/report"),
        ("POST", "/slo/pack"),
        ("GET", "/providers/readiness"),
        ("POST", "/providers/fallback-pack"),
        ("GET", "/config/hygiene"),
        ("POST", "/config/hygiene-pack"),
        ("GET", "/sandbox/policy"),
        ("POST", "/sandbox/evaluate"),
        ("POST", "/sandbox/policy-pack"),
        ("GET", "/supply-chain/report"),
        ("POST", "/supply-chain/pack"),
        ("GET", "/prompt-governance/report"),
        ("POST", "/prompt-governance/validate"),
        ("POST", "/prompt-governance/pack"),
        ("GET", "/privacy/retention-report"),
        ("POST", "/privacy/redact"),
        ("POST", "/privacy/retention-pack"),
        ("GET", "/ops/smoke-matrix"),
        ("POST", "/ops/launch-checklist"),
        ("GET", "/ui/dashboard-smoke"),
        ("GET", "/artifacts/inventory"),
        ("GET", "/api/contract-audit"),
        ("POST", "/api/reviewer-collection"),
        ("POST", "/api/contract-drift-pack"),
        ("GET", "/handoff/final-audit"),
        ("POST", "/handoff/final-pack"),
        ("GET", "/runtime/demo-readiness"),
        ("POST", "/runtime/demo-pack"),
        ("GET", "/repository/automation-plan"),
        ("POST", "/repository/automation-pack"),
        ("GET", "/platform/pack"),
        ("POST", "/platform/pack/export"),
        ("POST", "/agents/collaborate"),
        ("POST", "/agents/collaboration-pack"),
        ("GET", "/agents/society-eval"),
        ("POST", "/agents/society-eval-pack"),
        ("GET", "/workers/runs"),
        ("POST", "/workers/runs"),
        ("GET", "/workers/scale-plan"),
        ("POST", "/workers/runbook-pack"),
    ]

    DEMO_FLOW_ENDPOINTS = [
        ("POST", "/agents/run"),
        ("POST", "/policy/simulate"),
        ("POST", "/workflows/{template_id}/simulate"),
        ("GET", "/conformance/report"),
        ("POST", "/evidence/export"),
        ("POST", "/releases/export"),
        ("POST", "/ops/launch-checklist"),
        ("POST", "/reviewer/walkthrough-pack"),
        ("POST", "/artifacts/readme-checklist"),
        ("GET", "/marketplace/catalog"),
        ("POST", "/marketplace/rollout-pack"),
        ("GET", "/skills/compatibility"),
        ("POST", "/skills/compatibility-pack"),
        ("GET", "/usage/analytics"),
        ("POST", "/usage/chargeback-pack"),
        ("GET", "/reliability/skills"),
        ("POST", "/reliability/pack"),
        ("GET", "/slo/report"),
        ("POST", "/slo/pack"),
        ("GET", "/providers/readiness"),
        ("POST", "/providers/fallback-pack"),
        ("GET", "/config/hygiene"),
        ("POST", "/config/hygiene-pack"),
        ("GET", "/sandbox/policy"),
        ("POST", "/sandbox/policy-pack"),
        ("GET", "/supply-chain/report"),
        ("POST", "/supply-chain/pack"),
        ("GET", "/prompt-governance/report"),
        ("POST", "/prompt-governance/pack"),
        ("GET", "/privacy/retention-report"),
        ("POST", "/privacy/retention-pack"),
        ("POST", "/ui/verification-pack"),
        ("GET", "/api/contract-audit"),
        ("POST", "/api/reviewer-collection"),
        ("POST", "/api/contract-drift-pack"),
        ("GET", "/repository/automation-plan"),
        ("POST", "/repository/automation-pack"),
        ("GET", "/platform/pack"),
        ("POST", "/platform/pack/export"),
        ("POST", "/agents/collaborate"),
        ("POST", "/agents/collaboration-pack"),
        ("GET", "/agents/society-eval"),
        ("POST", "/agents/society-eval-pack"),
        ("POST", "/workers/runs"),
        ("GET", "/workers/scale-plan"),
        ("POST", "/workers/runbook-pack"),
    ]

    def __init__(
        self,
        app_state: Any,
        output_dir: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self.app_state = app_state
        self.output_dir = output_dir or Path("data") / "api_contracts"
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]

    def contract_audit(self) -> ApiContractAuditResult:
        routes = self._route_inventory()
        route_keys = {(route["method"], route["path"]) for route in routes}
        docs_coverage = self._docs_api_coverage(route_keys)
        dashboard_alignment = self._dashboard_smoke_alignment(route_keys)
        artifact_coverage = self._generated_artifact_endpoint_coverage(route_keys)
        demo_coverage = self._demo_flow_endpoint_coverage(route_keys)
        mcp_inventory = self._mcp_inventory()
        mcp_coverage = self._mcp_coverage(mcp_inventory)
        contract_drift = self._contract_drift(route_keys, mcp_inventory)
        missing_docs = [
            f"{item['method']} {item['path']} is missing from docs/api.md."
            for item in docs_coverage
            if item["important"] and not item["docs_api_mentioned"]
        ]
        duplicate_deprecated_warnings = self._deprecated_duplicate_route_warnings(routes)
        checks = self._checks(
            routes,
            docs_coverage,
            dashboard_alignment,
            artifact_coverage,
            demo_coverage,
            mcp_inventory,
            mcp_coverage,
            contract_drift,
            missing_docs,
            duplicate_deprecated_warnings,
        )
        fail_count = sum(1 for check in checks if check.status == "fail")
        warn_count = sum(1 for check in checks if check.status == "warn")
        readiness_status: SecurityReadinessStatus = "ready"
        if fail_count:
            readiness_status = "blocked"
        elif warn_count:
            readiness_status = "needs_review"
        score = self._score(checks)
        protected_count = sum(1 for route in routes if route["auth_required"])
        summary = {
            "local_only": True,
            "mock_provider": self.app_state.provider.name == "mock",
            "route_count": len(routes),
            "protected_endpoint_count": protected_count,
            "important_endpoint_count": len(docs_coverage),
            "docs_api_missing_count": len(missing_docs),
            "dashboard_smoke_aligned": dashboard_alignment["aligned"],
            "generated_artifact_endpoint_count": len(artifact_coverage),
            "demo_flow_endpoint_count": len(demo_coverage),
            "mcp_tool_count": mcp_inventory["tool_count"],
            "mcp_resource_count": mcp_inventory["resource_count"],
            "mcp_prompt_count": mcp_inventory["prompt_count"],
            "contract_drift_status": contract_drift["status"],
            "contract_drift_count": contract_drift["drift_count"],
            "contract_warning_count": contract_drift["warning_count"],
            "warning_count": warn_count,
            "fail_count": fail_count,
            "artifact_root": str(self.output_dir),
        }
        return ApiContractAuditResult(
            audit_id=self.AUDIT_ID,
            generated_at=utc_now(),
            readiness_status=readiness_status,
            score=score,
            summary=summary,
            checks=checks,
            openapi_route_count=len(routes),
            auth_protected_endpoint_count=protected_count,
            endpoint_inventory_by_domain=self._group_routes_by_domain(routes),
            docs_api_coverage=docs_coverage,
            dashboard_smoke_alignment=dashboard_alignment,
            generated_artifact_endpoint_coverage=artifact_coverage,
            demo_flow_endpoint_coverage=demo_coverage,
            mcp_inventory=mcp_inventory,
            mcp_coverage=mcp_coverage,
            contract_drift=contract_drift,
            missing_docs_warnings=missing_docs,
            deprecated_duplicate_route_warnings=duplicate_deprecated_warnings,
            local_only_limitations=self._limitations(),
            verification_commands=self._verification_commands(),
        )

    def reviewer_collection(
        self,
        request: ApiReviewerCollectionRequest | None = None,
    ) -> ApiReviewerCollectionResult:
        request = request or ApiReviewerCollectionRequest()
        audit = self.contract_audit()
        bundle = {
            "collection_id": self.COLLECTION_ID,
            "generated_at": utc_now().isoformat(),
            "actor": request.actor,
            "readiness_status": audit.readiness_status,
            "contract_audit": audit.model_dump(mode="json"),
            "endpoint_inventory_grouped_by_domain": audit.endpoint_inventory_by_domain,
            "mcp_inventory": audit.mcp_inventory,
            "contract_drift": audit.contract_drift,
            "sample_commands": self._sample_commands(),
            "demo_token_flow": self._demo_token_flow(),
            "mcp_cli_commands": self._mcp_cli_commands(),
            "expected_status_codes": self._expected_status_codes(),
            "auth_notes": self._auth_notes(),
            "generated_artifact_endpoints": audit.generated_artifact_endpoint_coverage,
            "one_command_verification_order": self._one_command_verification_order(),
            "recruiter_engineer_explanation": self._recruiter_engineer_explanation(audit),
            "limitations": audit.local_only_limitations,
        }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"{self.COLLECTION_ID}.json"
        markdown_path = self.output_dir / f"{self.COLLECTION_ID}.md"
        json_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(self._markdown(bundle), encoding="utf-8")
        self.app_state.audit.record(
            "api.reviewer_collection_exported",
            "api_reviewer_collection",
            self.COLLECTION_ID,
            new_trace_id(),
            request.actor,
            {
                "readiness_status": audit.readiness_status,
                "score": audit.score,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
        )
        return ApiReviewerCollectionResult(
            collection_id=self.COLLECTION_ID,
            generated_at=utc_now(),
            readiness_status=audit.readiness_status,
            json_path=str(json_path.resolve()),
            markdown_path=str(markdown_path.resolve()),
            summary={
                "readiness_status": audit.readiness_status,
                "score": audit.score,
                "route_count": audit.openapi_route_count,
                "protected_endpoint_count": audit.auth_protected_endpoint_count,
                "mcp_tool_count": audit.mcp_inventory["tool_count"],
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
        )

    def contract_drift_pack(
        self,
        request: ApiContractDriftPackRequest | None = None,
    ) -> ApiContractDriftPackResult:
        request = request or ApiContractDriftPackRequest()
        audit = self.contract_audit()
        drift = audit.contract_drift
        bundle = {
            "pack_id": self.DRIFT_PACK_ID,
            "generated_at": utc_now().isoformat(),
            "actor": request.actor,
            "readiness_status": audit.readiness_status,
            "score": audit.score,
            "contract_drift": drift,
            "fastapi_contract": drift["fastapi_contract"],
            "mcp_manifest_matrix": drift["mcp_manifest_matrix"],
            "remediation_plan": drift["remediation_plan"],
            "governance_patterns": drift["governance_patterns"],
            "local_verification_commands": self._verification_commands(),
            "limitations": audit.local_only_limitations,
        }
        self.output_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.output_dir / f"{self.DRIFT_PACK_ID}.json"
        markdown_path = self.output_dir / f"{self.DRIFT_PACK_ID}.md"
        json_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
        markdown_path.write_text(self._drift_markdown(bundle), encoding="utf-8")
        self.app_state.audit.record(
            "api.contract_drift_pack_exported",
            "api_contract_drift_pack",
            self.DRIFT_PACK_ID,
            new_trace_id(),
            request.actor,
            {
                "readiness_status": audit.readiness_status,
                "score": audit.score,
                "drift_count": drift["drift_count"],
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
        )
        return ApiContractDriftPackResult(
            pack_id=self.DRIFT_PACK_ID,
            generated_at=utc_now(),
            readiness_status=audit.readiness_status,
            score=audit.score,
            json_path=str(json_path.resolve()),
            markdown_path=str(markdown_path.resolve()),
            summary={
                "readiness_status": audit.readiness_status,
                "score": audit.score,
                "contract_drift_status": drift["status"],
                "drift_count": drift["drift_count"],
                "warning_count": drift["warning_count"],
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            },
        )

    def _route_inventory(self) -> list[JsonDict]:
        source = self._read_text(Path("app") / "main.py")
        pattern = re.compile(
            r"@app\.(get|post|patch|put|delete)\(\s*[\"']([^\"']+)[\"'][^\n]*\n(?P<body>.*?)(?=\n@app\.|\Z)",
            re.DOTALL,
        )
        routes = []
        for method, path, body in pattern.findall(source):
            function_match = re.search(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)|async\s+def\s+([a-zA-Z_][a-zA-Z0-9_]*)", body)
            function_name = ""
            if function_match:
                function_name = next(group for group in function_match.groups() if group)
            routes.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "domain": self._domain_for(path),
                    "function": function_name,
                    "auth_required": "Depends(require_api_key)" in body,
                    "openapi_inferred": True,
                    "docs_api_mentioned": path in self._read_text(Path("docs") / "api.md"),
                    "deprecated_hint": "deprecated" in body.lower() or "deprecated" in path.lower(),
                }
            )
        return sorted(routes, key=lambda route: (route["domain"], route["path"], route["method"]))

    def _group_routes_by_domain(self, routes: list[JsonDict]) -> JsonDict:
        grouped: dict[str, list[JsonDict]] = defaultdict(list)
        for route in routes:
            grouped[route["domain"]].append(route)
        return {
            domain: {
                "count": len(items),
                "protected_count": sum(1 for item in items if item["auth_required"]),
                "endpoints": items,
            }
            for domain, items in sorted(grouped.items())
        }

    def _docs_api_coverage(self, route_keys: set[tuple[str, str]]) -> list[JsonDict]:
        docs = self._read_text(Path("docs") / "api.md")
        readme = self._read_text(Path("README.md"))
        rows = []
        for method, path in self.IMPORTANT_ENDPOINTS:
            rows.append(
                {
                    "method": method,
                    "path": path,
                    "important": True,
                    "implemented": (method, path) in route_keys,
                    "docs_api_mentioned": path in docs,
                    "readme_mentioned": path in readme,
                }
            )
        return rows

    def _dashboard_smoke_alignment(self, route_keys: set[tuple[str, str]]) -> JsonDict:
        smoke = self.app_state.ui_verification.dashboard_smoke()
        endpoint_refs = smoke.endpoint_references
        missing_routes = [
            f"{endpoint['method']} {endpoint['path']}"
            for endpoint in endpoint_refs
            if (endpoint["method"], endpoint["path"]) not in route_keys
        ]
        contract_refs = [
            endpoint
            for endpoint in endpoint_refs
            if endpoint["path"] in {"/api/contract-audit", "/api/reviewer-collection"}
        ]
        return {
            "smoke_id": smoke.smoke_id,
            "readiness_status": smoke.readiness_status,
            "aligned": not missing_routes and len(contract_refs) == 2,
            "endpoint_reference_count": len(endpoint_refs),
            "missing_route_references": missing_routes,
            "contract_endpoint_references": contract_refs,
            "generated_artifact_tabs": [
                tab
                for tab in smoke.generated_artifact_tabs
                if tab["artifact_dir"] == "data/api_contracts/"
            ],
        }

    def _generated_artifact_endpoint_coverage(self, route_keys: set[tuple[str, str]]) -> list[JsonDict]:
        rows = []
        for item in self.app_state.artifacts.inventory().items:
            if not item.producer_endpoint:
                continue
            method, path = item.producer_endpoint.split(" ", 1)
            rows.append(
                {
                    "artifact_id": item.artifact_id,
                    "name": item.name,
                    "producer_endpoint": item.producer_endpoint,
                    "directory": item.directory,
                    "ignored_status": item.ignored_status,
                    "implemented": (method, path) in route_keys,
                    "generated": item.generated,
                }
            )
        return rows

    def _demo_flow_endpoint_coverage(self, route_keys: set[tuple[str, str]]) -> list[JsonDict]:
        demo_source = self._read_text(Path("app") / "demo.py")
        return [
            {
                "method": method,
                "path": path,
                "implemented": (method, path) in route_keys,
                "demo_mentions_path": path in demo_source,
                "demo_invokes_service": self._demo_service_hint(path) in demo_source,
            }
            for method, path in self.DEMO_FLOW_ENDPOINTS
        ]

    def _mcp_inventory(self) -> JsonDict:
        tools = self.app_state.mcp.list_tools()
        resources = self.app_state.mcp.list_resources()
        prompts = self.app_state.mcp.list_prompts()
        return {
            "tool_count": len(tools),
            "resource_count": len(resources),
            "prompt_count": len(prompts),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "version": tool.annotations.get("version"),
                    "input_schema_keys": sorted(tool.input_schema.get("properties", {}).keys()),
                    "output_schema_keys": sorted(tool.output_schema.get("properties", {}).keys()),
                    "input_schema_hash": self._schema_hash(tool.input_schema),
                    "output_schema_hash": self._schema_hash(tool.output_schema),
                    "annotations": tool.annotations,
                }
                for tool in tools
            ],
            "resources": [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "mime_type": resource.mime_type,
                    "content_ref": resource.content_ref,
                }
                for resource in resources
            ],
            "prompts": [
                {
                    "id": prompt.id,
                    "name": prompt.name,
                    "arguments": [argument.model_dump(mode="json") for argument in prompt.arguments],
                }
                for prompt in prompts
            ],
            "cli_commands": self._mcp_cli_commands(),
        }

    def _mcp_coverage(self, mcp_inventory: JsonDict) -> JsonDict:
        docs = self._read_text(Path("docs") / "mcp.md") + "\n" + self._read_text(Path("docs") / "api.md")
        readme = self._read_text(Path("README.md"))
        commands = self._mcp_cli_commands()
        return {
            "tools_endpoint_documented": "/mcp/tools" in docs,
            "resources_endpoint_documented": "/mcp/resources" in docs,
            "prompts_endpoint_documented": "/mcp/prompts" in docs,
            "cli_commands_documented": {command: command in docs or command in readme for command in commands},
            "all_inventory_non_empty": all(
                mcp_inventory[key] > 0 for key in ("tool_count", "resource_count", "prompt_count")
            ),
        }

    def _checks(
        self,
        routes: list[JsonDict],
        docs_coverage: list[JsonDict],
        dashboard_alignment: JsonDict,
        artifact_coverage: list[JsonDict],
        demo_coverage: list[JsonDict],
        mcp_inventory: JsonDict,
        mcp_coverage: JsonDict,
        contract_drift: JsonDict,
        missing_docs: list[str],
        duplicate_deprecated_warnings: list[str],
    ) -> list[ApiContractCheck]:
        protected_count = sum(1 for route in routes if route["auth_required"])
        missing_important = [
            f"{item['method']} {item['path']}" for item in docs_coverage if not item["implemented"]
        ]
        artifact_missing = [
            item["producer_endpoint"] for item in artifact_coverage if not item["implemented"]
        ]
        demo_missing = [f"{item['method']} {item['path']}" for item in demo_coverage if not item["implemented"]]
        drift_status = "fail" if contract_drift["drift_count"] else "pass"
        if contract_drift["warning_count"] and drift_status == "pass":
            drift_status = "warn"
        return [
            self._check(
                "openapi_route_count",
                "openapi",
                "OpenAPI route count",
                "pass" if routes else "fail",
                f"Found {len(routes)} FastAPI route decorator(s) in app/main.py.",
                [f"{route['method']} {route['path']}" for route in routes[:10]],
                "Restore FastAPI route declarations in app/main.py.",
            ),
            self._check(
                "auth_protected_endpoint_count",
                "auth",
                "Auth-protected endpoint count",
                "pass" if protected_count >= 1 else "fail",
                f"Found {protected_count} endpoint(s) guarded by X-API-Key dependency.",
                [f"{route['method']} {route['path']}" for route in routes if route["auth_required"]][:10],
                "Protect non-public API endpoints with require_api_key.",
            ),
            self._check(
                "important_endpoint_docs_api_coverage",
                "docs",
                "docs/api coverage for important endpoints",
                "pass" if not missing_docs and not missing_important else "warn",
                f"{len(missing_docs)} important endpoint doc mention(s) missing; {len(missing_important)} important route(s) missing.",
                [f"{item['method']} {item['path']}" for item in docs_coverage if item["docs_api_mentioned"]],
                "Add missing important endpoint mentions to docs/api.md.",
            ),
            self._check(
                "dashboard_smoke_alignment",
                "dashboard",
                "Dashboard smoke alignment",
                "pass" if dashboard_alignment["aligned"] else "warn",
                f"Dashboard smoke references {dashboard_alignment['endpoint_reference_count']} endpoint(s) and includes API Contract endpoints: {len(dashboard_alignment['contract_endpoint_references'])}.",
                [endpoint["path"] for endpoint in dashboard_alignment["contract_endpoint_references"]],
                "Add API Contract endpoints and artifact tab to DashboardSmokeService.",
            ),
            self._check(
                "generated_artifact_endpoint_coverage",
                "artifacts",
                "Generated artifact endpoint coverage",
                "pass" if not artifact_missing else "warn",
                f"{len(artifact_coverage)} generated artifact producer endpoint(s) checked; {len(artifact_missing)} missing route(s).",
                [item["producer_endpoint"] for item in artifact_coverage if item["implemented"]],
                "Keep artifact inventory producer endpoints aligned with FastAPI routes.",
            ),
            self._check(
                "demo_flow_endpoint_coverage",
                "demo",
                "Demo flow endpoint coverage",
                "pass" if not demo_missing else "warn",
                f"{len(demo_coverage)} demo flow endpoint(s) checked; {len(demo_missing)} missing route(s).",
                [f"{item['method']} {item['path']}" for item in demo_coverage if item["implemented"]],
                "Keep app/demo.py service flow aligned with published API endpoints.",
            ),
            self._check(
                "mcp_tools_resources_prompts_coverage",
                "mcp",
                "MCP tools/resources/prompts coverage",
                "pass" if mcp_coverage["all_inventory_non_empty"] else "fail",
                f"Found {mcp_inventory['tool_count']} tool(s), {mcp_inventory['resource_count']} resource(s), and {mcp_inventory['prompt_count']} prompt(s).",
                mcp_inventory["cli_commands"],
                "Promote at least one skill and keep MCP resources/prompts registered.",
            ),
            self._check(
                "tool_contract_drift",
                "contract drift",
                "Tool contract drift",
                drift_status,
                f"{contract_drift['drift_count']} blocking drift item(s), {contract_drift['warning_count']} warning(s), and {contract_drift['aligned_count']} aligned promoted tool(s).",
                [
                    f"{item['skill_id']}: {item['status']}"
                    for item in contract_drift["mcp_manifest_matrix"]
                    if item["status"] != "aligned"
                ][:10],
                "Regenerate MCP tool schemas from promoted manifests, update docs for version changes, and export the Contract Drift Pack.",
            ),
            self._check(
                "missing_docs_warnings",
                "docs",
                "Missing docs warnings",
                "pass" if not missing_docs else "warn",
                f"{len(missing_docs)} important endpoint(s) are missing docs/api.md coverage.",
                missing_docs[:10],
                "Update docs/api.md for the missing endpoint(s).",
            ),
            self._check(
                "deprecated_duplicate_route_warnings",
                "routes",
                "Deprecated or duplicate route warnings",
                "pass" if not duplicate_deprecated_warnings else "warn",
                f"{len(duplicate_deprecated_warnings)} deprecated or duplicate route warning(s) found.",
                duplicate_deprecated_warnings[:10],
                "Remove duplicates or mark deprecated routes clearly in docs.",
            ),
            self._check(
                "local_only_limitations",
                "runtime",
                "Local-only limitations",
                "pass",
                f"{len(self._limitations())} local-only limitation(s) disclosed.",
                self._limitations(),
                None,
            ),
        ]

    def _check(
        self,
        check_id: str,
        category: str,
        title: str,
        status: CiDoctorCheckStatus,
        detail: str,
        evidence: list[str],
        remediation: str | None,
    ) -> ApiContractCheck:
        return ApiContractCheck(
            id=check_id,
            category=category,
            status=status,
            title=title,
            detail=detail,
            evidence=evidence,
            remediation=None if status == "pass" else remediation,
        )

    def _contract_drift(self, route_keys: set[tuple[str, str]], mcp_inventory: JsonDict) -> JsonDict:
        matrix = self._mcp_manifest_matrix()
        fastapi_contract = self._fastapi_contract_summary(route_keys)
        drift_count = sum(1 for item in matrix if item["status"] == "drift")
        warning_count = sum(1 for item in matrix if item["status"] == "warning")
        aligned_count = sum(1 for item in matrix if item["status"] == "aligned")
        remediation_plan = self._drift_remediation(matrix, fastapi_contract)
        status = "drift_detected" if drift_count else "aligned"
        if warning_count and not drift_count:
            status = "needs_review"
        return {
            "status": status,
            "drift_count": drift_count,
            "warning_count": warning_count,
            "aligned_count": aligned_count,
            "promoted_manifest_count": len(self.app_state.registry.mcp_exposed()),
            "mcp_tool_count": mcp_inventory["tool_count"],
            "fastapi_contract": fastapi_contract,
            "mcp_manifest_matrix": matrix,
            "remediation_plan": remediation_plan,
            "governance_patterns": [
                "tool registry: promoted manifests remain the source of truth for MCP tool schemas.",
                "tool governance: each exposed tool carries schema hashes, version evidence, and remediation notes.",
                "handoffs: the drift pack writes local JSON/Markdown artifacts for reviewer sign-off.",
            ],
        }

    def _mcp_manifest_matrix(self) -> list[JsonDict]:
        tools = {tool.name: tool for tool in self.app_state.mcp.list_tools()}
        rows = []
        for manifest in self.app_state.registry.list():
            tool = tools.get(manifest.id)
            manifest_input_hash = self._schema_hash(manifest.input_schema)
            manifest_output_hash = self._schema_hash(manifest.output_schema)
            latest_version = self.app_state.registry.versions(manifest.id)[-1]
            if not self.app_state.registry.is_mcp_exposed(manifest):
                rows.append(
                    {
                        "skill_id": manifest.id,
                        "status": "warning",
                        "mcp_exposed": False,
                        "manifest_version": manifest.version,
                        "latest_registry_version": latest_version.version,
                        "manifest_hash": latest_version.manifest_hash,
                        "manifest_input_schema_hash": manifest_input_hash,
                        "manifest_output_schema_hash": manifest_output_hash,
                        "mcp_input_schema_hash": None,
                        "mcp_output_schema_hash": None,
                        "drift_reasons": ["Skill is not promoted/enabled for MCP exposure."],
                        "remediation": "Promote the skill if agents should discover it, or leave it hidden intentionally.",
                    }
                )
                continue
            if tool is None:
                rows.append(
                    {
                        "skill_id": manifest.id,
                        "status": "drift",
                        "mcp_exposed": False,
                        "manifest_version": manifest.version,
                        "latest_registry_version": latest_version.version,
                        "manifest_hash": latest_version.manifest_hash,
                        "manifest_input_schema_hash": manifest_input_hash,
                        "manifest_output_schema_hash": manifest_output_hash,
                        "mcp_input_schema_hash": None,
                        "mcp_output_schema_hash": None,
                        "drift_reasons": ["Promoted manifest is missing from MCP tool registry."],
                        "remediation": "Ensure McpToolAdapter.list_tools reads promoted manifests and validates their schemas.",
                    }
                )
                continue
            tool_input_hash = self._schema_hash(tool.input_schema)
            tool_output_hash = self._schema_hash(tool.output_schema)
            reasons = []
            if tool.annotations.get("version") != manifest.version:
                reasons.append("MCP annotation version does not match manifest version.")
            if tool_input_hash != manifest_input_hash:
                reasons.append("MCP input schema hash differs from manifest input schema hash.")
            if tool_output_hash != manifest_output_hash:
                reasons.append("MCP output schema hash differs from manifest output schema hash.")
            rows.append(
                {
                    "skill_id": manifest.id,
                    "status": "drift" if reasons else "aligned",
                    "mcp_exposed": True,
                    "manifest_version": manifest.version,
                    "mcp_version": tool.annotations.get("version"),
                    "latest_registry_version": latest_version.version,
                    "manifest_hash": latest_version.manifest_hash,
                    "manifest_input_schema_hash": manifest_input_hash,
                    "manifest_output_schema_hash": manifest_output_hash,
                    "mcp_input_schema_hash": tool_input_hash,
                    "mcp_output_schema_hash": tool_output_hash,
                    "input_schema_keys": sorted(manifest.input_schema.get("properties", {}).keys()),
                    "output_schema_keys": sorted(manifest.output_schema.get("properties", {}).keys()),
                    "drift_reasons": reasons,
                    "remediation": (
                        "Regenerate the MCP tool definition from the promoted manifest."
                        if reasons
                        else "No remediation required."
                    ),
                }
            )
        return rows

    def _fastapi_contract_summary(self, route_keys: set[tuple[str, str]]) -> JsonDict:
        request_schema = InvokeSkillRequest.model_json_schema()
        response_schema = SkillInvocation.model_json_schema()
        request_fields = sorted(request_schema.get("properties", {}).keys())
        response_fields = sorted(response_schema.get("properties", {}).keys())
        required_routes = {
            "invoke_skill": ("POST", "/skills/{skill_id}/invoke"),
            "mcp_tools": ("GET", "/mcp/tools"),
            "contract_audit": ("GET", "/api/contract-audit"),
            "contract_drift_pack": ("POST", "/api/contract-drift-pack"),
        }
        route_alignment = {
            name: {"method": method, "path": path, "implemented": (method, path) in route_keys}
            for name, (method, path) in required_routes.items()
        }
        governance_fields = ["input", "actor", "policy_context"]
        trace_fields = ["skill_id", "version", "trace_id", "token_usage", "latency_ms"]
        missing_request_fields = [field for field in governance_fields if field not in request_fields]
        missing_response_fields = [field for field in trace_fields if field not in response_fields]
        return {
            "invoke_endpoint": route_alignment["invoke_skill"],
            "route_alignment": route_alignment,
            "request_model": "InvokeSkillRequest",
            "response_model": "SkillInvocation",
            "request_schema_hash": self._schema_hash(request_schema),
            "response_schema_hash": self._schema_hash(response_schema),
            "request_fields": request_fields,
            "response_fields": response_fields,
            "missing_governance_request_fields": missing_request_fields,
            "missing_trace_response_fields": missing_response_fields,
            "status": "aligned" if not missing_request_fields and not missing_response_fields else "warning",
            "note": "FastAPI exposes a governed generic skill invocation contract; per-skill JSON schemas remain in manifests and MCP tools.",
        }

    def _drift_remediation(self, matrix: list[JsonDict], fastapi_contract: JsonDict) -> list[JsonDict]:
        plan = []
        for item in matrix:
            if item["status"] == "aligned":
                continue
            plan.append(
                {
                    "target": item["skill_id"],
                    "severity": "blocker" if item["status"] == "drift" else "review",
                    "reason": "; ".join(item["drift_reasons"]),
                    "action": item["remediation"],
                }
            )
        if fastapi_contract["status"] != "aligned":
            plan.append(
                {
                    "target": "FastAPI invocation contract",
                    "severity": "review",
                    "reason": "Generic invoke request/response model is missing governance or trace fields.",
                    "action": "Restore input, actor, policy_context, skill_id, version, trace_id, token_usage, and latency fields.",
                }
            )
        if not plan:
            plan.append(
                {
                    "target": "contract surfaces",
                    "severity": "none",
                    "reason": "Promoted manifest schemas, MCP tool schemas, and FastAPI governance fields are aligned.",
                    "action": "Regenerate this pack before release or after manifest/schema changes.",
                }
            )
        return plan

    def _schema_hash(self, schema: JsonDict) -> str:
        return sha256(self._canonical_json(schema).encode("utf-8")).hexdigest()[:16]

    def _canonical_json(self, payload: JsonDict) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    def _deprecated_duplicate_route_warnings(self, routes: list[JsonDict]) -> list[str]:
        counts = Counter((route["method"], route["path"]) for route in routes)
        warnings = [
            f"Duplicate route declaration: {method} {path}"
            for (method, path), count in counts.items()
            if count > 1
        ]
        warnings.extend(
            f"Deprecated route hint found: {route['method']} {route['path']}"
            for route in routes
            if route["deprecated_hint"]
        )
        return sorted(warnings)

    def _expected_status_codes(self) -> list[JsonDict]:
        return [
            {"method": "POST", "path": "/auth/demo-token", "with_api_key": False, "expected_status": 200},
            {"method": "GET", "path": "/health", "with_api_key": False, "expected_status": 200},
            {"method": "GET", "path": "/skills", "with_api_key": False, "expected_status": 401},
            {"method": "GET", "path": "/skills", "with_api_key": True, "expected_status": 200},
            {"method": "GET", "path": "/api/contract-audit", "with_api_key": True, "expected_status": 200},
            {"method": "POST", "path": "/api/contract-drift-pack", "with_api_key": True, "expected_status": 200},
            {"method": "GET", "path": "/marketplace/catalog", "with_api_key": True, "expected_status": 200},
            {"method": "GET", "path": "/skills/compatibility", "with_api_key": True, "expected_status": 200},
            {
                "method": "POST",
                "path": "/skills/compatibility-pack",
                "with_api_key": True,
                "expected_status": 200,
            },
            {"method": "GET", "path": "/usage/analytics", "with_api_key": True, "expected_status": 200},
            {
                "method": "POST",
                "path": "/usage/chargeback-pack",
                "with_api_key": True,
                "expected_status": 200,
            },
            {"method": "GET", "path": "/reliability/skills", "with_api_key": True, "expected_status": 200},
            {
                "method": "POST",
                "path": "/reliability/pack",
                "with_api_key": True,
                "expected_status": 200,
            },
            {"method": "GET", "path": "/slo/report", "with_api_key": True, "expected_status": 200},
            {
                "method": "POST",
                "path": "/slo/pack",
                "with_api_key": True,
                "expected_status": 200,
            },
            {"method": "GET", "path": "/prompt-governance/report", "with_api_key": True, "expected_status": 200},
            {
                "method": "POST",
                "path": "/prompt-governance/pack",
                "with_api_key": True,
                "expected_status": 200,
            },
            {"method": "GET", "path": "/privacy/retention-report", "with_api_key": True, "expected_status": 200},
            {
                "method": "POST",
                "path": "/privacy/retention-pack",
                "with_api_key": True,
                "expected_status": 200,
            },
            {"method": "GET", "path": "/workers/scale-plan", "with_api_key": True, "expected_status": 200},
            {"method": "POST", "path": "/workers/runs", "with_api_key": True, "expected_status": 200},
            {"method": "POST", "path": "/workers/runbook-pack", "with_api_key": True, "expected_status": 200},
            {
                "method": "POST",
                "path": "/marketplace/rollout-pack",
                "with_api_key": True,
                "expected_status": 200,
            },
            {
                "method": "POST",
                "path": "/api/reviewer-collection",
                "with_api_key": True,
                "expected_status": 200,
            },
            {"method": "GET", "path": "/mcp/tools", "with_api_key": True, "expected_status": 200},
            {"method": "GET", "path": "/mcp/resources", "with_api_key": True, "expected_status": 200},
            {"method": "GET", "path": "/mcp/prompts", "with_api_key": True, "expected_status": 200},
        ]

    def _sample_commands(self) -> JsonDict:
        return {
            "powershell": [
                "$token = Invoke-RestMethod http://localhost:8000/auth/demo-token -Method POST",
                "$headers = @{ $token.header = $token.token }",
                "Invoke-RestMethod http://localhost:8000/api/contract-audit -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/api/contract-drift-pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/marketplace/catalog -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/marketplace/rollout-pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/skills/compatibility -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/skills/compatibility-pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/usage/analytics -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/usage/chargeback-pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/reliability/skills -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/reliability/pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/slo/report -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/slo/pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/prompt-governance/report -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/prompt-governance/pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/privacy/retention-report -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/privacy/retention-pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/workers/scale-plan -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/workers/runbook-pack -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/api/reviewer-collection -Method POST -Headers $headers",
                "Invoke-RestMethod http://localhost:8000/mcp/tools -Headers $headers",
            ],
            "curl": [
                "curl.exe -s -X POST http://localhost:8000/auth/demo-token",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/api/contract-audit",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/api/contract-drift-pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/marketplace/catalog",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/marketplace/rollout-pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/skills/compatibility",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/skills/compatibility-pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/usage/analytics",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/usage/chargeback-pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/reliability/skills",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/reliability/pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/slo/report",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/slo/pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/prompt-governance/report",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/prompt-governance/pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/privacy/retention-report",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/privacy/retention-pack",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/workers/scale-plan",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/workers/runbook-pack",
                "curl.exe -s -X POST -H \"X-API-Key: dev-local-token\" http://localhost:8000/api/reviewer-collection",
                "curl.exe -s -H \"X-API-Key: dev-local-token\" http://localhost:8000/mcp/tools",
            ],
        }

    def _demo_token_flow(self) -> list[JsonDict]:
        return [
            {
                "step": 1,
                "command": "Invoke-RestMethod http://localhost:8000/auth/demo-token -Method POST",
                "expected_status": 200,
                "expected_output": "`token` and `header` fields.",
            },
            {
                "step": 2,
                "command": "$headers = @{ \"X-API-Key\" = \"dev-local-token\" }",
                "expected_status": "local shell setup",
                "expected_output": "Headers object for protected endpoints.",
            },
            {
                "step": 3,
                "command": "Invoke-RestMethod http://localhost:8000/api/contract-audit -Headers $headers",
                "expected_status": 200,
                "expected_output": "Structured API Contract audit JSON.",
            },
        ]

    def _mcp_cli_commands(self) -> list[str]:
        return [
            "python -m app.mcp_server tools",
            "python -m app.mcp_server resources",
            "python -m app.mcp_server prompts",
        ]

    def _auth_notes(self) -> list[str]:
        return [
            "`POST /auth/demo-token` and `GET /health` are public local demo endpoints.",
            "All API Contract, MCP, skill, workflow, ops, artifact, and dashboard endpoints expect `X-API-Key`.",
            "The default local token is `dev-local-token`; `.env` can override it through `API_KEY`.",
            "401 on a protected endpoint means the reviewer should refresh `$headers` from the demo-token flow.",
        ]

    def _one_command_verification_order(self) -> list[JsonDict]:
        commands = [
            "python -m pytest -q",
            "python -m ruff check app tests dashboard",
            "python -m app.evals.run_eval",
            "python -m app.evals.run_eval --validate-only",
            "python -m app.evals.run_conformance",
            "python scripts\\dashboard_smoke.py",
            "python -m app.demo",
            "python -m app.mcp_server tools",
            "python -m app.mcp_server resources",
            "python -m app.mcp_server prompts",
            "Invoke-RestMethod http://localhost:8000/api/contract-drift-pack -Method POST -Headers $headers",
            'rg "marketplace/catalog|marketplace/rollout-pack|Skill Marketplace|Tenant Rollout|marketplace_packs|rollout approval" app dashboard docs README.md tests scripts sample_data',
            'rg "skills/compatibility|compatibility-pack|Skill Compatibility|compatibility_packs|deprecated skill|migration recommendations" app dashboard docs README.md tests scripts sample_data',
            'rg "usage/analytics|usage/chargeback-pack|Skill Usage|Cost Chargeback|usage_packs|chargeback" app dashboard docs README.md tests scripts sample_data',
            'rg "slo/report|slo/pack|Skill SLO|slo_packs|error budget" app dashboard docs README.md tests scripts sample_data',
            'rg "api/contract-audit|api/reviewer-collection|API Contract|api_contracts|Reviewer Collection|OpenAPI" app dashboard docs README.md tests scripts sample_data',
            "Get-ChildItem -Recurse -File data\\api_contracts -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime",
        ]
        return [
            {"step": index, "command": command, "expected": self._expected_for_command(command)}
            for index, command in enumerate(commands, start=1)
        ]

    def _verification_commands(self) -> list[str]:
        return [item["command"] for item in self._one_command_verification_order()]

    def _recruiter_engineer_explanation(self, audit: ApiContractAuditResult) -> JsonDict:
        return {
            "recruiter": (
                "The API Contract audit turns the repo into a self-checking portfolio artifact: "
                f"{audit.openapi_route_count} FastAPI routes, {audit.mcp_inventory['tool_count']} MCP tools, "
                f"{audit.mcp_inventory['resource_count']} resources, and {audit.mcp_inventory['prompt_count']} prompts "
                "are summarized with copy-ready local commands."
            ),
            "engineer": (
                "The Reviewer Collection is generated from route decorators, docs, dashboard smoke wiring, "
                "artifact inventory, demo flow expectations, and the live in-process MCP adapter. "
                "It should be regenerated from a fresh clone and compared against pytest, ruff, eval, conformance, "
                "dashboard smoke, demo, and MCP CLI output."
            ),
        }

    def _limitations(self) -> list[str]:
        return [
            "OpenAPI route count is source-derived from FastAPI decorators in app/main.py; it does not start a server.",
            "Docs coverage checks route string mentions in docs/api.md and README.md rather than semantic prose quality.",
            "Dashboard alignment uses deterministic Streamlit source smoke checks; it does not launch a browser.",
            "Generated artifact coverage confirms producer endpoint wiring and ignored folders, not artifact freshness in CI.",
            "The default provider is local/mock; OpenAI and Azure OpenAI remain optional integrations.",
        ]

    def _markdown(self, bundle: JsonDict) -> str:
        audit = bundle["contract_audit"]
        lines = [
            "# API Contract Reviewer Collection",
            "",
            f"- Collection ID: `{bundle['collection_id']}`",
            f"- Generated at: `{bundle['generated_at']}`",
            f"- Actor: `{bundle['actor']}`",
            f"- Readiness: `{bundle['readiness_status']}`",
            f"- OpenAPI route count: `{audit['openapi_route_count']}`",
            f"- Auth-protected endpoint count: `{audit['auth_protected_endpoint_count']}`",
            "",
            "## Contract Checks",
            "",
            "| Status | Category | Check | Detail |",
            "| --- | --- | --- | --- |",
            *[
                f"| `{check['status']}` | {check['category']} | {check['title']} | {check['detail']} |"
                for check in audit["checks"]
            ],
            "",
            "## Endpoint Inventory By Domain",
            "",
            *[
                f"- {domain}: `{group['count']}` endpoints, `{group['protected_count']}` protected"
                for domain, group in bundle["endpoint_inventory_grouped_by_domain"].items()
            ],
            "",
            "## Sample PowerShell Commands",
            "",
            *[f"- `{command}`" for command in bundle["sample_commands"]["powershell"]],
            "",
            "## Sample Curl Commands",
            "",
            *[f"- `{command}`" for command in bundle["sample_commands"]["curl"]],
            "",
            "## Demo Token Flow",
            "",
            *[
                f"- {item['step']}. `{item['command']}` -> `{item['expected_status']}`"
                for item in bundle["demo_token_flow"]
            ],
            "",
            "## MCP CLI Commands",
            "",
            *[f"- `{command}`" for command in bundle["mcp_cli_commands"]],
            "",
            "## Expected Status Codes",
            "",
            *[
                f"- `{item['method']} {item['path']}` with_api_key=`{item['with_api_key']}` -> `{item['expected_status']}`"
                for item in bundle["expected_status_codes"]
            ],
            "",
            "## Generated Artifact Endpoints",
            "",
            *[
                f"- {item['name']}: `{item['producer_endpoint']}` -> `{item['directory']}`"
                for item in bundle["generated_artifact_endpoints"]
            ],
            "",
            "## One-Command Verification Order",
            "",
            *[
                f"- {item['step']}. `{item['command']}` - {item['expected']}"
                for item in bundle["one_command_verification_order"]
            ],
            "",
            "## Recruiter And Engineer Explanation",
            "",
            f"- Recruiter: {bundle['recruiter_engineer_explanation']['recruiter']}",
            f"- Engineer: {bundle['recruiter_engineer_explanation']['engineer']}",
            "",
            "## Auth Notes",
            "",
            *[f"- {note}" for note in bundle["auth_notes"]],
            "",
            "## Limitations",
            "",
            *[f"- {note}" for note in bundle["limitations"]],
            "",
        ]
        return "\n".join(lines)

    def _domain_for(self, path: str) -> str:
        parts = [part for part in path.split("/") if part]
        if not parts:
            return "root"
        if parts[0] == "api":
            return "api contract"
        return parts[0].replace("-", " ")

    def _demo_service_hint(self, path: str) -> str:
        hints = {
            "/agents/run": "state.agent.run",
            "/policy/simulate": "state.policy.simulate",
            "/workflows/{template_id}/simulate": "state.workflows.simulate",
            "/conformance/report": "state.conformance.generate",
            "/evidence/export": "state.evidence.export",
            "/releases/export": "state.releases.export",
            "/ops/launch-checklist": "state.smoke.launch_checklist",
            "/reviewer/walkthrough-pack": "state.reviewer.walkthrough_pack",
            "/artifacts/readme-checklist": "state.artifacts.readme_checklist",
            "/ui/verification-pack": "state.ui_verification.verification_pack",
            "/marketplace/catalog": "state.marketplace.catalog",
            "/marketplace/rollout-pack": "state.marketplace.rollout_pack",
            "/skills/compatibility": "state.compatibility.report",
            "/skills/compatibility-pack": "state.compatibility.pack",
            "/usage/analytics": "state.usage.analytics",
            "/usage/chargeback-pack": "state.usage.chargeback_pack",
            "/reliability/skills": "state.reliability.report",
            "/reliability/pack": "state.reliability.pack",
            "/slo/report": "state.slo.report",
            "/slo/pack": "state.slo.pack",
            "/providers/readiness": "state.provider_readiness.readiness",
            "/providers/fallback-pack": "state.provider_readiness.fallback_pack",
            "/config/hygiene": "state.config_hygiene.report",
            "/config/hygiene-pack": "state.config_hygiene.pack",
            "/prompt-governance/report": "state.prompt_governance.report",
            "/prompt-governance/pack": "state.prompt_governance.pack",
            "/privacy/retention-report": "state.privacy_retention.report",
            "/privacy/retention-pack": "state.privacy_retention.pack",
            "/api/contract-audit": "state.api_contracts.contract_audit",
            "/api/reviewer-collection": "state.api_contracts.reviewer_collection",
            "/api/contract-drift-pack": "state.api_contracts.contract_drift_pack",
            "/repository/automation-plan": "state.git_readiness.automation_plan",
            "/repository/automation-pack": "state.git_readiness.automation_pack",
            "/agents/collaborate": "state.agent_collaboration.run",
            "/agents/collaboration-pack": "state.agent_collaboration.export",
            "/agents/society-eval": "state.agent_society_eval.report",
            "/agents/society-eval-pack": "state.agent_society_eval.pack",
            "/workers/runs": "state.worker_scaleout.submit_run",
            "/workers/scale-plan": "state.worker_scaleout.scale_plan",
            "/workers/runbook-pack": "state.worker_scaleout.runbook_pack",
        }
        return hints.get(path, path)

    def _expected_for_command(self, command: str) -> str:
        if "pytest" in command:
            return "All local tests pass."
        if "ruff" in command:
            return "No lint findings across app, tests, and dashboard."
        if "run_eval" in command:
            return "Golden eval and validate-only paths pass."
        if "run_conformance" in command:
            return "MCP conformance report passes for promoted skills."
        if "dashboard_smoke" in command:
            return "Dashboard API Contract tab and endpoint references are wired."
        if "app.demo" in command:
            return "Demo prints contract audit status, drift status, and Reviewer Collection path."
        if "mcp_server" in command:
            return "MCP CLI prints non-empty tools/resources/prompts JSON."
        if command.startswith("rg "):
            return "Source, docs, dashboard, tests, and scripts mention the contract surface."
        return "Generated data/api_contracts artifacts are present after POST /api/reviewer-collection."

    def _drift_markdown(self, bundle: JsonDict) -> str:
        drift = bundle["contract_drift"]
        lines = [
            "# Tool Contract Drift Pack",
            "",
            f"- Pack ID: `{bundle['pack_id']}`",
            f"- Generated at: `{bundle['generated_at']}`",
            f"- Actor: `{bundle['actor']}`",
            f"- Readiness: `{bundle['readiness_status']}`",
            f"- Score: `{bundle['score']}`",
            f"- Drift status: `{drift['status']}`",
            f"- Drift count: `{drift['drift_count']}`",
            f"- Warning count: `{drift['warning_count']}`",
            "",
            "## FastAPI Contract",
            "",
            f"- Request model: `{bundle['fastapi_contract']['request_model']}` hash `{bundle['fastapi_contract']['request_schema_hash']}`",
            f"- Response model: `{bundle['fastapi_contract']['response_model']}` hash `{bundle['fastapi_contract']['response_schema_hash']}`",
            f"- Status: `{bundle['fastapi_contract']['status']}`",
            f"- Note: {bundle['fastapi_contract']['note']}",
            "",
            "## MCP Manifest Matrix",
            "",
            "| Skill | Status | Manifest Version | MCP Version | Input Hash | Output Hash |",
            "| --- | --- | --- | --- | --- | --- |",
            *[
                f"| `{item['skill_id']}` | `{item['status']}` | `{item['manifest_version']}` | `{item.get('mcp_version') or 'n/a'}` | `{item['manifest_input_schema_hash']}` | `{item['manifest_output_schema_hash']}` |"
                for item in bundle["mcp_manifest_matrix"]
            ],
            "",
            "## Remediation Plan",
            "",
            *[
                f"- `{item['severity']}` {item['target']}: {item['reason']} Action: {item['action']}"
                for item in bundle["remediation_plan"]
            ],
            "",
            "## Governance Patterns",
            "",
            *[f"- {pattern}" for pattern in bundle["governance_patterns"]],
            "",
            "## Local Verification Commands",
            "",
            *[f"- `{command}`" for command in bundle["local_verification_commands"]],
            "",
            "## Limitations",
            "",
            *[f"- {note}" for note in bundle["limitations"]],
            "",
        ]
        return "\n".join(lines)

    def _score(self, checks: list[ApiContractCheck]) -> int:
        total = len(checks) or 1
        passed = sum(1 for check in checks if check.status == "pass")
        score = round(100 * passed / total)
        score -= min(35, 10 * sum(1 for check in checks if check.status == "fail"))
        score -= min(20, 3 * sum(1 for check in checks if check.status == "warn"))
        return max(0, min(100, score))

    def _read_text(self, path: Path) -> str:
        full_path = self._root(path)
        if not full_path.exists() or not full_path.is_file():
            return ""
        return full_path.read_text(encoding="utf-8", errors="ignore")

    def _root(self, path: Path) -> Path:
        return path if path.is_absolute() else self.repo_root / path

    def _file_row(self, path: Path) -> JsonDict:
        stat = path.stat()
        return {
            "path": str(path),
            "length": stat.st_size,
            "last_write_time": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        }
