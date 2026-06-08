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

Promotion is handled through `POST /skills/{skill_id}/promote`, which validates the manifest, marks it promoted/enabled, and records `skill.promoted` in the audit log.

## Policy Enforcement

MCP tool calls are permissive by default for local compatibility. Callers can pass a policy context with `enforce=true` to require an allow/deny policy decision before execution. The local rules cover `admin`, `reviewer`, `agent`, and `viewer` roles; `public`, `internal`, and `confidential` data sensitivity; environment; requested action; skill tags; and provider.

Confidential invocation is allowed for `admin` and `reviewer`, and denied for `agent` and `viewer`. Denied calls return a failed MCP-shaped payload and record a `policy.denied` audit event.

## Resources

Resources include file-backed sample policy/product docs plus a dynamic skill catalog:

- `resource://policy/ai-governance`
- `resource://policy/vendor-risk`
- `resource://product/skill-hub`
- `resource://skill-catalog`

## Prompts

Reusable governed prompts:

- `support_reply`
- `rfp_answer`
- `meeting_summary`

## CLI Inspector

```powershell
python -m app.mcp_server tools
python -m app.mcp_server resources
python -m app.mcp_server prompts
python -m app.mcp_server call --name search_knowledge_base --arguments "{\"query\":\"governance audit policy\",\"limit\":2}"
python -m app.mcp_server call --name search_knowledge_base --arguments "{\"query\":\"confidential policy\",\"limit\":2}" --role viewer --data-sensitivity confidential --enforce-policy
```

The HTTP endpoints under `/mcp/*` expose the same adapter behavior for dashboard and integration testing.
