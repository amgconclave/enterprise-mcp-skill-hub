# Evaluation

The eval command is a local acceptance smoke test for the hub:

```powershell
python -m app.evals.run_eval
python -m app.evals.run_eval --validate-only
python -m app.evals.run_conformance
python scripts\dashboard_smoke.py
python -m app.demo
```

It checks:

- Built-in manifests validate.
- An invalid manifest is rejected.
- Disabled skills are excluded from MCP tool listing.
- Built-in skills invoke successfully in mock mode.
- The demo agent selects at least two governed skills.
- Metrics include token and latency records.
- Golden eval cases pass with scored case-level expectations.
- Conformance checks prove promoted skills have valid schemas, deterministic sample outputs, policy checks, MCP exposure, and prompt/resource references.
- Workflow simulations cover template listing, successful composition, denied confidential composition, promoted-only execution, and trace contents.
- Workflow review checks cover submit/list/approve/reject, exclusion before approval, approved simulation, invalid missing-skill blocking, and review evidence export.
- The demo prints security review readiness plus local evidence artifact paths.
- Release tests cover `POST /releases/preview`, `POST /releases/export`, generated-baseline diffs, Markdown/JSON artifacts under `data/releases/`, MCP impact, and disabled/draft exclusion from release readiness.
- The demo prints release readiness plus the exported release notes path.
- Audit and attestation tests cover `POST /audit/query`, `POST /compliance/attestation`, filtering, empty/missing-evidence warnings, generated artifacts under `data/attestations/`, and disabled/draft exclusion from promoted capabilities.
- The demo prints attestation readiness plus the exported attestation path.
- Capacity tests cover `POST /capacity/forecast`, `POST /capacity/guardrails`, `POST /capacity/plan-export`, forecast shape, guardrail defaults/validation, risk flag behavior, generated artifacts under `data/capacity/`, endpoint behavior, and disabled/draft exclusion from capacity readiness.
- The demo prints capacity readiness plus the exported capacity plan path.
- Dependency tests cover `GET /dependencies/map`, `POST /dependencies/blast-radius`, `POST /dependencies/report`, graph shape, known skill impacts, unknown item warnings, generated artifacts under `data/dependencies/`, endpoint behavior, and disabled/draft exclusion from the active dependency graph.
- The demo prints dependency readiness plus the exported dependency report path.
- Incident tests cover every drill scenario, `POST /incidents/drill`, `POST /incidents/runbook`, runbook artifact contents under `data/incident_runbooks/`, endpoint behavior, and disabled/draft exclusion from active incident impact.
- The demo prints incident drill severity/readiness plus the exported incident runbook path.
- Tenant sandbox tests cover tenant-specific differences, `POST /tenants/policy-simulate`, `POST /tenants/sandbox-export`, blocked and review-required decisions, artifact contents under `data/tenant_sandboxes/`, endpoint behavior, and disabled/draft exclusion from active tenant decisions.
- The demo prints tenant sandbox readiness plus the exported tenant sandbox path.
- Skill Marketplace tests cover `GET /marketplace/catalog`, `POST /marketplace/rollout-pack`, deterministic Tenant Rollout scenarios, blocked and review-required rollouts, disabled-skill rollout/invocation blocks, usage/version/MCP exposure signals, artifact contents under `data/marketplace_packs/`, dashboard smoke wiring, Artifact Inventory, and API Contract coverage.
- Skill Usage Analytics tests cover `GET /usage/analytics`, `POST /usage/chargeback-pack`, deterministic usage fixtures across four tenant/environments and all built-in skills, chargeback calculations, token/cost estimates, high-latency anomaly, budget warning, disabled-skill blocked event, generated artifacts under `data/usage_packs/`, dashboard smoke wiring, Artifact Inventory, API Contract coverage, and smoke matrix wiring.
- Provider Readiness tests cover `GET /providers/readiness`, `POST /providers/fallback-pack`, mock-default posture, optional OpenAI/Azure static checks without network calls, generated artifacts under `data/provider_packs/`, dashboard smoke wiring, Artifact Inventory, API Contract coverage, and smoke matrix wiring.
- Privacy Retention tests cover `GET /privacy/retention-report`, `POST /privacy/redact`, `POST /privacy/retention-pack`, deterministic PII-like fixture findings, redacted previews, retention policy actions, generated artifacts under `data/privacy_packs/`, dashboard smoke wiring, Artifact Inventory, API Contract coverage, and smoke matrix wiring.
- Enterprise readiness tests cover `GET /enterprise/readiness-scorecard`, `POST /enterprise/portfolio-demo-pack`, category aggregation, MCP capability counts, verification commands, generated artifacts under `data/portfolio_demo/`, endpoint behavior, and portfolio/interviewer talking points.
- Portfolio Pack tests cover `GET /portfolio/evidence-index`, `POST /portfolio/interview-pack`, JD coverage, proof matrix rows, evidence score, generated artifacts under `data/portfolio_packs/`, technical talking points, local verification commands, and resume/GitHub README bullets.
- API smoke and launch checklist tests cover `GET /ops/smoke-matrix`, `POST /ops/launch-checklist`, expected endpoint matrix coverage, generated artifacts under `data/launch_checklists/`, endpoint behavior, JD skills demonstrated, and five interviewer talking points.
- Release Candidate tests cover `GET /release/quality-gate`, `POST /release/publish-pack`, status/score/blocker/warning shape, verification checklist, endpoint/MCP/artifact inventories, generated artifacts under `data/release_packs/`, GitHub checklist, recruiter notes, and known limitations.
- CI Doctor tests cover `GET /ops/ci-doctor`, `POST /ops/audit-pack`, command checks for pytest/ruff/eval/conformance/demo/MCP, GitHub Actions/Docker/env/docs/ignore/dependency/local-mock checks, suspicious secret scan summary, generated artifacts under `data/audit_packs/`, remediation notes, and recruiter/interviewer explanation.
- Reviewer Quickstart tests cover `GET /reviewer/quickstart`, `POST /reviewer/walkthrough-pack`, exact setup/demo/verification commands, endpoint walkthrough order, MCP command walkthrough, artifact proof map, expected outputs, role-specific notes, generated artifacts under `data/reviewer_packs/`, recruiter story, engineer path, command checklist, API/MCP proof tour, limitations, and GitHub README blurb.
- Artifact Inventory tests cover `GET /artifacts/inventory`, `POST /artifacts/readme-checklist`, generated artifact directories, latest file shape, producer endpoints/commands, ignored status, reviewer purpose, freshness notes, README Checklist contents, `data/artifact_indexes/` output, and the reviewer proof checklist.
- API Contract tests cover `GET /api/contract-audit`, `POST /api/reviewer-collection`, OpenAPI route count, auth-protected endpoint count, docs/api coverage, dashboard smoke alignment, generated artifact endpoint coverage, demo flow endpoint coverage, MCP tools/resources/prompts coverage, generated artifacts under `data/api_contracts/`, expected status codes, sample commands, and local-only limitations.
- Dashboard Smoke and UI Verification tests cover `GET /ui/dashboard-smoke`, `POST /ui/verification-pack`, `python scripts\dashboard_smoke.py`, expected Streamlit views/endpoints, generated artifact tabs, MCP proof surfaces, screenshot placeholders, `data/ui_verification/` output, and local/browser-free limitations.
- Final Handoff tests cover `GET /handoff/final-audit`, `POST /handoff/final-pack`, README Consistency checks, endpoint/MCP/artifact inventory summaries, dashboard smoke summary, eval/conformance proof summary, `data/final_handoff/` output, demo claims, and local/mock Azure/OpenAI optional-provider limitations.
- The demo prints enterprise readiness, portfolio evidence score/count, smoke readiness, the exported portfolio demo pack path, interview pack path, launch checklist path, release gate status/score, and publish pack path.
- The demo prints CI Doctor status/score and the exported Audit Pack path.
- The demo prints reviewer quickstart status/count and the exported Walkthrough Pack path.
- The demo prints artifact inventory count and the exported README Checklist path.
- The demo prints dashboard smoke status/check count and the exported UI Verification Pack path.
- The demo prints API Contract audit status/route count and the exported Reviewer Collection path.
- The demo prints Skill Marketplace readiness, catalog listing count, and the exported Tenant Rollout approval pack path.
- The demo prints Skill Usage Analytics readiness, Cost Chargeback estimated cost, and the exported chargeback pack path.
- The demo prints Privacy Retention readiness, finding count, and the exported Privacy Retention Pack path.
- The demo prints final audit status/score and the exported Final Handoff Pack path.

