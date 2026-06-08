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
- Golden eval cases pass with scored case-level expectations.

The pytest suite provides deeper endpoint and service coverage:

```powershell
python -m pytest
```

Covered behavior includes auth, health, registration, validation, invocation, disabled skill blocking, MCP tools/resources/prompts, agent routing, metrics, audit, and invocation history.

## Golden Cases

`sample_data/evals/golden_cases.json` defines behavior checks for classification, extraction, retrieval, and action-item generation.

Run the suite through the API:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/evals/golden -Method POST -Headers $headers
```

The regular eval command includes `golden_eval_score`, passed case count, and failed case count.

## Policy Simulation

The policy simulator gives interviewers a concrete access-control surface:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/policy/simulate `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"skill_id":"classify_request","role":"viewer","environment":"local","data_sensitivity":"confidential","requested_action":"invoke"}'
```

Invocation requests can include `policy_context.enforce=true` or policy headers to block unsafe calls before tool execution.
