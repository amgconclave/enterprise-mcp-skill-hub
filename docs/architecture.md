# Architecture

Enterprise MCP Skill Hub is organized around governed reuse. Agents do not call arbitrary prompts directly; they discover approved skills, inspect schemas, and invoke only enabled capabilities.

## Components

- `SkillRegistry` stores current manifests and version history.
- `SkillValidator` validates manifests plus invocation input and output payloads.
- `PolicyService` simulates role, environment, sensitivity, tag/provider, and action rules for skill invocation.
- `SkillInvocationService` enforces enabled status and optional policy context, calls built-in or manifest-backed skill handlers, records audit and metrics, stores policy context/decision, returns traceable invocation records, and replays prior invocations for drift checks.
- `McpToolAdapter` exposes enabled skills as MCP-shaped tools and provides resources/prompts.
- `PromptRegistry` stores reusable prompt templates for support replies, RFP answers, and meeting summaries.
- `ResourceRegistry` exposes file-backed policy/product resources, workflow templates, and a dynamic skill catalog.
- `AgentRunner` dynamically discovers MCP tools and selects multiple skills for compound tasks.
- `AgentCollaborationService` runs deterministic local multi-agent conversations with governance reviewer, intake, retrieval, synthesis, and action roles; each turn shares state, records handoff decisions, enforces existing MCP/policy/entitlement gates, tracks trace IDs and token/cost estimates, and writes Agent Collaboration Pack artifacts under `data/agent_collaboration/`.
- `AgentSocietyEvaluationService` evaluates the collaboration society with structured role, memory, MCP tool-use, handoff, and policy-gate scorecards, then writes reviewer artifacts under `data/agent_society_evals/`.
- `WorkflowTemplateService` loads approved file-backed templates, stores local review submissions, validates composition readiness, gates approval/rejection, simulates ordered skill composition with per-step policy decisions, and exports review evidence.
- `AuditService` records governance events.
- `MetricsService` aggregates invocation count, failures, latency, tokens, cost, and per-skill usage.
- `GovernanceReportService` produces readiness checks across manifest coverage, MCP discovery, resources, prompts, audit trail, and failure rate.
- `ConformanceReportService` runs contract checks for promoted skills: manifest schema, deterministic sample invocation, output schema, policy simulation, MCP exposure, and prompt/resource references.
- `EvalRegressionGateService` composes golden eval, conformance, release, reliability, and SLO signals into a local regression gate with state observations, bounded remediation steps, and ignored `data/eval_regression/` reviewer artifacts.
- `EvidenceBundleService` exports local JSON and Markdown review artifacts with governance, conformance, policy, invocation, audit, and MCP exposure evidence.
- `ReleaseService` previews promoted skill and approved workflow-template catalog changes against a local release snapshot, reports policy/conformance readiness and MCP impact, and exports governed release notes under `data/releases/`.
- `AuditQueryService` normalizes audit events, invocations, governance rows, workflow reviews, and release evidence into a deterministic filterable evidence stream for reviewers.
- `ComplianceAttestationService` exports procurement-ready Markdown and JSON attestation packs under `data/attestations/`.
- `CapacityPlanningService` forecasts local/mock skill demand from invocation history, promoted catalog rows, approved workflow templates, release/audit evidence, and mock traffic assumptions; it validates capacity guardrails and exports rollout plans under `data/capacity/`.
- `DependencyMapService` builds the cross-agent dependency graph from promoted skills, MCP tools/prompts/resources, workflow templates, release preview evidence, audit/invocation history, and capacity forecast evidence; it analyzes blast radius and exports reports under `data/dependencies/`.
- `SkillIncidentDrillService` runs deterministic local incident drills for schema, lifecycle, policy, capacity, and workflow dependency failures, then exports recovery runbooks under `data/incident_runbooks/`.
- `TenantPolicySandboxService` applies fake healthcare, fintech, public sector, and internal demo tenant profiles to promoted MCP skills and approved workflows, producing allowed, blocked, and review-required decisions plus exportable evidence under `data/tenant_sandboxes/`.
- `TenantEntitlementService` applies deterministic local tenant/user RBAC and scope policies to promoted skills, returns MCP-safe allowed tool subsets, blocks enforced denied invocations, records `entitlement.denied` audit events, and writes reviewer packs under `data/entitlement_packs/`.
- `SkillMarketplaceGovernanceService` turns the registry into a governed Skill Marketplace with lifecycle listings, deterministic Tenant Rollout eligibility scenarios, risk/review states, usage/version/MCP exposure signals, disabled-skill blocks, and rollout approval artifacts under `data/marketplace_packs/`.
- `SkillUsageAnalyticsService` builds deterministic local Skill Usage Analytics from invocation history, audit events, metrics, the skill registry, marketplace tenant scenarios, and mock token/cost fixtures; it returns budgets/anomalies and writes Cost Chargeback artifacts under `data/usage_packs/`.
- `ConfigHygieneService` checks `.env.example`, `.gitignore`, current provider mode, optional hosted-provider credential presence, and redacted suspicious secret findings; it writes Config Hygiene + Secret Rotation artifacts under ignored `data/config_hygiene/`.
- `GovernedSkillPlatformPackService` aggregates durable workflows, human-in-the-loop review, governance/conformance, provider fallback, tool governance, cost/trace signals, and handoff readiness into a platform-owner report and writes artifacts under `data/platform_packs/`.
- `ReviewSlaService` normalizes workflow reviews, marketplace approvals, and sandbox exceptions into one human-review SLA queue with escalation policy, owner actions, trace evidence, and artifacts under `data/review_sla/`.
- `WorkerScaleOutService` simulates local worker pools for governed skill execution, performs sandbox preflight before dispatch, records transparent run timelines, derives scale recommendations from capacity forecasts and run history, and writes Worker Scale-Out Runbook artifacts under `data/worker_runbooks/`.
- `TaskRunObservabilityService` normalizes invocation history, worker timelines, sandbox decisions, sandbox exception reviews, and audit-only events into a unified local task-run ledger with state observation, bounded action-loop steps, replay commands, and ignored `data/run_transparency/` artifacts.
- `PolicyReplayDriftService` replays historical policy-bearing invocations and deterministic baseline decisions against current rules, then writes HITL review evidence under ignored `data/policy_replay/`.
- `AuditIntegrityService` projects audit events and skill invocations into a deterministic SHA-256 hash chain with root hash, gap detection, replay commands, and reviewer artifacts under ignored `data/audit_integrity/`.
- `PrivacyRetentionService` scans invocation inputs, invocation outputs, audit metadata, and ad hoc JSON payloads for local PII-like patterns, returns redacted previews and retention actions, and writes Privacy Retention artifacts under `data/privacy_packs/`.
- `EnterpriseReadinessService` aggregates governance, conformance, release, audit/attestation, capacity, dependency blast radius, incident drill, tenant sandbox, and demo agent behavior into an executive scorecard and portfolio demo pack under `data/portfolio_demo/`.
- `PortfolioEvidenceService` maps recruiter JD skills to concrete implementation proof across MCP tools/resources/prompts, FastAPI APIs, manifests, governance, audit, evals, release, capacity, tenant, incident, readiness, smoke, and launch checklist surfaces, then writes an Interview Pack under `data/portfolio_packs/`.
- `SmokeMatrixService` assembles a deterministic local API smoke matrix and writes launch checklist artifacts under `data/launch_checklists/` for README and interview verification.
- `ReleaseCandidateService` composes readiness, smoke, release, docs, tests, eval, demo, MCP, endpoint, and artifact signals into a Release Candidate quality gate and writes a GitHub Publish Pack under ignored `data/release_packs/`.
- `CiDoctorService` performs deterministic local CI Doctor checks across command coverage, GitHub Actions, Docker Compose, environment examples, README/docs, ignored artifact folders, dependency manifests, local/mock provider posture, and suspicious secret scan summaries, then writes Audit Pack artifacts under ignored `data/audit_packs/`.
- `SupplyChainGovernanceService` builds a local direct-dependency SBOM from Python and TypeScript manifests, applies deterministic license/pinning/provider review policy, and writes Supply Chain artifacts under ignored `data/supply_chain/`.
- `ReviewerQuickstartService` composes smoke, portfolio, release, CI Doctor, MCP inventory, endpoint walkthrough, and artifact proof signals into `GET /reviewer/quickstart`, then writes recruiter/engineer Walkthrough Pack artifacts under ignored `data/reviewer_packs/`.
- `ArtifactInventoryService` catalogs generated MCP proof artifact directories, producer endpoints/commands, latest local files, ignored status, reviewer purpose, and freshness notes, then writes a README Checklist pack under ignored `data/artifact_indexes/`.
- `ApiContractService` builds an API Contract snapshot from FastAPI route decorators, docs/api coverage, dashboard smoke wiring, generated artifact endpoints, demo flow expectations, MCP tools/resources/prompts, and tool contract drift. It writes Reviewer Collection and Contract Drift Pack artifacts under ignored `data/api_contracts/`.
- `DashboardSmokeService` verifies Streamlit dashboard source wiring, expected reviewer views, endpoint references, generated artifact tabs, MCP proof surfaces, local commands, and ignored `data/ui_verification/` artifacts without launching a browser.
- `FinalHandoffService` runs the Portfolio README Consistency final audit across README/docs/API/demo/MCP/script/artifact/local-mock/provider claims, then writes Final Handoff Pack artifacts under ignored `data/final_handoff/`.
- `PersistenceService` saves a local JSON snapshot for demo handoff and audit inspection.
- `BaseLLMProvider`, `MockLLMProvider`, `OpenAIProvider`, and `AzureOpenAIProvider` isolate LLM execution.

