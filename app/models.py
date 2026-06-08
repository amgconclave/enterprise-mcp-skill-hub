from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

JsonDict = dict[str, Any]
SkillLifecycleStatus = Literal["draft", "validated", "promoted", "disabled"]
InvocationStatus = Literal["succeeded", "failed"]
PolicyRole = Literal["admin", "reviewer", "agent", "viewer"]
DataSensitivity = Literal["public", "internal", "confidential"]
PolicyDecisionValue = Literal["allow", "deny"]


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
    status: SkillLifecycleStatus = "draft"
    tags: list[str] = Field(default_factory=list)

    @field_validator("input_schema", "output_schema")
    @classmethod
    def schema_must_be_object(cls, value: JsonDict) -> JsonDict:
        if value.get("type") != "object":
            raise ValueError("schema must be a JSON schema object with type=object")
        if "properties" not in value:
            raise ValueError("schema must define properties")
        return value

    @model_validator(mode="after")
    def sync_lifecycle_with_enabled_flag(self) -> SkillManifest:
        if self.status == "disabled" or not self.enabled:
            self.status = "disabled"
            self.enabled = False
        elif self.status == "promoted":
            self.enabled = True
        return self


class SkillVersion(BaseModel):
    skill_id: str
    version: str
    manifest_hash: str
    created_at: datetime
    status: SkillLifecycleStatus


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
    policy_context: PolicyInvocationContext | None = None


class SkillStatusRequest(BaseModel):
    enabled: bool
    actor: str = "demo-user"


class PromoteSkillRequest(BaseModel):
    actor: str = "demo-user"


class AgentRunRequest(BaseModel):
    prompt: str
    actor: str = "demo-user"


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    manifest_id: str | None = None


class PolicyInvocationContext(BaseModel):
    role: PolicyRole = "agent"
    environment: str = "local"
    data_sensitivity: DataSensitivity = "internal"
    requested_action: str = "invoke"
    enforce: bool = False


class PolicySimulationRequest(BaseModel):
    skill_id: str
    role: PolicyRole
    environment: str = "local"
    data_sensitivity: DataSensitivity = "internal"
    requested_action: str = "invoke"


class PolicySimulationResult(BaseModel):
    skill_id: str
    role: PolicyRole
    environment: str
    data_sensitivity: DataSensitivity
    requested_action: str
    decision: PolicyDecisionValue
    reasons: list[str]
    matched_rules: list[str]


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


class SkillGovernanceRecord(BaseModel):
    skill_id: str
    version: str
    enabled: bool
    status: SkillLifecycleStatus
    schema_valid: bool
    schema_errors: list[str] = Field(default_factory=list)
    last_invocation: datetime | None = None
    invocation_count: int
    failure_count: int
    provider: str
    tags: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    policy_access: dict[str, list[DataSensitivity]] = Field(default_factory=dict)
    mcp_exposed: bool
    mcp_exposure_status: Literal["exposed", "not_exposed"]


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
    lifecycle_counts: dict[str, int]
    skills: list[SkillGovernanceRecord]


class LocalSnapshot(BaseModel):
    path: str
    saved_at: datetime
    skills: int
    invocations: int
    audit_events: int
    metrics: int


class GoldenExpectation(BaseModel):
    path: str
    operator: Literal["equals", "contains", "min_length", "exists"]
    value: Any | None = None


class GoldenEvalCase(BaseModel):
    id: str
    skill_id: str
    description: str
    input: JsonDict
    expectations: list[GoldenExpectation]
    tags: list[str] = Field(default_factory=list)


class GoldenEvalCaseResult(BaseModel):
    case_id: str
    skill_id: str
    status: Literal["pass", "fail"]
    score: float
    trace_id: str | None = None
    latency_ms: float
    failed_expectations: list[str] = Field(default_factory=list)


class GoldenEvalSuiteResult(BaseModel):
    run_id: str
    generated_at: datetime
    total_cases: int
    passed_cases: int
    failed_cases: int
    score: float
    average_latency_ms: float
    results: list[GoldenEvalCaseResult]
