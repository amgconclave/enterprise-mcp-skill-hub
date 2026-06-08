# TypeScript Bridge

Python is the primary implementation. This folder shows how a TypeScript team could define schemas with Zod and convert them into MCP-compatible JSON schema before registering a skill manifest.

The idea mirrors `zod-to-mcp-json`: keep authoring ergonomic in TypeScript while producing plain JSON schema for MCP and FastAPI validation.

```bash
npm install zod zod-to-json-schema
node example-zod-schema.mjs
```

The emitted schema can be copied into a skill manifest under `input_schema` or `output_schema`.