## Request Flow

1. A client authenticates with `X-API-Key`.
2. The API or MCP adapter receives an invocation request.
3. `SkillRegistry` resolves the manifest.
4. If `policy_context.enforce_entitlements=true` or entitlement headers request enforcement, `TenantEntitlementService` returns a tenant/user/scope allow/deny decision before execution.
5. Denied entitlement checks create a failed invocation record, `entitlement.denied` audit event, and failure metric.
6. If `policy_context.enforce=true` or policy headers request enforcement, `PolicyService` returns an allow/deny decision before execution.
7. Denied policy checks create a failed invocation record, `policy.denied` audit event, and failure metric.
8. Disabled skills fail before execution.
9. `SkillValidator` checks input schema.
10. A built-in handler or manifest-backed mock provider executes.
11. `SkillValidator` checks output schema.
12. `AuditService` and `MetricsService` record the outcome with a trace ID.
13. Conformance and governance reports can export the current runtime posture.
14. Security review summaries and evidence bundles combine those reports with policy denials and MCP exposure.
15. Audit query and compliance attestation endpoints assemble local review evidence across audit, invocation, governance, workflow, release, and MCP sources.
16. The API returns a structured invocation record.

## Agent Collaboration Flow

1. A platform reviewer calls `POST /agents/collaborate` with a task, actor, role, environment, and data sensitivity.
2. `AgentCollaborationService` creates an in-memory shared state with the original task, tool-governance settings, memory entries, artifacts, and handoff records.
3. The governance reviewer hands off to the intake agent for `classify_request`, then intake hands off to retrieval for `search_knowledge_base`, retrieval hands off to synthesis for `summarize_document`, and synthesis hands off to the action agent for `generate_action_items` when the prompt asks for follow-up work.
4. Before each MCP tool call, the service simulates policy for the target skill and records a typed handoff decision with governance checks.
5. If policy enforcement denies the step, the collaboration stops before tool execution and returns a `needs_review` run.
6. Allowed turns call the existing MCP adapter with policy and entitlement context, then store the tool output in shared artifacts and a compact memory entry for later turns.
7. The run returns participants, turns, shared state, final output, trace IDs, latency, token usage, estimated local cost, and limitations.
8. `POST /agents/collaboration-pack` writes `agent_collaboration_pack_latest.json` and `.md` under ignored `data/agent_collaboration/` for reviewer evidence.