The pytest suite provides deeper endpoint and service coverage:

```powershell
python -m pytest
```

Covered behavior includes auth, health, registration, validation, invocation, disabled skill blocking, MCP tools/resources/prompts, agent routing, metrics, audit, and invocation history.
Replay tests cover deterministic successful invocations and enforced policy denials that remain denied without executing the skill handler.
Evidence tests cover `POST /evidence/export` contents and `GET /security/review-summary` readiness fields.
Workflow tests cover `GET /workflows/templates`, `POST /workflows/{template_id}/simulate`, denied confidential workflows, disabled skill blocking, trace contents, `POST /workflows/templates/submit`, `GET /workflows/reviews`, approval/rejection gates, approved-template simulation, and `POST /workflows/{template_id}/review-evidence`.
Release tests cover release preview diff behavior, export artifact contents, endpoint behavior, MCP capability impact, and exclusion of disabled/draft skills from release readiness.
Audit/attestation tests cover normalized audit query behavior across audit, invocation, governance, release, and workflow evidence plus compliance pack JSON/Markdown contents.
Capacity tests cover deterministic local/mock skill usage forecasting, quota/latency/token risk flags, guardrail validation/defaults, capacity plan export contents, endpoint behavior, and exclusion of disabled/draft skills from demand planning.
Dependency tests cover deterministic graph shape, high-centrality skill detection, known skill blast radius, unknown item warnings, report export contents, endpoint behavior, and exclusion of disabled/draft skills from active dependency readiness.
Incident tests cover deterministic skill incident drill scenarios, recovery runbook export contents, endpoint behavior, MCP capabilities affected, and exclusion of disabled/draft skills from active incident impact.
Tenant sandbox tests cover healthcare, fintech, public sector, and internal demo policy differences; allowed, blocked, and review-required skill/workflow decisions; endpoint behavior; export artifacts; MCP impact; and disabled/draft skill exclusion.
Skill Usage Analytics tests cover usage grouping, deterministic token/cost chargeback, latency bands, budget/anomaly flags, disabled-skill blocked events, generated `data/usage_packs/` artifacts, dashboard/API contract wiring, and smoke matrix coverage.
Privacy Retention tests cover deterministic local PII-like scanning across fixtures and live invocation/audit payloads, ad hoc JSON redaction, generated `data/privacy_packs/` artifacts, dashboard/API contract wiring, and smoke matrix coverage.
Enterprise readiness tests cover the executive scorecard, portfolio demo pack, endpoint behavior, artifact contents, MCP capability counts, verification commands, JD skills demonstrated, and five interviewer talking points.
Release Candidate tests cover the quality gate, Publish Pack export, endpoint behavior, artifact contents, verification commands, endpoint inventory, MCP capability inventory, GitHub checklist, recruiter review notes, and known limitations.
CI Doctor tests cover the local publish-safety audit, Audit Pack export, endpoint behavior, dependency inventory, secret scan summary, generated artifact ignore coverage, local verification commands, remediation notes, and recruiter/interviewer explanation.
Reviewer Quickstart tests cover the quickstart API, Walkthrough Pack export, endpoint behavior, setup and verification command coverage, MCP proof tour, generated `data/reviewer_packs/` artifacts, troubleshooting notes, role-specific reviewer notes, recruiter story, engineer deep dive, limitations, and README blurb.
Artifact Inventory tests cover the inventory API, README Checklist export, endpoint behavior, generated `data/artifact_indexes/` artifacts, badge/checklist suggestions, local commands, cleanup/regeneration notes, and reviewer proof checklist.
Dashboard Smoke tests cover source-only Streamlit wiring checks, `/ui/dashboard-smoke`, `/ui/verification-pack`, generated `data/ui_verification/` artifacts, screenshot placeholders, MCP proof surfaces, and the local `python scripts\dashboard_smoke.py` script.
Final Handoff tests cover the README Consistency final audit, `/handoff/final-audit`, `/handoff/final-pack`, generated `data/final_handoff/` artifacts, endpoint inventory summary, MCP inventory summary, artifact inventory summary, dashboard smoke summary, eval/conformance proof summary, exact clone/run commands, and recruiter-facing final README blurb.

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

