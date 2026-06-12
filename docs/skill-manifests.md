# Skill Manifests

Skill manifests are YAML or JSON documents that describe reusable governed capabilities.

## Required Fields

- `id` - lowercase snake_case identifier.
- `name` - human-readable name.
- `version` - semantic version string.
- `description` - business purpose and boundaries.
- `input_schema` - JSON-schema-shaped object schema.
- `output_schema` - JSON-schema-shaped object schema.

## Optional Fields

- `provider` - defaults to `mock`.
- `enabled` - defaults to `true`.
- `status` - lifecycle state: `draft`, `validated`, `promoted`, or `disabled`; defaults to `draft`.
- `tags` - discovery and governance tags; local policy rules can use tags such as `agent-tools` when deciding role access.

`enabled` is retained for backward compatibility. MCP exposure requires both `enabled: true` and `status: promoted`. If `enabled: false` or `status: disabled`, the skill is hidden from MCP tools and blocked from agent use.

## Example

```yaml
id: classify_request
name: Request Classification
version: 1.0.0
description: Classify a business request into category, priority, confidence, and rationale.
provider: mock
enabled: true
status: promoted
tags: [classification, routing, agent-tools]
input_schema:
  type: object
  properties:
    request:
      type: string
  required: [request]
output_schema:
  type: object
  properties:
    category:
      type: string
    priority:
      type: string
    confidence:
      type: number
    rationale:
      type: string
  required: [category, priority, confidence]
```

Sample manifests live in `sample_data/manifests/`. They can be pasted into the dashboard or posted to `POST /skills/register`. A valid registration without an explicit status is marked `validated`; an explicit `status: draft` remains draft. Both states let reviewers inspect schema validity and governance flags before promotion.

Validation rules currently enforce object schemas, declared properties, supported primitive types, required fields, and input/output payload type checks.

## Policy Signals

Policy simulation uses manifest metadata plus request context. The manifest contributes:

- `status` and `enabled` - governed invocation requires promoted and enabled skills when policy is enforced.
- `provider` - production use of non-mock providers is restricted to admins in the local rule set.
- `tags` - viewer access is blocked for `agent-tools` skills.

Request context contributes `role`, `environment`, `data_sensitivity`, and `requested_action`. The simulator returns `decision`, `reasons`, and `matched_rules`, and the governance report summarizes allowed sensitivities by role for every skill.

## Promotion

Use `POST /skills/{skill_id}/promote` after review. Promotion validates the registered manifest, checks `GET /marketplace/promotion-gate/{skill_id}` by default, marks it `status: promoted`, sets `enabled: true`, exposes it through MCP tool discovery, and records an audit event. For a draft or validated skill, submit and approve a marketplace record first so owner signoff is available to the gate.
