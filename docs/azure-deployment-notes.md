# Azure Deployment Notes

The project runs locally in mock mode by default. To adapt it for Azure:

1. Containerize with the included `Dockerfile`.
2. Store secrets in Azure Key Vault or managed environment variables.
3. Set `LLM_PROVIDER=azure_openai`.
4. Set `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_DEPLOYMENT`.
5. Put the API behind an authenticated ingress such as Azure API Management or App Service authentication.
6. Persist audit, invocation, and metrics streams to Azure Monitor, Log Analytics, or a database.
7. Keep `API_KEY` rotation separate from model provider credentials.

The Azure provider is intentionally optional. The acceptance path should continue to pass without Azure credentials.