## Agent Society Evaluation Flow

1. A reviewer calls `GET /agents/society-eval` or `POST /agents/society-eval-pack`.
2. `AgentSocietyEvaluationService` runs a successful internal collaboration and, by default, a confidential policy-denied collaboration.
3. The service scores expected roles, shared memory entries, artifact alignment, MCP tool exposure, handoff approval, and stop-before-tool policy behavior.
4. The response is a typed structured eval result with readiness, score, recommendations, proof commands, and local/mock limitations.
5. Pack export writes `agent_society_eval_pack_latest.json` and `.md` under ignored `data/agent_society_evals/`.

## Worker Scale-Out Flow

1. A platform operator calls `POST /workers/runs` with a promoted skill, input payload, pool, priority, and sandbox enforcement flag.
2. `WorkerScaleOutService` creates a typed worker run record with a queued timeline event and audit trace.
3. If sandbox enforcement is enabled, `InvocationSandboxPolicyService` evaluates payload size, action class, endpoint, and skill risk before dispatch.
4. Denied sandbox decisions stop before skill execution and return a failed worker run with matched policy rules.
5. Allowed runs dispatch through `SkillInvocationService` using the local/mock provider and record the invocation id, invocation trace id, output, latency, metrics, and audit evidence.
6. `GET /workers/scale-plan` combines recent worker runs with capacity forecasts to show pool status, backlog by skill, and scale recommendations.
7. `POST /workers/runbook-pack` writes JSON/Markdown evidence for worker scale-out, run transparency, task sandbox, typed contracts, and structured outputs under `data/worker_runbooks/`.

## Task Run Transparency Flow

1. Existing local services continue to own invocations, worker runs, sandbox decisions, exception reviews, and audit events.
2. `GET /runs/ledger` observes those records and projects them into one typed ledger with trace ids, checkpoints, actors, risk flags, governance links, and replay commands.
3. The ledger exposes a bounded reviewer loop: observe state, verify trace coverage, review failed or denied runs, replay representative invocations, and export the pack.
4. `POST /runs/transparency-pack` writes JSON/Markdown evidence under ignored `data/run_transparency/`.
5. No hosted tracing backend, browser automation, queue, GitHub API, Azure, or OpenAI service is required.

## Policy Replay Flow

1. A reviewer calls `GET /policy/replay-drift`.
2. `PolicyReplayDriftService` reads current invocation history and selects rows that carried `policy_context`.
3. For rows with stored `policy_decision`, it re-simulates the current `PolicyService` decision and compares original versus replayed allow/deny behavior.
4. For rows with policy context but missing enforced decision evidence, it routes a `needs_evidence` item to the approval queue.
5. Fresh clones also run deterministic baseline allow/deny scenarios so reviewers can verify policy guardrails before traffic exists.
6. `POST /policy/replay-pack` writes JSON/Markdown evidence under ignored `data/policy_replay/` with drift rows, approval queue, state observations, bounded review steps, and local proof commands.

## Workflow Composition Flow

1. A client lists templates with `GET /workflows/templates`.
2. A client posts input text, role, data sensitivity, and environment to `POST /workflows/{template_id}/simulate`.
3. `WorkflowTemplateService` loads the ordered skill list and resolves each skill through `SkillRegistry`.
4. The policy service evaluates each step using the requested role, environment, and sensitivity plus the template's required role.
5. Only promoted/enabled skills are executed through the MCP adapter.
6. A denied, disabled, unpromoted, or missing skill is recorded as a blocked step and stops the workflow deterministically.
7. The result returns selected skills, step outputs, policy decisions, trace entries, final output, and blocked steps.

## Workflow Review Flow

1. A client submits a new template with `POST /workflows/templates/submit`.
2. `WorkflowTemplateService` stores the submission under `data/workflow_reviews/submitted_templates.json` with `in_review` status.
3. Validation reports the template status, required role, default sensitivity, missing skills, invalid/unpromoted skills, policy warnings, and structural errors.
4. `GET /workflows/reviews` returns the review queue with current validation results.
5. `POST /workflows/{template_id}/approve` promotes only valid submitted templates into `GET /workflows/templates` and simulation.
6. `POST /workflows/{template_id}/reject` records rejection metadata and keeps the template excluded from executable composition.
7. `POST /workflows/{template_id}/review-evidence` runs a dry-run simulation against the submitted template and writes Markdown/JSON evidence with template, validation, approval/rejection, policy warnings, and audit events.

