# MCP Compatibility

This repo is designed to run locally even when the official MCP Python SDK is unavailable. The `McpToolAdapter` implements a clean MCP-compatible layer with protocol-shaped discovery and invocation payloads.

## Tools

Only skills that are both `enabled=true` and `status=promoted` are exposed as tools:

```json
{
  "name": "summarize_document",
  "description": "Summarize document text or a resource URI into a concise summary and key points.",
  "input_schema": {"type": "object", "properties": {}},
  "output_schema": {"type": "object", "properties": {}},
  "annotations": {"version": "1.0.0", "tags": ["summarization"], "provider": "mock", "status": "promoted"}
}
```

Draft, validated, disabled, or schema-invalid skills do not appear in `list_tools()` and fail if called directly through the MCP adapter. The demo agent selects from `list_tools()`, so it cannot use unpromoted skills.

Promotion is handled through `POST /skills/{skill_id}/promote`, which validates the manifest, checks the marketplace promotion gate by default, marks it promoted/enabled, and records `skill.promoted` in the audit log. `GET /marketplace/promotion-gate/{skill_id}` exposes the pre-mutation evidence: schema readiness, tenant policy result, risk level, approval record, owner signoff, and stage gate.

## Policy Enforcement

MCP tool calls are permissive by default for local compatibility. Callers can pass a policy context with `enforce=true` to require an allow/deny policy decision before execution. The local rules cover `admin`, `reviewer`, `agent`, and `viewer` roles; `public`, `internal`, and `confidential` data sensitivity; environment; requested action; skill tags; and provider.

Confidential invocation is allowed for `admin` and `reviewer`, and denied for `agent` and `viewer`. Denied calls return a failed MCP-shaped payload and record a `policy.denied` audit event.

## Tenant RBAC Entitlements

MCP tool calls can also enforce tenant/user entitlements with `enforce_entitlements=true`. The local entitlement pack evaluates tenant id, user id, user scopes, role, environment, sensitivity, and skill id before execution. Denied calls return the normal failed MCP-shaped payload, store a failed invocation row, and record `entitlement.denied` with the decision metadata.

`POST /tenants/entitlements/evaluate` returns `mcp_safe_tool_names`, the set of promoted and schema-valid MCP tools allowed for a specific tenant/user context. `POST /tenants/entitlements/pack` writes reviewer evidence under `data/entitlement_packs/`.

## Resources

Resources include file-backed sample policy/product docs plus a dynamic skill catalog:

- `resource://policy/ai-governance`
- `resource://policy/vendor-risk`
- `resource://product/skill-hub`
- `resource://workflow-templates`
- `resource://skill-catalog`

## Prompts

Reusable governed prompts:

- `support_reply`
- `rfp_answer`
- `meeting_summary`
- `workflow_composition`

Workflow templates are not exposed as executable MCP tools. They are exposed as a resource and prompt pattern so agent builders can inspect reusable compositions while the simulator still enforces promoted/enabled tool execution through the local MCP adapter.

Submitted workflow templates go through the local review queue before they become executable compositions. `GET /workflows/reviews` shows validation status, missing/invalid skills, and policy warnings; `POST /workflows/{template_id}/approve` makes a valid submission available to `GET /workflows/templates` and simulation; rejected or in-review templates remain excluded from executable composition. `POST /workflows/{template_id}/review-evidence` exports JSON/Markdown proof under `data/workflow_reviews/`.

## CLI Inspector

```powershell
python -m app.mcp_server tools
python -m app.mcp_server resources
python -m app.mcp_server prompts
python -m app.mcp_server call --name search_knowledge_base --arguments "{\"query\":\"governance audit policy\",\"limit\":2}"
python -m app.mcp_server call --name search_knowledge_base --arguments "{\"query\":\"confidential policy\",\"limit\":2}" --role viewer --data-sensitivity confidential --enforce-policy
python -m app.mcp_server call --name translate_text --arguments "{\"text\":\"Patient follow-up note\",\"target_language\":\"Spanish\"}" --role agent --tenant-id healthcare --user-id care-agent --user-scopes skill.invoke,tenant.healthcare --enforce-entitlements
```

The HTTP endpoints under `/mcp/*` expose the same adapter behavior for dashboard and integration testing.

`GET /runtime/demo-readiness`, `POST /runtime/demo-pack`, and `python scripts\runtime_check.py` include the same MCP CLI verification order so a fresh-clone reviewer can prove tools, resources, and prompts before or after starting the FastAPI and Streamlit demo runtime. The generated Runtime Demo Server Pack is written under ignored `data/runtime_packs/`.

## Security Evidence

`POST /evidence/export` records MCP exposure in the security evidence bundle: tool names, resource URIs, prompt ids, counts, and the skills excluded from MCP discovery because they are disabled, draft, validated-only, or otherwise not promoted. This gives review boards a local artifact proving that agents only discover promoted and enabled tools.

