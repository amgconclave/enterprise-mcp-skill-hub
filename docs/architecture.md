# Architecture

Enterprise MCP Skill Hub is organized around governed reuse. Agents do not call arbitrary prompts directly; they discover approved skills, inspect schemas, and invoke only enabled capabilities.

## Components

- `SkillRegistry` stores current manifests and version history.
- `SkillValidator` validates manifests plus invocation input and output payloads.
- `PolicyService` simulates role, environment, sensitivity, tag/provider, and action rules for skill invocation.
- `SkillInvocationService` enforces enabled status and optional policy context, calls built-in or manifest-backed skill handlers, records audit and metrics, and returns traceable invocation records.
- `McpToolAdapter` exposes enabled skills as MCP-shaped tools and provides resources/prompts.
- `PromptRegistry` stores reusable prompt templates for support replies, RFP answers, and meeting summaries.
- `ResourceRegistry` exposes file-backed policy/product resources and a dynamic skill catalog.
- `AgentRunner` dynamically discovers MCP tools and selects multiple skills for compound tasks.
- `AuditService` records governance events.
- `MetricsService` aggregates invocation count, failures, latency, tokens, cost, and per-skill usage.
- `GovernanceReportService` produces readiness checks across manifest coverage, MCP discovery, resources, prompts, audit trail, and failure rate.
- `PersistenceService` saves a local JSON snapshot for demo handoff and audit inspection.
- `BaseLLMProvider`, `MockLLMProvider`, `OpenAIProvider`, and `AzureOpenAIProvider` isolate LLM execution.

## Request Flow

1. A client authenticates with `X-API-Key`.
2. The API or MCP adapter receives an invocation request.
3. `SkillRegistry` resolves the manifest.
4. If `policy_context.enforce=true` or policy headers request enforcement, `PolicyService` returns an allow/deny decision before execution.
5. Denied policy checks create a failed invocation record, `policy.denied` audit event, and failure metric.
6. Disabled skills fail before execution.
7. `SkillValidator` checks input schema.
8. A built-in handler or manifest-backed mock provider executes.
9. `SkillValidator` checks output schema.
10. `AuditService` and `MetricsService` record the outcome with a trace ID.
11. Governance reports and local snapshots can export the current runtime posture.
12. The API returns a structured invocation record.

## Governance Model

The project keeps governance close to the skill runtime:

- Manifests define name, description, version, provider, enabled status, tags, input schema, and output schema.
- Version history records each registration hash.
- Status changes create audit events.
- Policy simulation explains which roles can invoke which skills at `public`, `internal`, or `confidential` sensitivity.
- Tool discovery excludes disabled skills.
- Invocation history is available at `GET /invocations`.
- Metrics are available at `GET /metrics/usage`.
- Governance readiness is available at `GET /governance/report`.
- Governance rows include policy access summaries and policy risk flags.
- Local snapshots are saved with `POST /snapshots/local`.