## Replay Flow

1. A client calls `POST /invocations/{invocation_id}/replay`.
2. `SkillInvocationService` loads the original in-memory invocation record.
3. If the original used enforced policy, `PolicyService` evaluates the same policy context.
4. Policy-denied replays stop at the policy gate and return the same denied shape when rules are unchanged.
5. Successful replays rerun the current local handler with the original input, validate output schema, normalize non-business metadata, and compare original versus replay output.
6. Replay emits an `invocation.replayed` audit event with `same_output` and drift status, but does not create a new invocation metric.

## Governance Model

The project keeps governance close to the skill runtime:

- Manifests define name, description, version, provider, enabled status, tags, input schema, and output schema.
- Version history records each registration hash.
- Status changes create audit events.
- Policy simulation explains which roles can invoke which skills at `public`, `internal`, or `confidential` sensitivity.
- Tool discovery excludes disabled skills.
- Invocation history is available at `GET /invocations`.
- Deterministic replay is available at `POST /invocations/{invocation_id}/replay`.
- Metrics are available at `GET /metrics/usage`.
- Governance readiness is available at `GET /governance/report`.
- Contract conformance is available at `GET /conformance/report`.
- Workflow template composition is available at `GET /workflows/templates` and `POST /workflows/{template_id}/simulate`.
- Workflow template review is available at `POST /workflows/templates/submit`, `GET /workflows/reviews`, `POST /workflows/{template_id}/approve`, `POST /workflows/{template_id}/reject`, and `POST /workflows/{template_id}/review-evidence`.
- Security readiness is available at `GET /security/review-summary`.
- Evidence bundles are saved with `POST /evidence/export` under ignored local folder `data/evidence/`.
- Audit evidence is queryable with `POST /audit/query`.
- Compliance attestation packs are saved with `POST /compliance/attestation` under ignored local folder `data/attestations/`.
- Release previews are available at `POST /releases/preview`.
- Governed release notes are saved with `POST /releases/export` under ignored local folder `data/releases/`.
- Capacity forecasts are available at `POST /capacity/forecast`.
- Capacity guardrails are validated with `POST /capacity/guardrails`.
- Capacity plans are saved with `POST /capacity/plan-export` under ignored local folder `data/capacity/`.
- Dependency readiness is available at `GET /dependencies/map`.
- Blast radius is analyzed with `POST /dependencies/blast-radius`.
- Dependency reports are saved with `POST /dependencies/report` under ignored local folder `data/dependencies/`.
- Skill incident drills are available at `POST /incidents/drill`.
- Recovery runbooks are saved with `POST /incidents/runbook` under ignored local folder `data/incident_runbooks/`.
- Tenant policy simulations are available at `POST /tenants/policy-simulate`.
- Tenant sandbox exports are saved with `POST /tenants/sandbox-export` under ignored local folder `data/tenant_sandboxes/`.
- Tenant RBAC entitlement policies, evaluations, and reviewer packs are available through `GET /tenants/entitlements/policies`, `POST /tenants/entitlements/evaluate`, and `POST /tenants/entitlements/pack`, with pack output under ignored local folder `data/entitlement_packs/`.
- Skill Marketplace catalog is available at `GET /marketplace/catalog`.
- Tenant Rollout approval packs are saved with `POST /marketplace/rollout-pack` under ignored local folder `data/marketplace_packs/`.
- Skill Usage Analytics are available at `GET /usage/analytics`.
- Cost Chargeback Packs are saved with `POST /usage/chargeback-pack` under ignored local folder `data/usage_packs/`.
- Governed Skill Platform Pack reports are available at `GET /platform/pack`.
- Governed Skill Platform Pack artifacts are saved with `POST /platform/pack/export` under ignored local folder `data/platform_packs/`.
- Agent Collaboration runs are available at `POST /agents/collaborate`.
- Agent Collaboration Pack artifacts are saved with `POST /agents/collaboration-pack` under ignored local folder `data/agent_collaboration/`.
- Enterprise readiness is available at `GET /enterprise/readiness-scorecard`.
- Portfolio demo packs are saved with `POST /enterprise/portfolio-demo-pack` under ignored local folder `data/portfolio_demo/`.
- Portfolio Evidence indexes are returned by `GET /portfolio/evidence-index`.
- Interview Pack artifacts are saved with `POST /portfolio/interview-pack` under ignored local folder `data/portfolio_packs/`.
- API smoke readiness is available at `GET /ops/smoke-matrix`.
- Launch checklists are saved with `POST /ops/launch-checklist` under ignored local folder `data/launch_checklists/`.
- CI Doctor readiness is available at `GET /ops/ci-doctor`.
- Local CI Doctor Audit Packs are saved with `POST /ops/audit-pack` under ignored local folder `data/audit_packs/`.
- Reviewer Quickstart is available at `GET /reviewer/quickstart`.
- Reviewer Walkthrough Packs are saved with `POST /reviewer/walkthrough-pack` under ignored local folder `data/reviewer_packs/`.
- Artifact Inventory is available at `GET /artifacts/inventory`.
- README Checklist packs are saved with `POST /artifacts/readme-checklist` under ignored local folder `data/artifact_indexes/`.
- API Contract audit is available at `GET /api/contract-audit`.
- API Reviewer Collection packs are saved with `POST /api/reviewer-collection` under ignored local folder `data/api_contracts/`.
- Dashboard Smoke is available at `GET /ui/dashboard-smoke` and with `python scripts\dashboard_smoke.py`.
- UI Verification Packs are saved with `POST /ui/verification-pack` under ignored local folder `data/ui_verification/`.
- README Consistency final audits are returned by `GET /handoff/final-audit`.
- Final Handoff Packs are saved with `POST /handoff/final-pack` under ignored local folder `data/final_handoff/`.
- Release Candidate gates are returned by `GET /release/quality-gate`.
- GitHub Publish Packs are saved with `POST /release/publish-pack` under ignored local folder `data/release_packs/`.
- Workflow review evidence is saved under ignored local folder `data/workflow_reviews/`.
- Governance rows include policy access summaries and policy risk flags.
- Local snapshots are saved with `POST /snapshots/local`.