## Workflow Simulation

Workflow composition checks show how promoted skills become reusable enterprise agent flows:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/workflows/templates -Headers $headers
Invoke-RestMethod http://localhost:8000/workflows/support_triage/simulate `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"input_text":"Support ticket: security review is blocking an RFP.","role":"agent","data_sensitivity":"internal","environment":"local"}'
```

The expected local behavior is deterministic: allowed steps execute through promoted MCP tools, denied steps are reported in `blocked_steps`, and the trace includes step index, skill id, policy decision, matched rules, and trace id.

## Workflow Review Evidence

The review queue makes workflow composition testable before execution:

```powershell
$template = @{
  id = "reviewed_support_pack"
  name = "Reviewed Support Pack"
  description = "Classify and summarize a support request after workflow review approval."
  ordered_skill_ids = @("classify_request", "summarize_document")
  required_role = "agent"
  default_sensitivity = "internal"
  expected_outputs = @("category", "summary")
} | ConvertTo-Json

Invoke-RestMethod http://localhost:8000/workflows/templates/submit -Method POST -Headers $headers -ContentType "application/json" -Body $template
Invoke-RestMethod http://localhost:8000/workflows/reviews -Headers $headers
Invoke-RestMethod http://localhost:8000/workflows/reviewed_support_pack/approve -Method POST -Headers $headers -ContentType "application/json" -Body '{"actor":"eval-reviewer"}'
Invoke-RestMethod http://localhost:8000/workflows/reviewed_support_pack/review-evidence -Method POST -Headers $headers
```

The evidence export is deterministic and local. It includes the submitted template, current validation, dry-run simulation, approval/rejection state, policy warnings, and related audit events.

## Invocation Replay

Every invocation stores the skill id/version, input, output or denial, policy context, policy decision, trace id, and timing. Replay uses that history to rerun the current local handler with the original input, normalizes non-business metadata such as the trace id, and returns drift notes.

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
$created = Invoke-RestMethod http://localhost:8000/skills/classify_request/invoke `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{"input":{"request":"Security outage is blocking the RFP."}}'
Invoke-RestMethod "http://localhost:8000/invocations/$($created.id)/replay" -Method POST -Headers $headers
```

## Security Review Evidence

The security summary is intentionally compact for dashboards and procurement checklists:

```powershell
Invoke-RestMethod http://localhost:8000/security/review-summary -Headers $headers
```

The full evidence export writes ignored local files under `data/evidence/`:

```powershell
Invoke-RestMethod http://localhost:8000/evidence/export -Method POST -Headers $headers
```

The JSON and Markdown bundle includes governance, conformance, policy denial history, promoted skills, disabled/draft exclusions, invocation history, MCP exposure, and recommended next controls.

## Release Preview Evidence

Release preview is a local, deterministic audit check for what would change before platform owners release promoted skills and approved workflow templates:

```powershell
Invoke-RestMethod http://localhost:8000/releases/preview -Method POST -Headers $headers
Invoke-RestMethod http://localhost:8000/releases/export -Method POST -Headers $headers
```

If `data/releases/current_snapshot.json` does not exist, the service uses a generated baseline so fresh clones still show added/changed catalog entries. Export writes `release_notes_latest.json`, `release_notes_latest.md`, and a refreshed `current_snapshot.json` under ignored `data/releases/`. The release notes include local verification commands, MCP tools/resources/prompts affected, conformance and governance status, JD skills demonstrated, and five interviewer talking points.

## Audit Query And Compliance Attestation

The audit query console is deterministic and local. It normalizes audit events, invocation records, governance rows, workflow reviews, and release preview/export evidence into filterable records:

```powershell
Invoke-RestMethod http://localhost:8000/audit/query -Method POST -Headers $headers -ContentType "application/json" -Body '{"action":"skill.invoked","status":"succeeded"}'
```

The compliance pack is the procurement/security handoff artifact:

```powershell
Invoke-RestMethod http://localhost:8000/compliance/attestation -Method POST -Headers $headers -ContentType "application/json" -Body '{"actor":"security-reviewer"}'
```

It writes `compliance_attestation_latest.json` and `compliance_attestation_latest.md` under ignored `data/attestations/` with governance controls, MCP exposure, conformance, release readiness, audit summary, policy examples, exclusions, verification commands, JD skills, and five talking points.

## Capacity Forecast Evidence

Capacity planning proves the hub can operate as a platform control plane before broad agent enablement:

```powershell
Invoke-RestMethod http://localhost:8000/capacity/forecast -Method POST -Headers $headers -ContentType "application/json" -Body '{"forecast_days":30}'
Invoke-RestMethod http://localhost:8000/capacity/guardrails -Method POST -Headers $headers -ContentType "application/json" -Body '{"write_config":true}'
Invoke-RestMethod http://localhost:8000/capacity/plan-export -Method POST -Headers $headers
```

The forecast is deterministic and local. It uses invocation history, promoted skills, approved workflow templates, release/audit evidence, and mock traffic assumptions to estimate per-skill demand, tokens, local planning cost, latency p95, top workflow drivers, risks, and recommended rate limits. Export writes `capacity_plan_latest.json` and `capacity_plan_latest.md` under ignored `data/capacity/`.

## Dependency Map Evidence

Dependency analysis proves owners can reason about blast radius before changing a skill, prompt, resource, or workflow template:

```powershell
Invoke-RestMethod http://localhost:8000/dependencies/map -Headers $headers
Invoke-RestMethod http://localhost:8000/dependencies/blast-radius -Method POST -Headers $headers -ContentType "application/json" -Body '{"skill_id":"search_knowledge_base"}'
Invoke-RestMethod http://localhost:8000/dependencies/report -Method POST -Headers $headers
```

The graph is deterministic and local. It combines promoted skills, MCP tools/prompts/resources, approved workflow templates, release preview evidence, invocation/audit history, and capacity forecast evidence. Report export writes `dependency_report_latest.json` and `dependency_report_latest.md` under ignored `data/dependencies/`.

## Skill Incident Drill Evidence

Incident drills demonstrate platform reliability under realistic local failure modes:

```powershell
Invoke-RestMethod http://localhost:8000/incidents/drill -Method POST -Headers $headers -ContentType "application/json" -Body '{"scenario":"policy_denial_spike"}'
Invoke-RestMethod http://localhost:8000/incidents/runbook -Method POST -Headers $headers -ContentType "application/json" -Body '{"scenario":"policy_denial_spike"}'
```

The drill composes dependency blast radius, capacity forecast, audit query, MCP discovery, conformance/eval commands, and disabled/draft exclusions. Runbook export writes `incident_runbook_latest_<scenario>.json` and `.md` under ignored `data/incident_runbooks/` with timeline, containment, owner matrix, rollback/canary plan, verification commands, JD skills demonstrated, and five interviewer talking points.

## Tenant Policy Sandbox Evidence

Tenant simulations demonstrate enterprise multi-tenant governance over the same MCP catalog:

```powershell
Invoke-RestMethod http://localhost:8000/tenants/policy-simulate -Method POST -Headers $headers -ContentType "application/json" -Body '{"tenant":"healthcare","role":"reviewer","environment":"production","data_sensitivity":"confidential"}'
Invoke-RestMethod http://localhost:8000/tenants/sandbox-export -Method POST -Headers $headers
```

The response separates allowed, blocked, and review-required skills/workflows, reports policy reasons, impacted MCP tools/resources/prompts, recommended guardrails, warnings, readiness, and disabled/draft exclusions. Export writes `tenant_policy_sandbox_latest.json` and `.md` under ignored `data/tenant_sandboxes/` with the policy matrix, scenario results, blocked/review actions, MCP impact, local verification commands, JD skills demonstrated, and five interviewer talking points.

## Skill Marketplace Rollout Approval Evidence

Marketplace governance demonstrates reviewed local capability rollout instead of raw MCP discovery:

```powershell
Invoke-RestMethod http://localhost:8000/marketplace/catalog -Headers $headers
Invoke-RestMethod http://localhost:8000/marketplace/rollout-pack -Method POST -Headers $headers
```

The catalog returns promoted, approved/validated, draft, and disabled listings with Tenant Rollout scenarios for internal ops, regulated healthcare, fintech/confidential, and public-sector restricted environments. The rollout approval pack writes `rollout_approval_pack_latest.json` and `.md` under ignored `data/marketplace_packs/` with rollout recommendations, tenant policy decisions, disabled-skill blocks, version comparison notes, reviewer checklist, proof commands, and limitations.

## Enterprise Readiness Evidence

The final portfolio check aggregates all readiness areas into one scorecard:

```powershell
Invoke-RestMethod http://localhost:8000/enterprise/readiness-scorecard -Headers $headers
Invoke-RestMethod http://localhost:8000/enterprise/portfolio-demo-pack -Method POST -Headers $headers
```

The scorecard includes governance, conformance, release readiness, audit/attestation, capacity, dependency blast radius, incident drill, tenant sandbox, and demo agent behavior. The portfolio demo pack writes `portfolio_demo_pack_latest.json` and `.md` under ignored `data/portfolio_demo/` with the scorecard, architecture talking points, local demo commands, endpoint map, artifacts list, JD skills demonstrated, and five interviewer talking points.

## Portfolio Evidence And Interview Pack

The recruiter/interviewer proof surface is deterministic and local:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/portfolio/evidence-index -Headers $headers
Invoke-RestMethod http://localhost:8000/portfolio/interview-pack -Method POST -Headers $headers
```

