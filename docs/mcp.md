# MCP Behavior

The project implements MCP-compatible concepts directly in Python:

- Tools are generated from enabled skill manifests.
- Disabled skills are excluded from discovery.
- Tool calls validate arguments before invocation.
- Tool results include trace IDs and metadata.
- Resources are discoverable and readable.
- Prompts are discoverable and retrievable.

## CLI Inspector

```bash
python -m app.mcp_server tools
python -m app.mcp_server resources
python -m app.mcp_server prompts
python -m app.mcp_server call --name classify_request --arguments "{\"request\":\"RFP security review\"}"
```

## Required Tools

- `summarize_document`
- `extract_entities`
- `translate_text`
- `classify_request`
- `generate_action_items`
- `search_knowledge_base`

## Required Resources

- `resource://policy/ai-governance`
- `resource://product/skill-hub`
- `resource://skill-catalog`

## Required Prompts

- `support_reply`
- `rfp_answer`
- `meeting_summary`