## Evidence Bundle Flow

1. A reviewer calls `POST /evidence/export`.
2. `EvidenceBundleService` records an `evidence.exported` audit event.
3. Governance and conformance reports are generated from the current local state.
4. Policy summary simulations run across registered skills, roles, and data sensitivities.
5. Denied policy attempts are collected from invocation history.
6. MCP tools, resources, and prompts are summarized.
7. The service writes `security_evidence_latest.json` and `security_evidence_latest.md` under `data/evidence/`.

## Audit Query And Attestation Flow

1. A reviewer calls `POST /audit/query` with optional filters for action/type, actor, skill id, workflow template id, status, date range, or free-text query.
2. `AuditQueryService` collects local audit events, invocation history, governance skill rows, workflow review rows, and release preview evidence.
3. The response returns matched normalized records, action/status counts, related invocations, related release/workflow evidence, trace/correlation ids, and warnings for missing optional evidence in a fresh clone.
4. A reviewer calls `POST /compliance/attestation`.
5. `ComplianceAttestationService` combines governance controls, promoted skills, MCP tools/resources/prompts, conformance status, release readiness, recent audit summary, policy examples, exclusions, verification commands, JD skills demonstrated, and five talking points.
6. The service writes `compliance_attestation_latest.json` and `compliance_attestation_latest.md` under ignored `data/attestations/`.

## Release Preview Flow

1. A platform owner calls `POST /releases/preview`.
2. `ReleaseService` builds a current release snapshot from promoted/enabled skills and approved workflow templates.
3. The service loads `data/releases/current_snapshot.json`; when it is missing, it uses a deterministic generated baseline for fresh-clone demos.
4. Skill and workflow-template hashes produce added, changed, and removed diffs.
5. Governance, conformance, workflow validation, risk flags, regression commands, MCP tools/resources/prompts affected, governance events, and excluded disabled/draft/validated artifacts are returned with release readiness.
6. `POST /releases/export` writes `release_notes_latest.json`, `release_notes_latest.md`, and the refreshed `current_snapshot.json` under ignored `data/releases/`.

## Capacity Planning Flow

1. A platform owner calls `POST /capacity/forecast` with optional forecast days, traffic multiplier, workflow-run assumptions, and direct skill-invocation assumptions.
2. `CapacityPlanningService` includes only enabled promoted skills, then reads approved workflow templates and current invocation history.
3. The service estimates per-skill invocation demand, input/output tokens, local planning cost, latency p95, top workflow drivers, recommended rate limits, and bottleneck flags.
4. Release preview and audit query evidence are attached so the forecast reflects current governance and MCP exposure.
5. `POST /capacity/guardrails` returns defaults or validates supplied max invocations/minute, token/day, latency p95, per-skill quotas, fallback behavior, and policy actions.
6. `POST /capacity/plan-export` writes `capacity_plan_latest.json` and `capacity_plan_latest.md` under ignored `data/capacity/` with forecast, guardrails, risks, rollout stages, MCP tools affected, local verification commands, JD skills demonstrated, and five interviewer talking points.

## Dependency Map And Blast Radius Flow

1. A platform owner calls `GET /dependencies/map`.
2. `DependencyMapService` includes only enabled promoted skills as active skill/tool nodes and records disabled, draft, and validated-only skills as exclusions.
3. The service adds edges from workflow templates to skills, prompts to likely skill/tool use, resources to retrieval/catalog/workflow consumers, release preview evidence to changed skills/workflows, capacity forecast evidence to demand-bearing skills/workflows, and audit history to likely agents.
4. The response returns nodes, edges, counts by node type, high-centrality skills, orphaned prompts/resources, exclusions, warnings, summary, and dependency readiness.
5. A reviewer calls `POST /dependencies/blast-radius` with one changed item: `skill_id`, `prompt_id`, `resource_uri`, or `workflow_template_id`.
6. The analyzer returns impacted skills, workflows, prompts, resources, likely agents/tool calls, capacity impact, conformance commands, risk flags, graph paths, warnings, and recommended rollout action.
7. `POST /dependencies/report` writes `dependency_report_latest.json` and `dependency_report_latest.md` under ignored `data/dependencies/` with map summary, blast-radius scenarios, rollout checklist, MCP commands, JD skills demonstrated, and five interviewer talking points.

## Skill Incident Drill And Runbook Flow