The Portfolio Evidence index maps JD skills to concrete proofs across MCP tools/resources/prompts, FastAPI admin API, skill manifests, schema validation, governance, audit logs, enable/disable/versioning, workflow templates, conformance evals, release preview, capacity guardrails, tenant policy sandbox, incident runbook, enterprise readiness, smoke matrix, and launch checklist. The Interview Pack writes `interview_pack_latest.json` and `.md` under ignored `data/portfolio_packs/` with a 3-minute demo script, 8-10 technical talking points, architecture walk-through, governance/failure-mode story, local verification commands, metrics/eval summary, artifact inventory, and resume/GitHub README bullets.

## API Smoke Matrix And Launch Checklist

The final local launch check makes the README/interview path copy-ready:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/ops/smoke-matrix -Headers $headers
Invoke-RestMethod http://localhost:8000/ops/launch-checklist -Method POST -Headers $headers
```

The smoke matrix returns expected statuses, sample commands, artifact expectations, and a readiness summary for auth/health, skills, MCP surfaces, governance, workflows, releases, capacity, tenant policy, incidents, and enterprise readiness. The launch checklist writes `launch_checklist_latest.json` and `.md` under ignored `data/launch_checklists/` with install/run commands, API smoke matrix, demo command, eval commands, artifact paths, troubleshooting notes, JD skills demonstrated, and five interviewer talking points.

## Release Candidate Quality Gate

The final publish gate is local and deterministic:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/release/quality-gate -Headers $headers
Invoke-RestMethod http://localhost:8000/release/publish-pack -Method POST -Headers $headers
```

