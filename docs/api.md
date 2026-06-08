# API

Protected endpoints require `X-API-Key: dev-local-token` by default. `POST /auth/demo-token` is intentionally unauthenticated for local demos.

## Required Endpoints

- `POST /auth/demo-token` - returns the local demo token and header name.
- `GET /health` - returns service health, provider mode, MCP mode, and version.
- `GET /skills` - lists registered skills.
- `POST /skills/register` - registers a valid `SkillManifest`; if no lifecycle status is supplied, it is stored as `validated`.
- `POST /skills/validate` - validates a raw manifest payload without registration.
- `POST /policy/simulate` - returns an allow/deny decision, reasons, and matched rules for role, environment, data sensitivity, skill tags/provider, and requested action.
- `POST /skills/{skill_id}/promote` - validates the registered manifest, marks it `promoted`, sets `enabled=true`, and records an audit event.
- `POST /skills/{skill_id}/invoke` - invokes an enabled skill with schema validation; optional policy context can enforce role/data access before execution.
- `PATCH /skills/{skill_id}/status` - enables/promotes or disables a skill for backward-compatible admin flows.
- `GET /skills/{skill_id}/versions` - returns registration history for a skill.
- `POST /agents/run` - runs the demo agent against dynamically discovered skills.
- `GET /audit/events` - returns governance audit events.
- `GET /metrics/usage` - returns usage summary.
- `GET /invocations` - returns invocation history.
- `GET /governance/report` - returns export-friendly JSON with readiness checks and per-skill governance rows: id, version, enabled flag, lifecycle status, schema validity, invocation counts, provider, tags, risk flags, MCP exposure status, and policy access by role.
- `POST /evals/golden` - runs the golden-case eval suite and returns scored case-level results.
- `POST /snapshots/local` - saves a local JSON snapshot under `.local/`.
- `GET /snapshots/local` - reads the latest local JSON snapshot metadata and payload.

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

## Policy Simulation and Enforcement

Roles are `admin`, `reviewer`, `agent`, and `viewer`. Data sensitivity values are `public`, `internal`, and `confidential`.

```powershell
Invoke-RestMethod http://localhost:8000/policy/simulate `
  -Headers $headers `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"skill_id":"search_knowledge_base","role":"agent","environment":"local","data_sensitivity":"confidential","requested_action":"invoke"}'
```

Invocation remains permissive unless enforcement is requested. Enforce through the body:

```json
{
  "input": {"query": "AI governance policy", "limit": 2},
  "actor": "demo-agent",
  "policy_context": {
    "role": "agent",
    "environment": "local",
    "data_sensitivity": "confidential",
    "requested_action": "invoke",
    "enforce": true
  }
}
```

Or enforce through headers: `X-Policy-Enforce: true`, `X-Policy-Role`, `X-Policy-Environment`, `X-Data-Sensitivity`, and `X-Requested-Action`. Denied FastAPI skill invocations return `403` and record `policy.denied` audit events.

## Promotion Flow

Newly registered manifests can remain draft and visible in the admin catalog without being exposed as MCP tools. Promote a valid skill before agents can discover it:

```powershell
Invoke-RestMethod http://localhost:8000/skills/draft_support_summary/promote `
  -Headers $headers `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"actor":"platform-admin"}'
```
