# Architecture

Enterprise MCP Skill Hub is organized around governed reuse. Agents do not call arbitrary prompts directly; they discover approved skills, inspect schemas, and invoke only enabled capabilities.

## Components

- `SkillRegistry` stores current manifests and version history.
- `SkillValidator` validates manifests plus invocation input and output payloads.
- `SkillInvocationService` enforces enabled status, calls built-in or manifest-backed skill handlers, records audit and metrics, and returns traceable invocation records.
- `McpToolAdapter` exposes enabled skills as MCP-shaped tools and provides resources/prompts.
- `PromptRegistry` stores reusable prompt templates for support replies, RFP answers, and meeting summaries.
- `ResourceRegistry` exposes file-backed policy/product resources and a dynamic skill catalog.
- `AgentRunner` dynamically discovers MCP tools and selects multiple skills for compound tasks.
- `AuditService` records governance events.
- `MetricsService` aggregates invocation count, failures, latency, tokens, cost, and per-skill usage.
- `BaseLLMProvider`, `MockLLMProvider`, `OpenAIProvider`, and `AzureOpenAIProvider` isolate LLM execution.

## Request Flow

1. A client authenticates with `X-API-Key`.
2. The API or MCP adapter receives an invocation request.
3. `SkillRegistry` resolves the manifest.
4. Disabled skills fail before execution.
5. `SkillValidator` checks input schema.
6. A built-in handler or manifest-backed mock provider executes.
7. `SkillValidator` checks output schema.
8. `AuditService` and `MetricsService` record the outcome with a trace ID.
9. The API returns a structured invocation record.

## Governance Model

The project keeps governance close to the skill runtime:

- Manifests define name, description, version, provider, enabled status, tags, input schema, and output schema.
- Version history records each registration hash.
- Status changes create audit events.
- Tool discovery excludes disabled skills.
- Invocation history is available at `GET /invocations`.
- Metrics are available at `GET /metrics/usage`.

