# Evaluation

The eval command is a local acceptance smoke test for the hub:

```powershell
python -m app.evals.run_eval
python -m app.evals.run_eval --validate-only
```

It checks:

- Built-in manifests validate.
- An invalid manifest is rejected.
- Disabled skills are excluded from MCP tool listing.
- Built-in skills invoke successfully in mock mode.
- The demo agent selects at least two governed skills.
- Metrics include token and latency records.

The pytest suite provides deeper endpoint and service coverage:

```powershell
python -m pytest
```

Covered behavior includes auth, health, registration, validation, invocation, disabled skill blocking, MCP tools/resources/prompts, agent routing, metrics, audit, and invocation history.

