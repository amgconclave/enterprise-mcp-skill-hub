# API

All protected endpoints require:

```text
X-API-Key: dev-local-token
```

## Endpoints

- `POST /auth/demo-token`: returns the local demo token.
- `GET /health`: returns status, provider mode, MCP mode, and version.
- `GET /skills`: lists registered skills.
- `POST /skills/register`: registers a `SkillManifest`.
- `POST /skills/validate`: validates a manifest without registering it.
- `POST /skills/{skill_id}/invoke`: invokes an enabled skill.
- `PATCH /skills/{skill_id}/status`: enables or disables a skill.
- `GET /skills/{skill_id}/versions`: lists skill version history.
- `POST /agents/run`: runs the demo agent.
- `GET /audit/events`: returns audit events.
- `GET /metrics/usage`: returns usage summary.
- `GET /mcp/tools`: lists enabled MCP-compatible tools.
- `POST /mcp/tools/{tool_name}/call`: invokes a tool through the MCP adapter.
- `GET /mcp/resources`: lists MCP-compatible resources.
- `GET /mcp/resources/read?uri=...`: reads a resource.
- `GET /mcp/prompts`: lists prompt templates.

## Example

```bash
curl -X POST http://localhost:8000/agents/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-local-token" \
  -d "{\"prompt\":\"Summarize this RFP request, search policy context, and create action items.\"}"
```
