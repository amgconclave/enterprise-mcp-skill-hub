from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import TokenUsage


class LLMResult(dict):
    text: str
    token_usage: TokenUsage


class BaseLLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def complete(self, prompt: str, context: dict[str, Any] | None = None) -> tuple[str, TokenUsage]:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    name = "mock"
    model = "mock-deterministic-v1"

    async def complete(self, prompt: str, context: dict[str, Any] | None = None) -> tuple[str, TokenUsage]:
        words = prompt.split()
        response = " ".join(words[: min(24, len(words))]) or "No input supplied."
        usage = TokenUsage(input_tokens=len(words), output_tokens=len(response.split()), estimated_cost=0.0)
        return response, usage


class OpenAIProvider(BaseLLMProvider):
    name = "openai"
    model = "gpt-4.1-mini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key
        if model:
            self.model = model

    async def complete(self, prompt: str, context: dict[str, Any] | None = None) -> tuple[str, TokenUsage]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIProvider.")
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.responses.create(model=self.model, input=prompt)
        usage = getattr(response, "usage", None)
        token_usage = TokenUsage(
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            estimated_cost=0.0,
        )
        return response.output_text, token_usage


class AzureOpenAIProvider(BaseLLMProvider):
    name = "azure_openai"
    model = "azure-configured-deployment"

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        deployment: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment = deployment
        if deployment:
            self.model = deployment

    async def complete(self, prompt: str, context: dict[str, Any] | None = None) -> tuple[str, TokenUsage]:
        if not self.api_key or not self.endpoint or not self.deployment:
            raise RuntimeError("Azure OpenAI endpoint, deployment, and key are required.")
        from openai import AsyncAzureOpenAI

        client = AsyncAzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version="2024-10-21",
        )
        response = await client.responses.create(model=self.deployment, input=prompt)
        usage = getattr(response, "usage", None)
        token_usage = TokenUsage(
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            estimated_cost=0.0,
        )
        return response.output_text, token_usage