1. A platform owner calls `POST /incidents/drill` with one scenario: `schema_breakage`, `disabled_skill_invoked`, `policy_denial_spike`, `latency_capacity_breach`, or `workflow_dependency_failure`.
2. `SkillIncidentDrillService` selects a deterministic skill or workflow target and composes dependency blast radius, capacity forecast, audit query, MCP discovery, and exclusion evidence.
3. The drill response returns affected skills, workflows, prompts, resources, symptoms, severity, containment actions, rollback/canary plan, conformance/eval commands, audit evidence, capacity/dependency links, MCP capabilities affected, disabled/draft exclusions, and readiness.
4. A platform owner calls `POST /incidents/runbook` for the same or another scenario.
5. The service writes Markdown and JSON under ignored `data/incident_runbooks/` with drill summary, timeline, containment steps, owner matrix, rollback plan, verification commands, MCP capabilities affected, JD skills demonstrated, and five interviewer talking points.
6. The workflow remains local/mock and does not integrate with PagerDuty or external incident systems.

## Tenant Policy Sandbox Flow

1. A platform owner calls `POST /tenants/policy-simulate` with tenant, role, environment, and data sensitivity.
2. `TenantPolicySandboxService` evaluates only enabled promoted skills that are valid and MCP-exposed; disabled, draft, validated-only, and invalid skills are reported as exclusions.
3. Approved workflow templates are evaluated from their ordered skills plus required role and scenario sensitivity.
4. Tenant overlays for healthcare, fintech, public sector, and internal demo convert outcomes into allowed, blocked, or review-required decisions.
5. The response includes policy reasons, impacted MCP tools/resources/prompts, recommended guardrails, warnings, readiness, and excluded skills/workflows.
6. `POST /tenants/sandbox-export` writes Markdown and JSON under ignored `data/tenant_sandboxes/` with the policy matrix, scenario results, blocked/review actions, MCP impact, local verification commands, JD skills demonstrated, and five interviewer talking points.

## Tenant RBAC Entitlement Flow

1. A reviewer calls `POST /tenants/entitlements/evaluate` with tenant id, user id, role, environment, sensitivity, scopes, and optional skill ids.
2. `TenantEntitlementService` applies local wildcard and skill-specific entitlement policies for internal demo, healthcare, fintech, and public sector tenants.
3. The response returns per-skill allow/deny decisions, missing scopes, matched policies, denied skill ids, and `mcp_safe_tool_names`.
4. A skill or MCP caller can set `X-Entitlement-Enforce: true` plus tenant/user/scope headers to enforce the same decision before execution.
5. Denied entitlement calls stop before handlers/providers run, create a failed invocation, record `entitlement.denied`, and remain replayable through the invocation replay endpoint.
6. `GET /tenants/entitlements/coverage` compares promoted MCP tools against tenant exact and wildcard policies, flags wildcard-only coverage rows for review, and includes denied entitlement audit evidence.
7. `POST /tenants/entitlements/pack` and `POST /tenants/entitlements/review-pack` write Markdown and JSON under ignored `data/entitlement_packs/` with scenario matrices, coverage drift review, reviewer proof, local commands, and limitations.

## Skill Marketplace Tenant Rollout Flow

1. A reviewer calls `GET /marketplace/catalog`.
2. `SkillMarketplaceGovernanceService` lists every registered skill, including promoted, approved/validated, draft, and disabled lifecycle states.
3. The service applies deterministic Tenant Rollout scenarios for internal ops, regulated healthcare, fintech confidential production, and public-sector restricted production.
4. Each listing returns tenant eligibility, risk level, required review state, usage signals, MCP exposure state, version comparison notes, disabled-skill blocks, and coverage summary.
5. `GET /marketplace/promotion-gate/{skill_id}` observes current catalog state plus approval records before a registry mutation, then returns pass/fail checks, owner-signoff evidence, stage readiness, and remediation steps.
6. `POST /skills/{skill_id}/promote` uses that gate by default so MCP tool discovery cannot expand without marketplace approval evidence.
7. `POST /marketplace/rollout-pack` writes Markdown and JSON under ignored `data/marketplace_packs/` with rollout recommendations, tenant policy decisions, disabled-skill blocks, reviewer checklist, local proof commands, and limitations.

## Skill Usage Analytics And Chargeback Flow

1. A platform owner calls `GET /usage/analytics`.
2. `SkillUsageAnalyticsService` combines existing invocation history, audit events, metrics, registry/MCP exposure state, marketplace-style tenant scenarios, and deterministic token/cost fixture rows.
3. The response groups usage by skill, tenant/environment, agent, status, MCP exposure, and latency band, then reports token/cost estimates, budget status, anomaly flags, disabled-skill blocked events, and coverage summary.
4. `POST /usage/chargeback-pack` writes Markdown and JSON under ignored `data/usage_packs/` with usage tables, cost allocation, budget/anomaly flags, recommended controls, reviewer checklist, local proof commands, and limitations.
5. The flow is local/mock portfolio evidence; cost estimates are not provider invoices and tenant/agent labels are deterministic scenarios.

## Privacy Retention And Redaction Flow

1. A reviewer calls `GET /privacy/retention-report`.
2. `PrivacyRetentionService` scans deterministic fixtures plus live invocation inputs, outputs, and audit metadata using local regex rules for regulated identifiers, contact data, health context, and credential-like strings.
3. The response returns source records, high-risk findings, redacted previews, deletion/redaction candidates, retention policy actions, local proof commands, and limitations.
4. A reviewer calls `POST /privacy/redact` to preview redaction for an ad hoc JSON payload or `POST /privacy/retention-pack` to export reviewer evidence.
5. The service writes Markdown and JSON under ignored `data/privacy_packs/`; generated artifacts store hashes and redacted previews rather than raw sensitive values.