The gate returns status, score, blockers, warnings, verification checklist, CI/docs/test/eval/demo/MCP/release coverage, artifact coverage, local runtime notes, publish readiness, endpoint inventory, and MCP capability inventory. The Publish Pack writes `publish_pack_latest.json` and `.md` under ignored `data/release_packs/` with setup/demo commands, verification commands, expected outputs, endpoint inventory, MCP capability inventory, artifact inventory, screenshot placeholders, GitHub checklist, commit/push notes, recruiter review notes, and known limitations.

## Local CI Doctor Audit Pack

The local CI Doctor makes the pre-publish check deterministic and repeatable:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/ops/ci-doctor -Headers $headers
Invoke-RestMethod http://localhost:8000/ops/audit-pack -Method POST -Headers $headers
```

The doctor returns structured checks for pytest, ruff, eval/conformance, demo, MCP inspector commands, GitHub Actions workflow presence, Docker Compose presence, `.env.example`, README sections, docs presence, generated artifact ignores, dependency files, local/mock provider notes, and a suspicious secret scan summary.

The Audit Pack writes `audit_pack_latest.json` and `.md` under ignored `data/audit_packs/`. It includes the CI Doctor results, dependency inventory, secret scan summary, local verification commands, publish-safety checklist, remediation notes, recruiter/interviewer explanation, and limitations. The secret scan is local and regex-based with redacted excerpts, so it is a publish-safety signal rather than a substitute for a dedicated external secret scanner.

## Artifact Inventory And README Checklist

The final GitHub reviewer polish check exposes the generated artifact surface:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/artifacts/inventory -Headers $headers
Invoke-RestMethod http://localhost:8000/artifacts/readme-checklist -Method POST -Headers $headers
Get-ChildItem -Recurse -File data\artifact_indexes -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime
```

