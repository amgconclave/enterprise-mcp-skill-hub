from __future__ import annotations

from app.config import get_settings
from app.models import SkillManifest
from app.providers import AzureOpenAIProvider, BaseLLMProvider, MockLLMProvider, OpenAIProvider
from app.services import AppState, AuditService, MetricsService
from app.validator import SkillValidator


def schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


BUILTIN_MANIFESTS = [
    SkillManifest(
        id="summarize_document",
        name="Document Summarization",
        version="1.0.0",
        description="Summarize document text or a resource URI into a concise summary and key points.",
        status="promoted",
        input_schema=schema(
            {
                "text": {"type": "string", "description": "Document text to summarize."},
                "resource_uri": {"type": "string", "description": "Optional MCP resource URI."},
            },
            [],
        ),
        output_schema=schema(
            {
                "summary": {"type": "string"},
                "key_points": {"type": "array"},
                "word_count": {"type": "integer"},
                "mode": {"type": "string"},
            },
            ["summary", "key_points"],
        ),
        tags=["summarization", "documents", "prompt-engineering"],
        owner="document-ai-owner",
        owner_team="Knowledge Productivity",
        escalation_channel="#mcp-doc-skills",
    ),
    SkillManifest(
        id="extract_entities",
        name="Entity Extraction",
        version="1.0.0",
        description="Extract people, organizations, products, dates, risks, and action items from text.",
        status="promoted",
        input_schema=schema({"text": {"type": "string"}}, ["text"]),
        output_schema=schema(
            {
                "people": {"type": "array"},
                "organizations": {"type": "array"},
                "products": {"type": "array"},
                "dates": {"type": "array"},
                "risks": {"type": "array"},
                "action_items": {"type": "array"},
            },
            ["people", "organizations"],
        ),
        tags=["extraction", "nlp", "governance"],
        owner="governance-nlp-owner",
        owner_team="AI Governance",
        escalation_channel="#mcp-governance-skills",
    ),
    SkillManifest(
        id="translate_text",
        name="Translation Stub",
        version="1.0.0",
        description="Return a deterministic placeholder translation with language metadata.",
        status="promoted",
        input_schema=schema(
            {
                "text": {"type": "string"},
                "target_language": {"type": "string"},
                "source_language": {"type": "string"},
            },
            ["text", "target_language"],
        ),
        output_schema=schema(
            {
                "translated_text": {"type": "string"},
                "source_language": {"type": "string"},
                "target_language": {"type": "string"},
                "quality": {"type": "string"},
            },
            ["translated_text", "target_language"],
        ),
        tags=["translation", "local-mode"],
        owner="localization-ai-owner",
        owner_team="Global Operations",
        escalation_channel="#mcp-localization-skills",
    ),
    SkillManifest(
        id="classify_request",
        name="Request Classification",
        version="1.0.0",
        description="Classify a business request into category, priority, confidence, and rationale.",
        status="promoted",
        input_schema=schema({"request": {"type": "string"}}, ["request"]),
        output_schema=schema(
            {
                "category": {"type": "string"},
                "priority": {"type": "string"},
                "confidence": {"type": "number"},
                "rationale": {"type": "string"},
            },
            ["category", "priority", "confidence"],
        ),
        tags=["classification", "routing", "agent-tools"],
        owner="intake-routing-owner",
        owner_team="Workflow Platform",
        escalation_channel="#mcp-routing-skills",
    ),
    SkillManifest(
        id="generate_action_items",
        name="Action Item Generator",
        version="1.0.0",
        description="Generate owner, task, due date, and priority action items from notes or support text.",
        status="promoted",
        input_schema=schema({"text": {"type": "string"}}, ["text"]),
        output_schema=schema({"action_items": {"type": "array"}, "count": {"type": "integer"}}, ["action_items"]),
        tags=["meetings", "handoff", "automation"],
        owner="workflow-automation-owner",
        owner_team="Workflow Platform",
        escalation_channel="#mcp-handoff-skills",
    ),
    SkillManifest(
        id="search_knowledge_base",
        name="Knowledge Base Search",
        version="1.0.0",
        description="Search fake internal policy and product resources and return ranked snippets.",
        status="promoted",
        input_schema=schema({"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
        output_schema=schema({"query": {"type": "string"}, "results": {"type": "array"}}, ["query", "results"]),
        tags=["retrieval", "resources", "rag"],
        owner="knowledge-retrieval-owner",
        owner_team="Knowledge Platform",
        escalation_channel="#mcp-retrieval-skills",
    ),
]


def build_provider() -> BaseLLMProvider:
    settings = get_settings()
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings.openai_api_key)
    if settings.llm_provider == "azure_openai":
        return AzureOpenAIProvider(
            settings.azure_openai_api_key,
            settings.azure_openai_endpoint,
            settings.azure_openai_deployment,
        )
    return MockLLMProvider()


def create_state() -> AppState:
    state = AppState(
        validator=SkillValidator(),
        audit=AuditService(),
        metrics=MetricsService(),
        provider=build_provider(),
    )
    for manifest in BUILTIN_MANIFESTS:
        state.registry.register(manifest)
    return state
