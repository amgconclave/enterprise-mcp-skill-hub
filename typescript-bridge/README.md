# TypeScript Bridge Concept

This optional bridge shows how a TypeScript team could author schemas in Zod and export MCP-compatible JSON schema for registration in the Python hub.

It is intentionally not required for local runtime.

```ts
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

const input = z.object({
  ticket: z.string().describe("Support ticket text"),
});

const output = z.object({
  draft: z.string(),
  confidence: z.number(),
});

export const manifest = {
  id: "draft_support_reply",
  name: "Draft Support Reply",
  version: "1.0.0",
  description: "Draft a governed support reply from ticket context.",
  provider: "mock",
  enabled: true,
  tags: ["support", "zod"],
  input_schema: zodToJsonSchema(input),
  output_schema: zodToJsonSchema(output),
};
```

The important contract is not the TypeScript runtime; it is the manifest shape consumed by `POST /skills/register`.