`POST /compliance/attestation` repeats that MCP exposure proof in a broader Compliance Attestation Pack under `data/attestations/`. The pack lists every currently discoverable MCP tool, resource, and prompt, and separately lists disabled, draft, and validated-only skills as exclusions instead of promoted capabilities.

`POST /audit/query` can filter MCP-adjacent evidence by skill id, workflow template id, action, type, actor, status, date range, or free-text query. Results include trace IDs, related invocations, release artifact availability, workflow review evidence, and warnings when a fresh clone has not generated optional evidence yet.

## Release Preview MCP Impact

`POST /releases/preview` and `POST /releases/export` include an MCP impact section for release governance. The release preview lists all current tool names, resource URIs, and prompt ids, then narrows the affected set to changed promoted skills and approved workflow templates.

Skill changes affect `resource://skill-catalog`; workflow template changes affect `resource://workflow-templates`; knowledge-base changes also flag related policy resources. Prompt impact is mapped for common compositions such as `meeting_summary`, `rfp_answer`, and `support_reply`.

## Capacity Planning MCP Impact

`POST /capacity/forecast`, `POST /capacity/guardrails`, and `POST /capacity/plan-export` plan only for enabled promoted MCP tools. Draft, validated-only, disabled, and schema-invalid skills are listed as exclusions rather than demand-bearing capabilities.

The capacity forecast reports `mcp_tools_affected`, per-skill demand, top approved workflow drivers, token/latency/cost estimates, risk flags, and recommended rate limits. The export writes JSON/Markdown under `data/capacity/` so platform owners can review MCP tool capacity before allowing broader agent discovery.

## Dependency Map MCP Impact

`GET /dependencies/map` builds a deterministic local graph from promoted skills, MCP tool exposure, prompts, resources, workflow templates, release preview evidence, audit/invocation history, and capacity forecast evidence. Draft, validated-only, disabled, and schema-invalid skills are excluded from active skill/tool nodes and listed as exclusions.

`POST /dependencies/blast-radius` accepts a changed `skill_id`, `prompt_id`, `resource_uri`, or `workflow_template_id` and returns impacted MCP tools, prompts, resources, workflows, likely agents/tool calls, capacity impact, conformance commands, risk flags, and rollout action.

`POST /dependencies/report` writes JSON/Markdown under `data/dependencies/` with map summary, blast-radius scenarios, rollout checklist, MCP commands, JD skills demonstrated, and five interviewer talking points.

## Incident Drill MCP Impact

`POST /incidents/drill` runs local reliability scenarios against MCP-facing skills and workflows. The response includes `mcp_capabilities_affected` with tools, workflows, prompts, resources, and likely tool calls, plus capacity/dependency links and disabled/draft exclusions.

`POST /incidents/runbook` writes JSON/Markdown under `data/incident_runbooks/`. The runbook includes the affected MCP capabilities, containment steps, rollback/canary plan, conformance/eval commands, owner matrix, JD skills demonstrated, and five interviewer talking points. It is intentionally local/mock and does not call external incident tooling.

## Tenant Policy Sandbox MCP Impact

`POST /tenants/policy-simulate` evaluates fake tenant policy profiles for `healthcare`, `fintech`, `public_sector`, and `internal_demo` against the active promoted MCP tool catalog and approved workflow templates. The response separates allowed, blocked, and review-required skills/workflows and reports impacted MCP tools, resources, and prompts.

`POST /tenants/sandbox-export` writes JSON/Markdown under `data/tenant_sandboxes/` with the tenant policy matrix, scenario results, blocked/review actions, MCP impact, local verification commands, JD skills demonstrated, and five interviewer talking points. Draft, disabled, validated-only, and schema-invalid skills remain excluded from tenant decisions and are reported as exclusions.

## Tenant RBAC Entitlement MCP Impact

`POST /tenants/entitlements/evaluate` computes tenant/user/scope decisions for promoted MCP skills and returns `mcp_safe_tool_names`, which is the allowed subset after entitlement checks. `GET /tenants/entitlements/coverage` compares every promoted MCP tool against tenant exact and wildcard entitlement policies, flags wildcard-only rows for review, and includes denied entitlement audit evidence. `GET /tenants/entitlements/access-review` adds privileged-policy rows, wildcard exposure, denied-audit pressure, and break-glass drill outcomes. `POST /tenants/entitlements/pack`, `POST /tenants/entitlements/review-pack`, and `POST /tenants/entitlements/access-review-pack` write JSON/Markdown under `data/entitlement_packs/` with scenario matrices, denied skill ids, MCP-safe tool names, coverage review rows, bounded remediation steps, reviewer proof, and local-only limitations.