The inventory covers MCP-specific portfolio demo, release packs, audit packs, reviewer packs, launch checklists, conformance/security/governance outputs, and related evidence directories. The README Checklist export writes `readme_checklist_latest.json` and `.md` under ignored `data/artifact_indexes/` with Artifact Inventory rows, README badge suggestions, local commands, cleanup/regeneration notes, and a reviewer proof checklist.

## API Contract Evidence

The API Contract audit gives reviewers a generated contract snapshot:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/api/contract-audit -Headers $headers
Invoke-RestMethod http://localhost:8000/api/reviewer-collection -Method POST -Headers $headers
Get-ChildItem -Recurse -File data\api_contracts -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime
```

The audit checks OpenAPI route count, auth-protected endpoint count, docs/api coverage for important endpoints, dashboard smoke alignment, generated artifact endpoint coverage, demo flow endpoint coverage, MCP tools/resources/prompts coverage, missing docs warnings, duplicate/deprecated route warnings, and local-only limitations. The Reviewer Collection writes `reviewer_collection_latest.json` and `.md` under ignored `data/api_contracts/` with endpoint inventory, MCP inventory, sample `X-API-Key` commands, demo-token flow, MCP CLI commands, expected status codes, auth notes, generated artifact endpoints, one-command verification order, and recruiter/engineer explanation.

## Final Handoff Evidence

The final README Consistency audit closes the handoff loop:

```powershell
$headers = @{ "X-API-Key" = "dev-local-token" }
Invoke-RestMethod http://localhost:8000/handoff/final-audit -Headers $headers
Invoke-RestMethod http://localhost:8000/handoff/final-pack -Method POST -Headers $headers
Get-ChildItem -Recurse -File data\final_handoff -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime
```

The audit checks README endpoint/MCP mentions, docs/api coverage, architecture/evaluation coverage, demo output claims, scripts present, dashboard smoke script present, generated artifact directory docs, MCP tools/resources/prompts clarity, local/mock limitation clarity, and Azure/OpenAI optional notes. The Final Handoff Pack writes `final_handoff_pack_latest.json` and `.md` under ignored `data/final_handoff/` with final audit results, exact clone/run commands, end-to-end verification order, endpoint/MCP/artifact summaries, dashboard smoke summary, eval/conformance proof summary, and a recruiter-facing final README blurb.
