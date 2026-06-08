# Architecture

Enterprise MCP Skill Hub is organized around governed service boundaries instead of route-level business logic.

## Core Services

- `SkillRegistry`: stores current skill manifests, enabled status, and version history.
- `SkillValidator`: validates manifests and invocation payloads against the supported JSON schema subset.
- `SkillInvocationService`: invokes built-in skill handlers, blocks disabled skills, records trace IDs, audit events, metrics, and token usage.
- `McpToolAdapter`: maps enabled skills into MCP-compatible tool definitions and handles tool calls.
- `PromptRegistry`: exposes reusable prompt definitions for support replies, RFP answers, and meeting summaries.
- `ResourceRegistry`: exposes fake policy docs, product docs, and a dynamic skill catalog resource.
- `AgentRunner`: discovers available skills and invokes multiple tools for compound tasks.
- `AuditService`: records registration, validation, status changes, and invocations.
- `MetricsService`: aggregates latency, tokens, estimated cost, provider, and failure counts.

## Runtime Flow

1. A skill is defined by YAML or JSON manifest.
2. The registry stores the manifest and version metadata.
3. The MCP adapter exposes only enabled skills as tools.
4. Invocation payloads are validated before handlers run.
5. Results include trace metadata and are captured in audit and metrics services.
6. The demo agent uses discovery to select multiple skills for a compound task.

## Persistence

The current implementation uses in-process local state to keep the demo lightweight and deterministic. Models are persistence-friendly and can be backed by SQLite, Postgres, or a JSON store without changing the API contracts.

## Provider Boundary

`BaseLLMProvider` isolates model access. `MockLLMProvider` is the default. `OpenAIProvider` and `AzureOpenAIProvider` are optional and only require credentials when selected.