When callers pass `X-Entitlement-Enforce: true` on `/skills/{skill_id}/invoke` or `/mcp/tools/{tool_name}/call`, the same entitlement gate runs before skill execution. Denied calls are MCP-safe because they return a failed payload instead of executing the tool and record `entitlement.denied` for audit review.

Break-glass scopes are modeled as a review drill, not a runtime bypass. The access review pack proves emergency scopes still deny unless a normal exact entitlement policy grants the skill.

## Skill Marketplace Tenant Rollout

`GET /marketplace/catalog` uses the same MCP exposure rules as tool discovery, but it keeps non-exposed draft, approved/validated, and disabled skills visible as governed marketplace listings. Each listing reports version history, Tenant Rollout eligibility for internal ops, regulated healthcare, fintech/confidential, and public-sector restricted scenarios, risk level, required review state, usage signals, MCP exposure state, and version comparison notes.

`POST /marketplace/rollout-pack` writes JSON/Markdown under `data/marketplace_packs/` with rollout recommendations, tenant policy decisions, disabled-skill blocks, reviewer checklist, local proof commands, and limitations. Disabled skills cannot roll out or invoke, and they remain hidden from `GET /mcp/tools` until re-enabled and promoted.

`GET /marketplace/promotion-gate/{skill_id}` is the registry mutation guard for draft or validated skills. It reads current catalog state and approval records, then returns `can_promote`, failed/warning check IDs, remediation steps, architecture patterns, and proof commands. `POST /skills/{skill_id}/promote` uses this gate by default so MCP discovery cannot be widened without owner-signoff evidence.

## Skill Usage Analytics MCP Exposure

`GET /usage/analytics` reports usage by MCP exposure state alongside skill, tenant/environment, agent, status, latency band, token/cost estimate, budget status, anomaly flags, and disabled-skill blocked events. The deterministic fixtures cover all built-in skills and include a blocked disabled-skill event so reviewers can see how hidden MCP tools are handled.

`POST /usage/chargeback-pack` writes JSON/Markdown under `data/usage_packs/` with usage tables, cost allocation, budget/anomaly flags, recommended controls, reviewer checklist, local proof commands, and limitations. Cost estimates are local/mock chargeback evidence, not provider invoices.

## Enterprise Readiness MCP Counts

`GET /enterprise/readiness-scorecard` includes `mcp_capability_counts` for the current tool, resource, and prompt catalog. This lets an executive or interviewer see exactly how many MCP capabilities are exposed while reviewing governance, conformance, release, audit, capacity, dependency, incident, tenant, and demo-agent readiness.

`POST /enterprise/portfolio-demo-pack` writes the same scorecard into `data/portfolio_demo/` along with local demo commands, endpoint map, artifact list, JD skills demonstrated, and five interviewer talking points. The pack is local/mock only and does not expose disabled, draft, or validated-only skills as MCP tools.

## Contract Conformance

`GET /conformance/report` and `python -m app.evals.run_conformance` prove that each promoted MCP tool is still contract-ready:

- Manifest schemas validate.
- A deterministic sample invocation passes.
- The returned output conforms to the declared output schema.
- The policy simulator allows a local internal agent invocation.
- The promoted skill appears in MCP tool discovery.
- Related prompt and resource references are listed when relevant.

This makes MCP exposure auditable: a skill is not just discoverable, it has a current local contract check attached to it.

## Final Handoff MCP Clarity

`GET /handoff/final-audit` includes README Consistency checks for MCP tools, resources, and prompts. It verifies that the local proof commands stay discoverable:

```powershell
python -m app.mcp_server tools
python -m app.mcp_server resources
python -m app.mcp_server prompts
```

`POST /handoff/final-pack` writes the MCP inventory summary into ignored `data/final_handoff/final_handoff_pack_latest.json` and `.md` alongside endpoint and artifact summaries. This is local/mock proof only; no Azure, OpenAI, or official MCP SDK is required for the handoff acceptance path.

## API Contract MCP Reviewer Collection

`GET /api/contract-audit` includes MCP tools/resources/prompts inventory and verifies the local proof commands stay aligned with FastAPI endpoints, dashboard smoke, docs/api, generated artifacts, and demo flow expectations.

`POST /api/reviewer-collection` writes the MCP Reviewer Collection into ignored `data/api_contracts/reviewer_collection_latest.json` and `.md`. The pack includes MCP CLI commands, sample `X-API-Key` API calls, generated artifact endpoints, expected status codes, auth notes, and recruiter/engineer explanations for fresh-clone review.

`POST /api/contract-drift-pack` writes `contract_drift_pack_latest.json` and `.md` in the same folder. It fingerprints promoted manifest schemas, MCP tool schemas, MCP version annotations, registry manifest hashes, and the generic FastAPI invocation contract so reviewers can spot stale tool contracts before agents discover them. The remediation section follows tool registry and tool governance patterns: manifests are the source of truth, MCP exposure is derived from promoted manifests, and every drift row has a specific action.