## Enterprise Readiness Flow

1. A reviewer calls `GET /enterprise/readiness-scorecard`.
2. `EnterpriseReadinessService` composes existing local/mock services: governance, conformance, security evidence, release preview, audit query, capacity forecast, dependency map/blast radius, incident drill, tenant sandbox, and demo agent behavior.
3. The response returns category scores, overall readiness, risks, recommended actions, artifact links, MCP capability counts, and verification commands.
4. A reviewer calls `POST /enterprise/portfolio-demo-pack`.
5. The service writes Markdown and JSON under ignored `data/portfolio_demo/` with the scorecard, architecture talking points, local demo commands, endpoint map, artifacts list, JD skills demonstrated, and five interviewer talking points.

## Portfolio Evidence Flow

1. A reviewer calls `GET /portfolio/evidence-index`.
2. `PortfolioEvidenceService` composes existing local/mock proof sources: governance, conformance, enterprise readiness, smoke matrix, release preview, capacity forecast and guardrails, tenant policy sandbox, incident drill, audit query, MCP discovery, and workflow templates.
3. The response returns a Portfolio Evidence score, JD coverage, proof matrix, MCP capability counts, artifact inventory, verification commands, and local-only summary.
4. A reviewer calls `POST /portfolio/interview-pack`.
5. The service writes Markdown and JSON under ignored `data/portfolio_packs/` with a 3-minute demo script, 8-10 technical talking points, architecture walk-through, governance/failure-mode story, verification commands, metrics/eval summary, artifact inventory, and resume/GitHub README bullets.

## Launch Checklist Flow

1. A reviewer starts the local FastAPI server and calls `GET /ops/smoke-matrix`.
2. `SmokeMatrixService` builds endpoint rows for auth/health, skills, MCP surfaces, governance, workflows, releases, capacity, tenant policy, marketplace, usage analytics, incidents, enterprise readiness, and ops.
3. The service combines live local signals from governance, conformance, release preview, capacity forecast, tenant simulation, usage analytics, incident drill, and enterprise scorecard into one smoke readiness summary.
4. A reviewer calls `POST /ops/launch-checklist`.
5. The service writes Markdown and JSON under ignored `data/launch_checklists/` with install/run commands, API smoke matrix, demo and eval commands, artifact paths, troubleshooting notes, JD skills demonstrated, and five interviewer talking points.
6. The workflow stays local/mock and does not require external model, tenant, incident, or compliance systems.

## Release Candidate Publish Flow

1. A reviewer calls `GET /release/quality-gate`.
2. `ReleaseCandidateService` composes governance, conformance, release preview, smoke matrix, enterprise readiness, endpoint inventory, MCP discovery, docs presence, verification commands, and artifact coverage into one deterministic release gate.
3. The gate returns status, score, blockers, warnings, CI/docs/test/eval/demo/MCP coverage, local runtime notes, publish readiness, endpoint inventory, MCP capability inventory, and artifact coverage.
4. A reviewer calls `POST /release/publish-pack`.
5. The service writes `publish_pack_latest.json` and `publish_pack_latest.md` under ignored `data/release_packs/`.
6. The Publish Pack includes setup/demo commands, verification commands, expected outputs, endpoint inventory, MCP capability inventory, artifact inventory, screenshot placeholders, GitHub repo checklist, commit/push notes, recruiter review notes, and known limitations.

## Local CI Doctor Audit Flow

1. A reviewer calls `GET /ops/ci-doctor`.
2. `CiDoctorService` inspects local files only: README/docs, Makefile/service command lists, `.github/workflows`, Docker Compose, `.env.example`, `.gitignore`, dependency manifests, provider config, and repo source files for suspicious secret patterns.
3. The response returns structured checks, command checks, dependency inventory, redacted secret scan summary, local runtime notes, and a publish-safety checklist.
4. A reviewer calls `POST /ops/audit-pack`.
5. The service writes `audit_pack_latest.json` and `audit_pack_latest.md` under ignored `data/audit_packs/`.
6. The Audit Pack includes CI Doctor results, dependency inventory, secret scan summary, local verification commands, publish-safety checklist, remediation notes, recruiter/interviewer explanation, and limitations.
7. The workflow stays deterministic and local/mock; it does not call external CI, package registry, source-control, or secret-scanning services.

## Config Hygiene Flow

1. A platform reviewer calls `GET /config/hygiene` before enabling OpenAI, Azure OpenAI, or shared deployment.
2. `ConfigHygieneService` parses `.env.example`, checks process environment variable presence without exporting secret values, validates `.gitignore` coverage for local config/artifacts, and scans text-like repo files for suspicious literal credentials.
3. The response returns redacted variable records, provider approval gate, gitignore checks, redacted findings, rotation steps, local proof commands, and limitations.
4. A reviewer calls `POST /config/hygiene-pack`.
5. The service writes `config_hygiene_pack_latest.json` and `.md` under ignored `data/config_hygiene/`.
6. The pack uses governance, provider-flexibility, and tool-governance patterns: mock remains the default acceptance path, hosted-provider enablement is approval-gated, and generated artifacts never contain raw secret values.

## Supply Chain SBOM Flow

