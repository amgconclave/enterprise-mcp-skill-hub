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
- `tags` - discovery and governance tags.

## Example

```yaml
id: classify_request
name: Request Classification
version: 1.0.0
description: Classify a business request into category, priority, confidence, and rationale.
provider: mock
enabled: true
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

Sample manifests live in `sample_data/manifests/`. They can be pasted into the dashboard or posted to `POST /skills/register`.

Validation rules currently enforce object schemas, declared properties, supported primitive types, required fields, and input/output payload type checks.

