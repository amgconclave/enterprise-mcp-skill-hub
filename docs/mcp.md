# MCP Compatibility

This repo is designed to run locally even when the official MCP Python SDK is unavailable. The `McpToolAdapter` implements a clean MCP-compatible layer with protocol-shaped discovery and invocation payloads.

## Tools

Enabled skill manifests are exposed as tools:

```json
{
  "name": "summarize_document",
  "description": "Summarize document text or a resource URI into a concise summary and key points.",
  "input_schema": {"type": "object", "properties": {}},
  "output_schema": {"type": "object", "properties": {}},
  "annotations": {"version": "1.0.0", "tags": ["summarization"], "provider": "mock"}
}
```

Disabled skills do not appear in `list_tools()` and fail if called directly.

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
```

The HTTP endpoints under `/mcp/*` expose the same adapter behavior for dashboard and integration testing.

