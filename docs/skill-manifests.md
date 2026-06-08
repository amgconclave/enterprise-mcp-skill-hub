# Skill Manifests

Skills are registered with YAML or JSON manifests.

Required fields:

- `id`
- `name`
- `version`
- `description`
- `input_schema`
- `output_schema`
- `provider`
- `enabled`
- `tags`

Schemas use a focused JSON schema subset:

- root `type` must be `object`
- `properties` must be an object
- supported field types are `string`, `integer`, `number`, `boolean`, `array`, and `object`
- `required` is optional but must be a list when present

Example:

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
  required: [category, priority, confidence]
```