1. A reviewer calls `GET /supply-chain/report`.
2. `SupplyChainGovernanceService` parses `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, and `typescript-bridge/package.json`.
3. The response returns manifest hashes, direct dependency rows, local license policy decisions, pinning signals, optional external-provider dependency gates, approval requirements, local proof commands, and limitations.
4. A reviewer calls `POST /supply-chain/pack`.
5. The service writes `supply_chain_pack_latest.json` and `.md` under ignored `data/supply_chain/`.
6. The workflow is deterministic and local/mock; it does not resolve transitive dependencies or query PyPI/npm.

## Reviewer Quickstart Flow

1. A GitHub reviewer calls `GET /reviewer/quickstart` after bootstrapping `$headers` from `POST /auth/demo-token`.
2. `ReviewerQuickstartService` composes existing local signals from smoke matrix, portfolio evidence, release quality gate, CI Doctor, and MCP discovery.
3. The response returns exact setup commands, one-command demo, verification commands, endpoint walkthrough order, MCP command walkthrough, artifact proof map, expected outputs, troubleshooting, role-specific reviewer notes, and a local/mock summary count.
4. A reviewer calls `POST /reviewer/walkthrough-pack`.
5. The service writes `walkthrough_pack_latest.json` and `walkthrough_pack_latest.md` under ignored `data/reviewer_packs/`.
6. The Walkthrough Pack includes a recruiter-friendly story, engineer deep-dive path, command checklist, API/MCP proof tour, artifacts to inspect, limitations, and GitHub README blurb.
7. The workflow is deterministic and local/mock; generated proof files are inspectable artifacts, not source-controlled outputs.

## Artifact Inventory Flow

1. A GitHub reviewer calls `GET /artifacts/inventory`.
2. `ArtifactInventoryService` walks a deterministic catalog of MCP-specific artifact families: UI verification, portfolio demo, portfolio packs, release packs, audit packs, reviewer packs, launch checklists, security evidence, attestations, releases, capacity, dependencies, incidents, tenant sandboxes, workflow reviews, conformance outputs, governance outputs, and artifact indexes.
3. For each row it resolves the local directory, collects latest files when present, checks `.gitignore`, attaches the producer endpoint or command, and returns reviewer purpose plus freshness notes.
4. A reviewer calls `POST /artifacts/readme-checklist`.
5. The service writes `readme_checklist_latest.json` and `readme_checklist_latest.md` under ignored `data/artifact_indexes/`.
6. The README Checklist pack includes Artifact Inventory rows, README badge suggestions, local commands, a reviewer proof checklist, cleanup/regeneration notes, and limitations.

## API Contract Flow

1. A reviewer calls `GET /api/contract-audit` after the repo has API routes, docs, dashboard smoke wiring, demo output, MCP CLI commands, and generated artifact producers wired.
2. `ApiContractService` parses FastAPI decorators as the local OpenAPI inventory and counts endpoints protected by the `X-API-Key` dependency.
3. The audit compares important endpoints against `docs/api.md`, dashboard smoke references, generated artifact producer endpoints, demo flow expectations, and MCP tools/resources/prompts.
4. A reviewer calls `POST /api/reviewer-collection`.
5. The service writes `reviewer_collection_latest.json` and `reviewer_collection_latest.md` under ignored `data/api_contracts/`.
6. The Reviewer Collection includes endpoint inventory by domain, MCP inventory, sample `X-API-Key` commands, demo-token flow, expected status codes, generated artifact endpoints, verification order, recruiter/engineer explanation, and local-only limitations.

## Dashboard Smoke And UI Verification Flow

1. A GitHub reviewer runs `python scripts\dashboard_smoke.py` or calls `GET /ui/dashboard-smoke`.
2. `DashboardSmokeService` reads local source files only: `dashboard/streamlit_app.py`, `app/main.py`, `.gitignore`, and the smoke script path.
3. The response reports pass/fail checks for expected dashboard views, `/ui/*` endpoint references, generated artifact tabs, MCP Inspector proof surfaces, local run commands, and limitations.
4. A reviewer calls `POST /ui/verification-pack` or exports from the Streamlit `UI Verification` view.
5. The service writes `ui_verification_pack_latest.json` and `ui_verification_pack_latest.md` under ignored `data/ui_verification/`.
6. The pack includes Dashboard Smoke results, the Streamlit run command, reviewer checklist, screenshot placeholders, troubleshooting, and limitations while staying local/mock and browser-free.

## Final Handoff Flow

1. A reviewer calls `GET /handoff/final-audit` after the repo has docs, API routes, demo output, MCP CLI commands, and generated artifact folders wired.
2. `FinalHandoffService` inspects local source files and docs for README Consistency markers: final endpoints, docs/api coverage, architecture/evaluation coverage, demo output claims, script presence, dashboard smoke command presence, `data/final_handoff/` docs/ignore status, MCP tools/resources/prompts clarity, local/mock limitations, and optional Azure/OpenAI notes.
3. The response includes structured checks plus endpoint, MCP, and artifact inventory summaries so reviewers can compare claims against implementation.
4. A reviewer calls `POST /handoff/final-pack`.
5. The service writes `final_handoff_pack_latest.json` and `final_handoff_pack_latest.md` under ignored `data/final_handoff/`.
6. The Final Handoff Pack includes exact clone/run commands, end-to-end verification order, endpoint/MCP/artifact summaries, dashboard smoke summary, eval/conformance proof summary, a recruiter-facing final README blurb, and local/mock limitations. No Azure, OpenAI, external CI, browser, or SaaS service is required for acceptance.
