# AI Governance Policy

Fictional policy for local demos.

- Approved skills must have a manifest, owner, version, input schema, output schema, and enabled status.
- Agents may only invoke enabled skills exposed through the MCP tool adapter.
- Each invocation must create a trace ID, audit event, latency metric, token usage record, and cost estimate.
- Production providers require security review before OpenAI or Azure OpenAI credentials are enabled.
