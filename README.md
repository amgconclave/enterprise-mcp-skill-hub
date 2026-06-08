Enterprise teams duplicate AI automations because reusable skills are hard to govern, validate, audit, and safely expose to agents.

Enterprise MCP Skill Hub is a locally runnable FastAPI and MCP-compatible skill layer where approved AI capabilities are registered by manifest, discovered dynamically, invoked with schema validation, and monitored with audit and usage telemetry.

# Enterprise MCP Skill Hub

Enterprise MCP Skill Hub (`enterprise-mcp-skill-hub` / `emcp-hub`) is a locally runnable reference implementation of a governed reusable skill layer for enterprise agents. It exposes approved skills through FastAPI and an MCP-compatible adapter with tools, resources, and prompts.

The default mode is deterministic mock LLM execution, so a fresh clone works without paid API keys. OpenAI and Azure OpenAI providers are available behind the `BaseLLMProvider` interface for teams that want to wire in hosted models later.

## What It Includes

- FastAPI admin API for skill registration, validation, enable/disable, invocation, versions, agent runs, audit, metrics, and health.
- MCP-compatible discovery and invocation for tools, resources, and prompts.
- Six built-in skills: `summarize_document`, `extract_entities`, `translate_text`, `classify_request`, `generate_action_items`, and `search_knowledge_base`.
- Manifest-first governance with JSON-schema-shaped input/output schemas.
- Disabled skills are excluded from MCP tool discovery and blocked during invocation.
- Trace IDs, audit events, invocation history, latency/token/cost metrics, and API-key auth.
- Streamlit admin console for catalog, validation, invocation, demo agent, MCP inspector, metrics, and audit.
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
```

The adapter intentionally uses protocol-shaped payloads even when the official MCP SDK is not installed. See [docs/mcp.md](docs/mcp.md).

## Project Layout

- `app/` - FastAPI app, domain models, registries, validators, providers, MCP adapter, demo, evals.
- `dashboard/` - Streamlit admin console.
- `sample_data/` - sample resources, tickets, meeting notes, expected outputs, and YAML skill manifests.
- `tests/` - pytest coverage for acceptance criteria.
- `docs/` - architecture, API, MCP, manifests, evaluation, and Azure notes.
- `typescript-bridge/` - optional Zod-to-MCP JSON schema concept.

## Environment

Copy `.env.example` to `.env` if you want to override defaults. Local mode needs no external key.

```env
API_KEY=dev-local-token
LLM_PROVIDER=mock
```

Optional provider modes:

- `LLM_PROVIDER=openai` with `OPENAI_API_KEY`.
- `LLM_PROVIDER=azure_openai` with `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_DEPLOYMENT`.
