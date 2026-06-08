Enterprise teams duplicate AI automations because reusable skills are hard to govern, validate, audit, and safely expose to agents.

Enterprise MCP Skill Hub is a locally runnable FastAPI and MCP-compatible skill layer where approved AI capabilities are registered by manifest, discovered dynamically, invoked with schema validation, and monitored with audit and usage telemetry.

# Enterprise MCP Skill Hub

Enterprise MCP Skill Hub (`enterprise-mcp-skill-hub` / `emcp-hub`) is a locally runnable reference implementation of a governed reusable skill layer for enterprise agents. It exposes approved skills through FastAPI and an MCP-compatible adapter with tools, resources, and prompts.

The default mode is deterministic mock LLM execution, so a fresh clone works without paid API keys. OpenAI and Azure OpenAI providers are available behind the `BaseLLMProvider` interface for teams that want to wire in hosted models later.

## What It Includes

- FastAPI admin API for skill registration, validation, promotion, enable/disable, invocation, versions, agent runs, audit, metrics, and health.
- MCP-compatible discovery and invocation for tools, resources, and prompts.
- Six built-in skills: `summarize_document`, `extract_entities`, `translate_text`, `classify_request`, `generate_action_items`, and `search_knowledge_base`.
- Manifest-first governance with JSON-schema-shaped input/output schemas and a `draft -> validated -> promoted -> disabled` lifecycle.
- Draft, disabled, and schema-invalid skills are excluded from MCP tool discovery; the demo agent only selects promoted/enabled tools.
- Local policy simulator for role, environment, data sensitivity, skill tags/provider, and allow/deny invocation decisions.
- Optional enforced invocation for FastAPI and MCP calls, with denied attempts captured in audit and metrics.
- Trace IDs, audit events, invocation history, latency/token/cost metrics, policy simulation, golden eval scorecards, per-skill governance reports, local JSON snapshots, and API-key auth.
- Streamlit admin console for catalog, validation, promotion, invocation, policy simulation, demo agent, eval lab, MCP inspector, governance reports, metrics, and audit.
- Sample policy/product resources, sample skill manifests, tests, eval smoke command, Docker Compose, and GitHub Actions CI.

## Quick Start

```powershell
cd C:\Users\Devan\Documents\emcp-hub
python -m pip install -r requirements-dev.txt
python -m pytest
python -m app.evals.run_eval
python -m uvicorn app.main:app --reload --port 8000
```

Get a demo token:

```powershell
curl -X POST http://localhost:8000/auth/demo-token
```

Use the returned `X-API-Key` value for protected endpoints.

Run the local demo agent:

```powershell
python -m app.demo
```

Run the dashboard:

```powershell
python -m streamlit run dashboard/streamlit_app.py
```

Run both API and dashboard:

```powershell
docker compose up --build
```

## MCP-Compatible Inspector

```powershell
python -m app.mcp_server tools
python -m app.mcp_server resources
python -m app.mcp_server prompts
python -m app.mcp_server call --name summarize_document --arguments "{\"text\":\"Atlas Labs needs governed AI skills.\"}"
python -m app.mcp_server call --name search_knowledge_base --arguments "{\"query\":\"confidential policy\",\"limit\":2}" --role agent --data-sensitivity confidential --enforce-policy
```

The adapter intentionally uses protocol-shaped payloads even when the official MCP SDK is not installed. See [docs/mcp.md](docs/mcp.md).

## Project Layout

- `app/` - FastAPI app, domain models, registries, validators, providers, MCP adapter, demo, evals.
- `dashboard/` - Streamlit admin console.
- `sample_data/` - sample resources, tickets, meeting notes, expected outputs, and YAML skill manifests.
- `tests/` - pytest coverage for acceptance criteria.
- `docs/` - architecture, API, MCP, manifests, evaluation, and Azure notes.
- `typescript-bridge/` - optional Zod-to-MCP JSON schema concept.

## Governance Snapshot

Generate an interviewer-friendly readiness report and save a local JSON snapshot of skills, versions, invocations, metrics, audit events, and the report:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/governance/report -Headers $headers
Invoke-RestMethod http://localhost:8000/snapshots/local -Method POST -Headers $headers
```

The governance report includes one row per skill with id, version, enabled flag, lifecycle status, schema validity, last invocation, invocation/failure counts, provider, tags, risk flags, MCP exposure status, and policy access by role.

## Policy Simulator

Use the simulator to explain why a role can or cannot invoke a skill:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/policy/simulate `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"skill_id":"search_knowledge_base","role":"agent","environment":"local","data_sensitivity":"confidential","requested_action":"invoke"}'
```

Policy enforcement is opt-in for local compatibility. Add `policy_context.enforce=true` in the request body or send headers such as `X-Policy-Enforce: true`, `X-Policy-Role: reviewer`, and `X-Data-Sensitivity: confidential`.

## Promotion Workflow

New manifests can be registered as draft or validated skills for local review. Promote a valid skill before MCP clients or the demo agent can discover it:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/skills/draft_support_summary/promote `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"actor":"platform-admin"}'
```

Promotion validates the manifest, sets `status=promoted`, keeps `enabled=true`, exposes the skill as an MCP tool, and records `skill.promoted` in the audit log.

## Evaluation And Policy Lab

The project now includes two reviewer-friendly controls:

- Golden evals: scored behavior checks from `sample_data/evals/golden_cases.json`.
- Policy simulation: role, environment, sensitivity, and action rules that can block enforced invocations.

```powershell
Invoke-RestMethod http://localhost:8000/evals/golden -Method POST -Headers $headers
Invoke-RestMethod http://localhost:8000/policy/simulate `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"skill_id":"classify_request","role":"viewer","environment":"local","data_sensitivity":"confidential","requested_action":"invoke"}'
```

## Environment

Copy `.env.example` to `.env` if you want to override defaults. Local mode needs no external key.

```env
API_KEY=dev-local-token
LLM_PROVIDER=mock
```

Optional provider modes:

- `LLM_PROVIDER=openai` with `OPENAI_API_KEY`.
- `LLM_PROVIDER=azure_openai` with `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_DEPLOYMENT`.
