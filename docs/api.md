# API

Protected endpoints require `X-API-Key: dev-local-token` by default. `POST /auth/demo-token` is intentionally unauthenticated for local demos.

## Required Endpoints

- `POST /auth/demo-token` - returns the local demo token and header name.
- `GET /health` - returns service health, provider mode, MCP mode, and version.
- `GET /skills` - lists registered skills.
- `POST /skills/register` - registers a `SkillManifest`.
- `POST /skills/validate` - validates a raw manifest payload without registration.
- `POST /skills/{skill_id}/invoke` - invokes an enabled skill with schema validation.
- `PATCH /skills/{skill_id}/status` - enables or disables a skill.
- `GET /skills/{skill_id}/versions` - returns registration history for a skill.
- `POST /agents/run` - runs the demo agent against dynamically discovered skills.
- `GET /audit/events` - returns governance audit events.
- `GET /metrics/usage` - returns usage summary.
- `GET /invocations` - returns invocation history.

## MCP Utility Endpoints

- `GET /mcp/tools`
- `POST /mcp/tools/{tool_name}/call`
- `GET /mcp/resources`
- `GET /mcp/resources/read?uri=...`
- `GET /mcp/prompts`

## Example

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/skills -Headers $headers
Invoke-RestMethod http://localhost:8000/skills/summarize_document/invoke `
  -Headers $headers `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"input":{"text":"Atlas Labs needs approved MCP tools and audit logs."}}'
```

