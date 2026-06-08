from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

JsonDict = dict[str, Any]
SkillStatus = Literal["enabled", "disabled"]
InvocationStatus = Literal["succeeded", "failed"]


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0


class SkillManifest(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    version: str
    description: str
    input_schema: JsonDict
    output_schema: JsonDict
    provider: str = "mock"
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)

    @field_validator("input_schema", "output_schema")
    @classmethod
    def schema_must_be_object(cls, value: JsonDict) -> JsonDict:
        if value.get("type") != "object":
            raise ValueError("schema must be a JSON schema object with type=object")
        if "properties" not in value:
            raise ValueError("schema must define properties")
        return value


class SkillVersion(BaseModel):
    skill_id: str
    version: str
    manifest_hash: str
    created_at: datetime
    status: SkillStatus


class SkillInvocation(BaseModel):
    id: str
    skill_id: str
    version: str
    input: JsonDict
    output: JsonDict | None
    status: InvocationStatus
    trace_id: str
    latency_ms: float
    token_usage: TokenUsage
    created_at: datetime
    error: str | None = None


class McpToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: JsonDict
    output_schema: JsonDict
    annotations: JsonDict = Field(default_factory=dict)


class PromptArgument(BaseModel):
    name: str
    description: str
    required: bool = True


class PromptDefinition(BaseModel):
    id: str
    name: str
    description: str
    arguments: list[PromptArgument]
    template: str
    version: str = "1.0.0"


class ResourceDefinition(BaseModel):
    uri: str
    name: str
    description: str
    mime_type: str = "text/plain"
    content_ref: str
    annotations: JsonDict = Field(default_factory=dict)


class ResourcePayload(BaseModel):
    definition: ResourceDefinition
    content: str


class AgentRun(BaseModel):
    id: str
    prompt: str
    selected_skills: list[str]
    final_output: str
    trace: list[JsonDict]
    token_usage: TokenUsage
    latency_ms: float


class UsageMetric(BaseModel):
    trace_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    estimated_cost: float
    skill_id: str | None = None
    status: InvocationStatus = "succeeded"


class AuditEvent(BaseModel):
    id: str
    trace_id: str
    actor: str
    action: str
    resource_type: str
    resource_id: str
    created_at: datetime
    metadata: JsonDict = Field(default_factory=dict)


class RegisterSkillRequest(BaseModel):
    manifest: SkillManifest


class ValidateSkillRequest(BaseModel):
    manifest: JsonDict


class InvokeSkillRequest(BaseModel):
    input: JsonDict
    actor: str = "demo-user"


class SkillStatusRequest(BaseModel):
    enabled: bool
    actor: str = "demo-user"


class AgentRunRequest(BaseModel):
    prompt: str
    actor: str = "demo-user"


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    manifest_id: str | None = None


class HealthResponse(BaseModel):
    status: str
    provider_mode: str
    mcp_mode: str
    version: str


class UsageSummary(BaseModel):
    invocation_count: int
    failure_count: int
    average_latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    by_skill: dict[str, int]


class GovernanceCheck(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str


class GovernanceReport(BaseModel):
    generated_at: datetime
    status: Literal["pass", "warn", "fail"]
    skills_registered: int
    enabled_tools: int
    disabled_skills: list[str]
    resource_count: int
    prompt_count: int
    invocation_count: int
    failure_count: int
    average_latency_ms: float
    estimated_cost: float
    checks: list[GovernanceCheck]


class LocalSnapshot(BaseModel):
    path: str
    saved_at: datetime
    skills: int
    invocations: int
    audit_events: int
    metrics: int
