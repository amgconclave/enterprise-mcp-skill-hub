# Azure Deployment Notes

The local project defaults to `MockLLMProvider`. To test Azure OpenAI, set:

```bash
LLM_PROVIDER=azure_openai
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment
```

Operational recommendations:

- keep provider credentials outside the repo
- separate local, staging, and production deployments
- record provider, model, token usage, latency, and trace ID for each invocation
- require security review before enabling skills that call external models
- use disabled status to hide tools from MCP discovery before rollback or deprecation

The provider adapter boundary is intentionally small, so teams can add enterprise policy checks, content filters, network controls, or customer-specific routing without changing the skill manifest contract.
