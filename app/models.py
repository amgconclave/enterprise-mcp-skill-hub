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
SecurityReadinessStatus = Literal["ready", "needs_review", "blocked"]
InvocationSandboxDecisionValue = Literal["allow", "deny"]
InvocationSandboxRiskLabel = Literal["low", "medium", "high", "critical"]
SandboxExceptionStatus = Literal["pending", "approved", "denied"]
SandboxExceptionDecision = Literal["approve", "deny"]
InvocationSandboxActionClass = Literal[
    "skill_invocation",
    "resource_access",
    "prompt_render",
    "external_network",
    "filesystem_write",
    "process_spawn",
    "secret_access",
    "repo_mutation",
    "unknown",
]
TenantKey = Literal["healthcare", "fintech", "public_sector", "internal_demo"]
TenantPolicyDecision = Literal["allowed", "blocked", "review_required"]
TenantEntitlementDecisionValue = Literal["allow", "deny"]
MarketplaceListingStatus = Literal["approved", "promoted", "draft", "disabled"]
MarketplaceRiskLevel = Literal["low", "medium", "high"]
MarketplaceReviewState = Literal["none", "approval_required", "review_required", "blocked", "disabled_block"]
MarketplaceApprovalStatus = Literal["pending", "approved", "rejected", "blocked"]
MarketplaceDecision = Literal["approve", "reject"]
MarketplaceRolloutStage = Literal[
    "catalog_review",
    "owner_signoff",
    "tenant_canary",
    "tenant_general_availability",
    "blocked",
]
SkillCompatibilityStatus = Literal["compatible", "needs_review", "incompatible", "deprecated"]
SkillVersionDelta = Literal["initial", "patch", "minor", "major", "same", "non_semver"]
WorkflowReviewStatus = Literal["draft", "in_review", "approved", "rejected"]
WorkflowValidationStatus = Literal["valid", "warnings", "invalid"]
ReleaseChangeType = Literal["added", "changed", "removed"]
CapacityGuardrailStatus = Literal["valid", "invalid", "defaulted"]
CapacityFallbackBehavior = Literal["deny", "queue", "degrade", "manual_review"]
DependencyNodeType = Literal[
    "agent",
    "audit_history",
    "capacity_forecast",
    "prompt",
    "release_preview",
    "resource",
    "skill",
    "tool",
    "workflow_template",
]
DependencyChangeType = Literal["skill", "prompt", "resource", "workflow_template", "unknown"]
SkillIncidentScenario = Literal[
    "schema_breakage",
    "disabled_skill_invoked",
    "policy_denial_spike",
    "latency_capacity_breach",
    "workflow_dependency_failure",
]
SkillIncidentSeverity = Literal["sev1", "sev2", "sev3"]
CiDoctorCheckStatus = Literal["pass", "warn", "fail"]
CircuitBreakerState = Literal["closed", "open", "half_open"]
CircuitBreakerAction = Literal["open", "close", "half_open"]
PromptGovernanceSeverity = Literal["none", "low", "medium", "high", "critical"]
PromptGovernanceTargetType = Literal["prompt", "resource", "text", "sample"]
PrivacyRetentionSeverity = Literal["none", "low", "medium", "high", "critical"]
PrivacyRetentionSourceType = Literal[
    "invocation_input",
    "invocation_output",
    "audit_metadata",
    "sample",
    "text",
]
WorkerRunStatus = Literal["queued", "running", "succeeded", "failed"]
WorkerPoolKey = Literal["local_mock_general", "retrieval_heavy", "governance_review"]
WorkerQueueDecisionValue = Literal["admit", "queue", "reject"]
AgentCollaborationTurnStatus = Literal["succeeded", "failed", "skipped"]
AgentCollaborationRole = Literal[
    "intake_agent",
    "retrieval_agent",
    "synthesis_agent",
    "action_agent",
    "governance_reviewer",
]


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
    policy_context: PolicyInvocationContext | None = None
    policy_decision: PolicySimulationResult | None = None
    entitlement_decision: SkillEntitlementDecision | None = None
    sandbox_decision: InvocationSandboxDecision | None = None


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


class AgentHandoffDecision(BaseModel):
    from_agent: AgentCollaborationRole
    to_agent: AgentCollaborationRole
    skill_id: str
    reason: str
    approved: bool
    governance_checks: list[str] = Field(default_factory=list)
    trace_id: str


class AgentCollaborationTurn(BaseModel):
    turn_index: int
    agent_id: AgentCollaborationRole
    skill_id: str
    status: AgentCollaborationTurnStatus
    input: JsonDict
    output: JsonDict | None = None
    handoff: AgentHandoffDecision
    policy_decision: PolicySimulationResult | None = None
    trace_id: str
    latency_ms: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    error: str | None = None


class AgentCollaborationRequest(BaseModel):
    prompt: str = (
        "Classify this RFP request, find approved governance policy context, summarize the answer, "
        "and create owner action items for the platform team."
    )
    actor: str = "collaboration-demo-user"
    role: PolicyRole = "agent"
    environment: str = "local"
    data_sensitivity: DataSensitivity = "internal"
    enforce_policy: bool = True
    enforce_entitlements: bool = True


class AgentCollaborationRun(BaseModel):
    id: str
    prompt: str
    actor: str
    participants: list[JsonDict]
    shared_state: JsonDict
    turns: list[AgentCollaborationTurn]
    final_output: str
    token_usage: TokenUsage
    estimated_cost: float
    latency_ms: float
    readiness_status: SecurityReadinessStatus
    governance_summary: JsonDict
    limitations: list[str] = Field(default_factory=list)


class AgentCollaborationPackRequest(BaseModel):
    actor: str = "agent-platform-reviewer"


class AgentCollaborationPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class AgentSocietyEvalRequest(BaseModel):
    actor: str = "agent-society-evaluator"
    include_policy_denial_case: bool = True


class AgentSocietyEvalResult(BaseModel):
    eval_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    evaluated_runs: list[JsonDict]
    role_scorecard: list[JsonDict]
    memory_checks: list[JsonDict]
    tool_use_checks: list[JsonDict]
    handoff_checks: list[JsonDict]
    policy_gate_checks: list[JsonDict]
    recommendations: list[str] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AgentSocietyEvalPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


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


class AuditQueryRequest(BaseModel):
    action: str | None = None
    type: str | None = None
    actor: str | None = None
    skill_id: str | None = None
    workflow_template_id: str | None = None
    status: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    query: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AuditQueryResult(BaseModel):
    generated_at: datetime
    filters: JsonDict
    matched_events: list[JsonDict]
    counts_by_action: dict[str, int]
    counts_by_status: dict[str, int]
    related_invocations: list[SkillInvocation]
    related_release_evidence: list[JsonDict] = Field(default_factory=list)
    related_workflow_evidence: list[JsonDict] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    correlation_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ComplianceAttestationRequest(BaseModel):
    actor: str = "compliance-reviewer"


class ComplianceAttestationResult(BaseModel):
    attestation_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class CapacityForecastRequest(BaseModel):
    actor: str = "capacity-planner"
    forecast_days: int = Field(default=30, ge=1, le=365)
    traffic_multiplier: float = Field(default=1.0, ge=0.1, le=25.0)
    assumed_daily_workflow_runs: dict[str, int] = Field(default_factory=dict)
    assumed_daily_skill_invocations: dict[str, int] = Field(default_factory=dict)


class CapacityWorkflowDemand(BaseModel):
    template_id: str
    name: str
    projected_runs: int
    ordered_skill_ids: list[str]
    required_role: PolicyRole
    default_sensitivity: DataSensitivity
    validation_status: WorkflowValidationStatus


class CapacitySkillForecast(BaseModel):
    skill_id: str
    name: str
    version: str
    forecasted_invocations: int
    historical_invocations: int
    workflow_invocations: int
    direct_invocations: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost: float
    estimated_latency_p95_ms: float
    top_workflows: list[JsonDict] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    recommended_rate_limit_per_minute: int


class CapacityForecastResult(BaseModel):
    forecast_id: str
    generated_at: datetime
    horizon_days: int
    readiness_status: SecurityReadinessStatus
    assumptions: JsonDict
    summary: JsonDict
    per_skill: list[CapacitySkillForecast]
    top_workflows: list[CapacityWorkflowDemand]
    bottleneck_risk_flags: list[str] = Field(default_factory=list)
    recommended_rate_limits: dict[str, int] = Field(default_factory=dict)
    mcp_tools_affected: list[str] = Field(default_factory=list)
    release_evidence: JsonDict = Field(default_factory=dict)
    audit_evidence: JsonDict = Field(default_factory=dict)
    excluded_skills: JsonDict = Field(default_factory=dict)


class CapacityGuardrails(BaseModel):
    max_invocations_per_minute: int = 120
    max_tokens_per_day: int = 250_000
    max_latency_p95_ms: float = 1_500.0
    per_skill_quotas: dict[str, int] = Field(default_factory=dict)
    fallback_behavior: CapacityFallbackBehavior = "queue"
    policy_actions: list[str] = Field(default_factory=lambda: ["throttle", "alert", "require_review"])


class CapacityGuardrailsRequest(BaseModel):
    actor: str = "capacity-planner"
    guardrails: CapacityGuardrails | None = None
    write_config: bool = False


class CapacityGuardrailsResult(BaseModel):
    generated_at: datetime
    status: CapacityGuardrailStatus
    guardrails: CapacityGuardrails
    validation_errors: list[str] = Field(default_factory=list)
    config_path: str | None = None


class CapacityPlanExportRequest(BaseModel):
    actor: str = "capacity-planner"
    forecast_request: CapacityForecastRequest | None = None
    guardrails_request: CapacityGuardrailsRequest | None = None


class CapacityPlanExportResult(BaseModel):
    plan_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class TenantPolicySimulationRequest(BaseModel):
    tenant: TenantKey = "internal_demo"
    role: PolicyRole = "agent"
    environment: str = "local"
    data_sensitivity: DataSensitivity = "internal"
    requested_action: str = "invoke"


class TenantCapabilityDecision(BaseModel):
    id: str
    name: str
    kind: Literal["skill", "workflow"]
    decision: TenantPolicyDecision
    reasons: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    mcp_tools: list[str] = Field(default_factory=list)
    mcp_resources: list[str] = Field(default_factory=list)
    mcp_prompts: list[str] = Field(default_factory=list)


class TenantPolicySimulationResult(BaseModel):
    generated_at: datetime
    scenario: TenantPolicySimulationRequest
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    allowed_skills: list[TenantCapabilityDecision] = Field(default_factory=list)
    blocked_skills: list[TenantCapabilityDecision] = Field(default_factory=list)
    review_required_skills: list[TenantCapabilityDecision] = Field(default_factory=list)
    allowed_workflows: list[TenantCapabilityDecision] = Field(default_factory=list)
    blocked_workflows: list[TenantCapabilityDecision] = Field(default_factory=list)
    review_required_workflows: list[TenantCapabilityDecision] = Field(default_factory=list)
    policy_reasons: list[str] = Field(default_factory=list)
    impacted_mcp_tools: list[str] = Field(default_factory=list)
    impacted_mcp_resources: list[str] = Field(default_factory=list)
    impacted_mcp_prompts: list[str] = Field(default_factory=list)
    recommended_tenant_guardrails: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    excluded_skills: JsonDict = Field(default_factory=dict)
    excluded_workflows: JsonDict = Field(default_factory=dict)


class TenantSandboxExportRequest(BaseModel):
    actor: str = "tenant-policy-reviewer"
    scenarios: list[TenantPolicySimulationRequest] = Field(default_factory=list)


class TenantSandboxExportResult(BaseModel):
    sandbox_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class TenantSkillEntitlementPolicy(BaseModel):
    tenant_id: str
    skill_id: str = "*"
    allowed_roles: list[PolicyRole] = Field(default_factory=list)
    denied_roles: list[PolicyRole] = Field(default_factory=list)
    required_scopes: list[str] = Field(default_factory=lambda: ["skill.invoke"])
    allowed_environments: list[str] = Field(default_factory=lambda: ["local", "dev", "test"])
    allowed_data_sensitivities: list[DataSensitivity] = Field(
        default_factory=lambda: ["public", "internal"]
    )
    reason: str


class SkillEntitlementDecision(BaseModel):
    tenant_id: str
    user_id: str
    user_scopes: list[str] = Field(default_factory=list)
    skill_id: str
    role: PolicyRole
    environment: str
    data_sensitivity: DataSensitivity
    decision: TenantEntitlementDecisionValue
    reasons: list[str] = Field(default_factory=list)
    matched_policies: list[str] = Field(default_factory=list)
    missing_scopes: list[str] = Field(default_factory=list)
    allowed_roles: list[PolicyRole] = Field(default_factory=list)
    required_scopes: list[str] = Field(default_factory=list)


class TenantEntitlementMatrixRequest(BaseModel):
    tenant_id: str = "internal_demo"
    user_id: str = "demo-user"
    role: PolicyRole = "agent"
    environment: str = "local"
    data_sensitivity: DataSensitivity = "internal"
    user_scopes: list[str] = Field(default_factory=lambda: ["skill.invoke"])
    skill_ids: list[str] = Field(default_factory=list)


class TenantEntitlementMatrixResult(BaseModel):
    generated_at: datetime
    request: TenantEntitlementMatrixRequest
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    decisions: list[SkillEntitlementDecision] = Field(default_factory=list)
    policies: list[TenantSkillEntitlementPolicy] = Field(default_factory=list)
    mcp_safe_tool_names: list[str] = Field(default_factory=list)
    denied_skill_ids: list[str] = Field(default_factory=list)
    reviewer_notes: list[str] = Field(default_factory=list)


class TenantEntitlementPackRequest(BaseModel):
    actor: str = "entitlement-reviewer"
    scenarios: list[TenantEntitlementMatrixRequest] = Field(default_factory=list)


class TenantEntitlementPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class TenantEntitlementCoverageRecord(BaseModel):
    tenant_id: str
    skill_id: str
    mcp_exposed: bool
    coverage_status: Literal["exact_policy", "wildcard_policy", "missing_policy"]
    has_exact_policy: bool
    uses_wildcard_policy: bool
    matched_policy_ids: list[str] = Field(default_factory=list)
    denied_audit_count: int = 0
    reviewer_action: str


class TenantEntitlementCoverageResult(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    tenants: list[str] = Field(default_factory=list)
    promoted_skill_ids: list[str] = Field(default_factory=list)
    records: list[TenantEntitlementCoverageRecord] = Field(default_factory=list)
    review_required: list[TenantEntitlementCoverageRecord] = Field(default_factory=list)
    denied_audit_events: list[JsonDict] = Field(default_factory=list)
    reviewer_notes: list[str] = Field(default_factory=list)


class TenantEntitlementReviewPackRequest(BaseModel):
    actor: str = "entitlement-reviewer"


class TenantEntitlementReviewPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class TenantEntitlementAccessReviewRequest(BaseModel):
    actor: str = "entitlement-access-reviewer"
    max_steps: int = Field(default=5, ge=1, le=10)


class TenantEntitlementAccessReviewResult(BaseModel):
    review_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    observations: JsonDict
    privileged_access_rows: list[JsonDict] = Field(default_factory=list)
    break_glass_drill: JsonDict = Field(default_factory=dict)
    bounded_steps: list[JsonDict] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    patterns_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TenantEntitlementAccessReviewPackRequest(BaseModel):
    actor: str = "entitlement-access-reviewer"
    max_steps: int = Field(default=5, ge=1, le=10)


class TenantEntitlementAccessReviewPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class MarketplaceTenantEligibility(BaseModel):
    scenario_id: str
    tenant: TenantKey
    environment: str
    role: PolicyRole
    data_sensitivity: DataSensitivity
    decision: TenantPolicyDecision
    reasons: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)


class MarketplaceSkillListing(BaseModel):
    skill_id: str
    name: str
    version: str
    listing_status: MarketplaceListingStatus
    lifecycle_status: SkillLifecycleStatus
    enabled: bool
    provider: str
    tags: list[str] = Field(default_factory=list)
    versions: list[JsonDict] = Field(default_factory=list)
    tenant_eligibility: list[MarketplaceTenantEligibility] = Field(default_factory=list)
    risk_level: MarketplaceRiskLevel
    risk_flags: list[str] = Field(default_factory=list)
    required_review_state: MarketplaceReviewState
    usage_signals: JsonDict = Field(default_factory=dict)
    mcp_exposure_state: JsonDict = Field(default_factory=dict)
    coverage_summary: JsonDict = Field(default_factory=dict)
    version_comparison_notes: list[str] = Field(default_factory=list)


class MarketplaceCatalogResult(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    listings: list[MarketplaceSkillListing]
    tenant_scenarios: list[JsonDict]
    coverage_summary: JsonDict
    disabled_skill_blocks: list[JsonDict] = Field(default_factory=list)
    review_required_rollouts: list[JsonDict] = Field(default_factory=list)
    blocked_rollouts: list[JsonDict] = Field(default_factory=list)
    usage_summary: UsageSummary
    limitations: list[str] = Field(default_factory=list)


class MarketplaceRolloutPackRequest(BaseModel):
    actor: str = "marketplace-reviewer"


class MarketplaceRolloutPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class MarketplaceApprovalSubmitRequest(BaseModel):
    skill_id: str = "summarize_document"
    tenant_scenario_id: str = "internal_ops_local"
    actor: str = "marketplace-reviewer"
    owner: str = "platform-owner"
    owner_role: str = "platform_owner"
    note: str | None = None


class MarketplaceApprovalDecisionRequest(BaseModel):
    actor: str = "marketplace-reviewer"
    decision: MarketplaceDecision = "approve"
    owner_signoff: bool = True
    note: str | None = None


class MarketplaceStageAdvanceRequest(BaseModel):
    actor: str = "marketplace-release-manager"
    next_stage: MarketplaceRolloutStage = "tenant_canary"
    note: str | None = None


class MarketplaceApprovalPackRequest(BaseModel):
    actor: str = "marketplace-reviewer"


class MarketplacePromotionGateResult(BaseModel):
    generated_at: datetime
    skill_id: str
    tenant_scenario_id: str
    actor: str
    readiness_status: SecurityReadinessStatus
    can_promote: bool
    decision: Literal["allow", "review_required", "block"]
    listing_snapshot: JsonDict
    approval_evidence: JsonDict
    checks: list[JsonDict] = Field(default_factory=list)
    failed_check_ids: list[str] = Field(default_factory=list)
    warning_check_ids: list[str] = Field(default_factory=list)
    remediation_steps: list[JsonDict] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class MarketplaceApprovalRecord(BaseModel):
    approval_id: str
    skill_id: str
    tenant_scenario_id: str
    status: MarketplaceApprovalStatus
    current_stage: MarketplaceRolloutStage
    requested_by: str
    owner: str
    owner_role: str
    created_at: datetime
    updated_at: datetime
    trace_id: str
    listing_snapshot: JsonDict
    tenant_decision: JsonDict
    promotion_checks: list[JsonDict] = Field(default_factory=list)
    required_signoffs: list[JsonDict] = Field(default_factory=list)
    signoffs: list[JsonDict] = Field(default_factory=list)
    rollout_stages: list[JsonDict] = Field(default_factory=list)
    reviewer_notes: list[str] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)


class MarketplaceApprovalQueueResult(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    approval_records: list[MarketplaceApprovalRecord] = Field(default_factory=list)
    catalog_promotion_checks: list[JsonDict] = Field(default_factory=list)
    rollout_stage_policy: list[JsonDict] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class MarketplaceApprovalPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class SkillCompatibilityRecord(BaseModel):
    skill_id: str
    name: str
    current_version: str
    previous_version: str | None = None
    semantic_version_valid: bool
    version_delta: SkillVersionDelta
    compatibility_status: SkillCompatibilityStatus
    deprecated: bool = False
    deprecation_warnings: list[str] = Field(default_factory=list)
    schema_compatibility: JsonDict = Field(default_factory=dict)
    migration_recommendations: list[str] = Field(default_factory=list)
    mcp_exposure_state: JsonDict = Field(default_factory=dict)
    evidence: list[JsonDict] = Field(default_factory=list)


class SkillCompatibilityReport(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    records: list[SkillCompatibilityRecord]
    compatibility_matrix: list[JsonDict] = Field(default_factory=list)
    deprecated_skill_warnings: list[JsonDict] = Field(default_factory=list)
    migration_recommendations: list[JsonDict] = Field(default_factory=list)
    coverage_summary: JsonDict = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class SkillCompatibilityPackRequest(BaseModel):
    actor: str = "compatibility-reviewer"
    skill_ids: list[str] = Field(default_factory=list)


class SkillCompatibilityPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class UsageAnalyticsResult(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    usage_by_skill: list[JsonDict] = Field(default_factory=list)
    usage_by_tenant_environment: list[JsonDict] = Field(default_factory=list)
    usage_by_agent: list[JsonDict] = Field(default_factory=list)
    usage_by_status: dict[str, int] = Field(default_factory=dict)
    usage_by_mcp_exposure: dict[str, int] = Field(default_factory=dict)
    latency_bands: list[JsonDict] = Field(default_factory=list)
    token_cost_estimates: JsonDict = Field(default_factory=dict)
    budget_status: list[JsonDict] = Field(default_factory=list)
    anomalies: list[JsonDict] = Field(default_factory=list)
    disabled_skill_blocked_events: list[JsonDict] = Field(default_factory=list)
    coverage_summary: JsonDict = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class UsageChargebackPackRequest(BaseModel):
    actor: str = "finops-reviewer"


class UsageChargebackPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class CircuitBreakerActionRequest(BaseModel):
    action: CircuitBreakerAction
    actor: str = "platform-sre"
    reason: str | None = None


class SkillReliabilityRecord(BaseModel):
    skill_id: str
    name: str
    version: str
    lifecycle_status: SkillLifecycleStatus
    enabled: bool
    mcp_exposed: bool
    circuit_state: CircuitBreakerState
    recommended_action: str
    recommendation_reason: str
    total_invocations: int
    success_count: int
    failure_count: int
    blocked_count: int
    consecutive_failures: int
    failure_rate: float
    average_latency_ms: float
    p95_latency_ms: float
    latency_slo_ms: float
    latency_breach_count: int
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    recent_failures: list[JsonDict] = Field(default_factory=list)
    audit_trace_ids: list[str] = Field(default_factory=list)


class SkillReliabilityReport(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    skills: list[SkillReliabilityRecord]
    disable_recommendations: list[JsonDict] = Field(default_factory=list)
    re_enable_recommendations: list[JsonDict] = Field(default_factory=list)
    circuit_breaker_events: list[JsonDict] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SkillReliabilityPackRequest(BaseModel):
    actor: str = "platform-sre"


class SkillReliabilityPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class SkillSloRecord(BaseModel):
    skill_id: str
    name: str
    version: str
    enabled: bool
    mcp_exposed: bool
    objective_name: str
    availability_slo_pct: float
    success_rate_pct: float
    error_budget_pct: float
    error_budget_remaining_pct: float
    error_budget_burn_pct: float
    latency_slo_ms: float
    p95_latency_ms: float
    latency_budget_remaining_ms: float
    total_observations: int
    failed_observations: int
    blocked_observations: int
    error_budget_status: str
    release_gate: str
    recommended_action: str
    evidence_trace_ids: list[str] = Field(default_factory=list)


class SkillSloReport(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    objectives: JsonDict
    skills: list[SkillSloRecord]
    burn_rate_alerts: list[JsonDict] = Field(default_factory=list)
    release_gate: JsonDict
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SkillSloPackRequest(BaseModel):
    actor: str = "slo-reviewer"


class SkillSloPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class ProviderReadinessReport(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    current_provider: JsonDict
    provider_checks: list[JsonDict] = Field(default_factory=list)
    fallback_matrix: list[JsonDict] = Field(default_factory=list)
    skill_provider_inventory: list[JsonDict] = Field(default_factory=list)
    summary: JsonDict
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ProviderFallbackPackRequest(BaseModel):
    actor: str = "provider-reviewer"


class ProviderFallbackPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


ProviderFailoverFailureMode = Literal[
    "provider_unavailable",
    "missing_credentials",
    "rate_limited",
    "budget_exceeded",
    "policy_rejected",
]
ProviderFailoverDecisionValue = Literal["primary_allowed", "fallback_to_mock", "blocked"]


class ProviderFailoverScenario(BaseModel):
    skill_id: str = "summarize_document"
    requested_provider: str = "openai"
    failure_mode: ProviderFailoverFailureMode = "provider_unavailable"
    tenant_id: str = "internal_demo"
    actor: str = "provider-drill-reviewer"


class ProviderFailoverDrillRequest(BaseModel):
    actor: str = "provider-drill-reviewer"
    scenarios: list[ProviderFailoverScenario] = Field(default_factory=list)
    include_recent_traces: bool = True


class ProviderFailoverDecision(BaseModel):
    scenario_id: str
    skill_id: str
    requested_provider: str
    failure_mode: ProviderFailoverFailureMode
    decision: ProviderFailoverDecisionValue
    selected_provider: str | None = None
    fallback_provider: str | None = None
    reviewer_required: bool = False
    network_calls_performed: int = 0
    estimated_cost_delta: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    governance_checks: list[JsonDict] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    replay_command: str


class ProviderFailoverDrillResult(BaseModel):
    drill_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    decisions: list[ProviderFailoverDecision] = Field(default_factory=list)
    provider_readiness: ProviderReadinessReport
    runbook_steps: list[JsonDict] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ProviderFailoverPackRequest(BaseModel):
    actor: str = "provider-drill-reviewer"
    drill_request: ProviderFailoverDrillRequest | None = None


class ProviderFailoverPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class ConfigVariableRecord(BaseModel):
    name: str
    required_for: str
    present_in_env_example: bool
    present_in_process: bool
    secret: bool
    placeholder_safe: bool
    exported_value: str
    recommendation: str


class ConfigHygieneReport(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    variables: list[ConfigVariableRecord]
    provider_gate: JsonDict
    gitignore_checks: list[JsonDict] = Field(default_factory=list)
    secret_findings: list[JsonDict] = Field(default_factory=list)
    rotation_plan: list[JsonDict] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ConfigHygienePackRequest(BaseModel):
    actor: str = "config-security-reviewer"


class ConfigHygienePackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class PromptGovernanceValidationRequest(BaseModel):
    content: str
    target_id: str = "ad_hoc"
    target_type: PromptGovernanceTargetType = "text"
    actor: str = "prompt-security-reviewer"


class PromptGovernanceFinding(BaseModel):
    finding_id: str
    target_type: PromptGovernanceTargetType
    target_id: str
    severity: PromptGovernanceSeverity
    category: str
    pattern: str
    description: str
    matched_excerpt: str
    approval_required: bool
    recommended_action: str
    control: str


class PromptGovernanceTargetResult(BaseModel):
    target_type: PromptGovernanceTargetType
    target_id: str
    name: str
    content_hash: str
    max_severity: PromptGovernanceSeverity
    approval_required: bool
    finding_count: int
    categories: list[str] = Field(default_factory=list)
    findings: list[PromptGovernanceFinding] = Field(default_factory=list)


class PromptGovernanceReport(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    targets: list[PromptGovernanceTargetResult]
    high_risk_findings: list[PromptGovernanceFinding] = Field(default_factory=list)
    approval_required_targets: list[JsonDict] = Field(default_factory=list)
    endpoint_review: list[JsonDict] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PromptGovernancePackRequest(BaseModel):
    actor: str = "prompt-security-reviewer"


class PromptGovernancePackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class PromptGovernanceRemediationRequest(BaseModel):
    actor: str = "prompt-remediation-reviewer"
    include_low_risk: bool = False


class PromptGovernanceRemediationStep(BaseModel):
    step_id: str
    target_type: PromptGovernanceTargetType
    target_id: str
    severity: PromptGovernanceSeverity
    category: str
    action: str
    owner_role: str
    approval_gate: str
    verification_command: str
    completion_signal: str
    source_finding_ids: list[str] = Field(default_factory=list)


class PromptGovernanceRemediationPlan(BaseModel):
    plan_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    steps: list[PromptGovernanceRemediationStep]
    bounded_action_loop: list[JsonDict] = Field(default_factory=list)
    approval_queue: list[JsonDict] = Field(default_factory=list)
    run_transparency: list[JsonDict] = Field(default_factory=list)
    audit_evidence: list[JsonDict] = Field(default_factory=list)
    json_path: str
    markdown_path: str
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PrivacyRetentionFinding(BaseModel):
    finding_id: str
    source_type: PrivacyRetentionSourceType
    source_id: str
    field_path: str
    severity: PrivacyRetentionSeverity
    category: str
    matched_excerpt: str
    redacted_excerpt: str
    recommended_action: str
    retention_action: str
    control: str


class PrivacyRetentionRecord(BaseModel):
    source_type: PrivacyRetentionSourceType
    source_id: str
    skill_id: str | None = None
    trace_id: str | None = None
    created_at: datetime | None = None
    content_hash: str
    max_severity: PrivacyRetentionSeverity
    finding_count: int
    categories: list[str] = Field(default_factory=list)
    recommended_retention: str
    redacted_preview: JsonDict
    findings: list[PrivacyRetentionFinding] = Field(default_factory=list)


class PrivacyRetentionReport(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    records: list[PrivacyRetentionRecord]
    high_risk_findings: list[PrivacyRetentionFinding] = Field(default_factory=list)
    deletion_candidates: list[JsonDict] = Field(default_factory=list)
    redaction_samples: list[JsonDict] = Field(default_factory=list)
    retention_policy: JsonDict = Field(default_factory=dict)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PrivacyRedactionRequest(BaseModel):
    payload: JsonDict
    source_id: str = "ad_hoc_payload"
    actor: str = "privacy-reviewer"


class PrivacyRedactionResult(BaseModel):
    source_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    redacted_payload: JsonDict
    findings: list[PrivacyRetentionFinding] = Field(default_factory=list)
    summary: JsonDict


class PrivacyRetentionPackRequest(BaseModel):
    actor: str = "privacy-reviewer"


class PrivacyRetentionPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class EnterpriseReadinessCategoryScore(BaseModel):
    category: str
    score: int = Field(ge=0, le=100)
    readiness_status: SecurityReadinessStatus
    signals: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class EnterpriseReadinessScorecard(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    overall_score: int = Field(ge=0, le=100)
    category_scores: list[EnterpriseReadinessCategoryScore]
    risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    artifact_links: list[JsonDict] = Field(default_factory=list)
    mcp_capability_counts: JsonDict
    verification_commands: list[str] = Field(default_factory=list)
    summary: JsonDict = Field(default_factory=dict)


class EnterprisePortfolioDemoPackRequest(BaseModel):
    actor: str = "portfolio-reviewer"


class EnterprisePortfolioDemoPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class PortfolioEvidenceIndexResult(BaseModel):
    index_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    evidence_score: int = Field(ge=0, le=100)
    jd_skill_count: int
    proof_count: int
    jd_coverage: list[JsonDict]
    proof_matrix: list[JsonDict]
    mcp_capability_counts: JsonDict
    artifact_inventory: list[JsonDict] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    summary: JsonDict = Field(default_factory=dict)


class PortfolioInterviewPackRequest(BaseModel):
    actor: str = "portfolio-interviewer"


class PortfolioInterviewPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    evidence_score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class ReviewerQuickstartResult(BaseModel):
    quickstart_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    setup_commands: list[str] = Field(default_factory=list)
    one_command_demo: JsonDict
    verification_commands: list[str] = Field(default_factory=list)
    endpoint_walkthrough: list[JsonDict] = Field(default_factory=list)
    mcp_command_walkthrough: list[JsonDict] = Field(default_factory=list)
    artifact_proof_map: list[JsonDict] = Field(default_factory=list)
    expected_outputs: list[JsonDict] = Field(default_factory=list)
    troubleshooting: list[str] = Field(default_factory=list)
    role_specific_notes: list[JsonDict] = Field(default_factory=list)
    summary: JsonDict = Field(default_factory=dict)


class ReviewerWalkthroughPackRequest(BaseModel):
    actor: str = "github-reviewer"


class ReviewerWalkthroughPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    quickstart_step_count: int
    json_path: str
    markdown_path: str
    summary: JsonDict


class ArtifactInventoryItem(BaseModel):
    artifact_id: str
    name: str
    directory: str
    expected_files: list[str] = Field(default_factory=list)
    latest_files: list[JsonDict] = Field(default_factory=list)
    producer_endpoint: str | None = None
    producer_command: str | None = None
    ignored_status: str
    reviewer_purpose: str
    freshness_notes: str
    mcp_specific: bool = True
    generated: bool = False


class ArtifactInventoryResult(BaseModel):
    inventory_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    artifact_count: int
    generated_directory_count: int
    ignored_directory_count: int
    items: list[ArtifactInventoryItem] = Field(default_factory=list)
    readme_badge_suggestions: list[JsonDict] = Field(default_factory=list)
    reviewer_proof_checklist: list[JsonDict] = Field(default_factory=list)
    local_commands: list[str] = Field(default_factory=list)
    cleanup_regeneration_notes: list[str] = Field(default_factory=list)
    summary: JsonDict = Field(default_factory=dict)


class ArtifactReadmeChecklistRequest(BaseModel):
    actor: str = "github-reviewer"


class ArtifactReadmeChecklistResult(BaseModel):
    checklist_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    inventory_count: int
    json_path: str
    markdown_path: str
    summary: JsonDict


class GovernedSkillPlatformPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    architecture_patterns: list[str] = Field(default_factory=list)
    capability_controls: list[JsonDict] = Field(default_factory=list)
    workflow_durability: JsonDict = Field(default_factory=dict)
    human_review_queue: JsonDict = Field(default_factory=dict)
    provider_flexibility: JsonDict = Field(default_factory=dict)
    tool_governance: JsonDict = Field(default_factory=dict)
    cost_and_trace_governance: JsonDict = Field(default_factory=dict)
    handoff_readiness: JsonDict = Field(default_factory=dict)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class GovernedSkillPlatformPackRequest(BaseModel):
    actor: str = "platform-owner"


class GovernedSkillPlatformPackExportResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class ReviewSlaItem(BaseModel):
    item_id: str
    queue: Literal["workflow_review", "marketplace_approval", "sandbox_exception"]
    subject: str
    raw_status: str
    sla_status: Literal["on_track", "due_soon", "breached", "closed"]
    escalation_level: Literal["none", "watch", "escalate"]
    owner: str
    submitted_at: datetime
    updated_at: datetime
    age_hours: float
    sla_hours: float
    time_remaining_hours: float
    recommended_action: str
    evidence_refs: list[JsonDict] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    source_payload: JsonDict = Field(default_factory=dict)


class ReviewSlaReport(BaseModel):
    report_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    queue_summaries: list[JsonDict] = Field(default_factory=list)
    items: list[ReviewSlaItem] = Field(default_factory=list)
    escalation_policy: list[JsonDict] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReviewSlaPackRequest(BaseModel):
    actor: str = "review-ops-owner"
    workflow_review_sla_hours: float = Field(default=24.0, ge=0.0)
    marketplace_approval_sla_hours: float = Field(default=48.0, ge=0.0)
    sandbox_exception_sla_hours: float = Field(default=8.0, ge=0.0)
    due_soon_ratio: float = Field(default=0.25, ge=0.0, le=1.0)


class ReviewSlaPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class WorkerRunTimelineEvent(BaseModel):
    timestamp: datetime
    status: WorkerRunStatus
    stage: str
    message: str
    metadata: JsonDict = Field(default_factory=dict)


class WorkerSkillRunRequest(BaseModel):
    skill_id: str = "search_knowledge_base"
    input: JsonDict = Field(default_factory=lambda: {"query": "AI governance policy", "limit": 2})
    actor: str = "platform-worker"
    tenant: TenantKey = "internal_demo"
    worker_pool: WorkerPoolKey = "local_mock_general"
    priority: int = Field(default=5, ge=1, le=10)
    policy_context: PolicyInvocationContext | None = None
    enforce_sandbox: bool = True
    allow_queue: bool = True
    max_queue_wait_ms: int = Field(default=30_000, ge=0, le=300_000)


class WorkerQueueAdmissionDecision(BaseModel):
    decision_id: str
    generated_at: datetime
    decision: WorkerQueueDecisionValue
    tenant: TenantKey
    skill_id: str
    worker_pool: WorkerPoolKey
    priority: int
    queue_position: int | None = None
    estimated_wait_ms: int = 0
    fairness_share: JsonDict = Field(default_factory=dict)
    pool_pressure: JsonDict = Field(default_factory=dict)
    matched_rules: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    trace_id: str


class WorkerSkillRunRecord(BaseModel):
    run_id: str
    created_at: datetime
    updated_at: datetime
    status: WorkerRunStatus
    skill_id: str
    actor: str
    worker_pool: WorkerPoolKey
    priority: int
    input: JsonDict
    trace_id: str
    invocation_id: str | None = None
    output: JsonDict | None = None
    error: str | None = None
    queue_decision: WorkerQueueAdmissionDecision | None = None
    sandbox_decision: InvocationSandboxDecision | None = None
    timeline: list[WorkerRunTimelineEvent] = Field(default_factory=list)
    transparency: JsonDict = Field(default_factory=dict)


class WorkerPoolStatus(BaseModel):
    pool_id: WorkerPoolKey
    display_name: str
    worker_count: int
    max_concurrency: int
    active_runs: int
    queued_runs: int
    supported_action_classes: list[InvocationSandboxActionClass] = Field(default_factory=list)
    isolation_profile: JsonDict = Field(default_factory=dict)
    scale_recommendation: JsonDict = Field(default_factory=dict)


class WorkerScalePlanResult(BaseModel):
    plan_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    pools: list[WorkerPoolStatus] = Field(default_factory=list)
    backlog_by_skill: list[JsonDict] = Field(default_factory=list)
    recommendations: list[JsonDict] = Field(default_factory=list)
    recent_runs: list[WorkerSkillRunRecord] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class WorkerQueueAdmissionReport(BaseModel):
    report_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    admission_policy: JsonDict
    pool_queue_status: list[JsonDict] = Field(default_factory=list)
    tenant_fairness: list[JsonDict] = Field(default_factory=list)
    recent_decisions: list[WorkerQueueAdmissionDecision] = Field(default_factory=list)
    recommendations: list[JsonDict] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class WorkerQueueAdmissionPackRequest(BaseModel):
    actor: str = "platform-sre"


class WorkerQueueAdmissionPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class WorkerRunbookPackRequest(BaseModel):
    actor: str = "platform-sre"


class WorkerRunbookPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class ApiContractCheck(BaseModel):
    id: str
    category: str
    status: CiDoctorCheckStatus
    title: str
    detail: str
    evidence: list[str] = Field(default_factory=list)
    remediation: str | None = None


class ApiContractAuditResult(BaseModel):
    audit_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    checks: list[ApiContractCheck] = Field(default_factory=list)
    openapi_route_count: int
    auth_protected_endpoint_count: int
    endpoint_inventory_by_domain: JsonDict
    docs_api_coverage: list[JsonDict] = Field(default_factory=list)
    dashboard_smoke_alignment: JsonDict
    generated_artifact_endpoint_coverage: list[JsonDict] = Field(default_factory=list)
    demo_flow_endpoint_coverage: list[JsonDict] = Field(default_factory=list)
    mcp_inventory: JsonDict
    mcp_coverage: JsonDict
    contract_drift: JsonDict = Field(default_factory=dict)
    missing_docs_warnings: list[str] = Field(default_factory=list)
    deprecated_duplicate_route_warnings: list[str] = Field(default_factory=list)
    local_only_limitations: list[str] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)


class ApiReviewerCollectionRequest(BaseModel):
    actor: str = "api-contract-reviewer"


class ApiReviewerCollectionResult(BaseModel):
    collection_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class ApiContractDriftPackRequest(BaseModel):
    actor: str = "contract-drift-reviewer"


class ApiContractDriftPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class ApiContractRemediationRunRequest(BaseModel):
    actor: str = "contract-remediation-reviewer"
    max_steps: int = Field(default=6, ge=1, le=12)
    include_pack_export: bool = False


class ApiContractRemediationRunResult(BaseModel):
    run_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    observations: JsonDict
    bounded_steps: list[JsonDict] = Field(default_factory=list)
    remediation_backlog: list[JsonDict] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    patterns_used: list[str] = Field(default_factory=list)
    artifacts: JsonDict = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class ApiContractRemediationPackRequest(BaseModel):
    actor: str = "contract-remediation-reviewer"
    max_steps: int = Field(default=6, ge=1, le=12)


class ApiContractRemediationPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class TaskRunLedgerEntry(BaseModel):
    run_id: str
    run_type: Literal[
        "skill_invocation",
        "worker_run",
        "sandbox_decision",
        "sandbox_exception",
        "audit_event",
    ]
    source: str
    status: str
    actor: str
    resource_type: str
    resource_id: str
    skill_id: str | None = None
    trace_id: str
    created_at: datetime
    updated_at: datetime
    checkpoint_count: int
    timeline: list[JsonDict] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    governance_links: JsonDict = Field(default_factory=dict)
    replay_commands: list[str] = Field(default_factory=list)
    summary: JsonDict = Field(default_factory=dict)


class TaskRunObservabilityResult(BaseModel):
    ledger_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    observations: JsonDict
    ledger: list[TaskRunLedgerEntry] = Field(default_factory=list)
    bounded_action_loop: list[JsonDict] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    patterns_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TaskRunTransparencyPackRequest(BaseModel):
    actor: str = "run-transparency-reviewer"


class TaskRunTransparencyPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class AuditIntegrityRecord(BaseModel):
    sequence: int
    record_id: str
    record_type: Literal["audit_event", "skill_invocation"]
    source: str
    action: str
    actor: str
    resource_type: str
    resource_id: str
    trace_id: str
    created_at: datetime
    previous_hash: str
    content_hash: str
    chain_hash: str
    verification_status: Literal["valid", "warning", "invalid"]
    risk_flags: list[str] = Field(default_factory=list)
    replay_commands: list[str] = Field(default_factory=list)
    summary: JsonDict = Field(default_factory=dict)


class AuditIntegrityReport(BaseModel):
    report_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    root_hash: str
    summary: JsonDict
    records: list[AuditIntegrityRecord] = Field(default_factory=list)
    gaps: list[JsonDict] = Field(default_factory=list)
    tamper_warnings: list[JsonDict] = Field(default_factory=list)
    verification_commands: list[str] = Field(default_factory=list)
    patterns_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AuditIntegrityPackRequest(BaseModel):
    actor: str = "audit-integrity-reviewer"


class AuditIntegrityPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    root_hash: str
    json_path: str
    markdown_path: str
    summary: JsonDict


class FinalAuditCheck(BaseModel):
    id: str
    category: str
    status: CiDoctorCheckStatus
    title: str
    detail: str
    evidence: list[str] = Field(default_factory=list)
    remediation: str | None = None


class FinalAuditResult(BaseModel):
    audit_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    checks: list[FinalAuditCheck] = Field(default_factory=list)
    endpoint_inventory_summary: JsonDict
    mcp_inventory_summary: JsonDict
    artifact_inventory_summary: JsonDict
    verification_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class FinalHandoffPackRequest(BaseModel):
    actor: str = "final-handoff-reviewer"


class FinalHandoffPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class GitReadinessResult(BaseModel):
    readiness_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    git_repository: JsonDict
    worktree_summary: JsonDict
    generated_artifact_directories: list[JsonDict] = Field(default_factory=list)
    changed_file_groups: JsonDict = Field(default_factory=dict)
    suspicious_files: list[JsonDict] = Field(default_factory=list)
    required_publish_checks: list[JsonDict] = Field(default_factory=list)
    dirty_worktree_guidance: list[str] = Field(default_factory=list)
    recommended_commit_groups: list[JsonDict] = Field(default_factory=list)
    mcp_publish_notes: list[str] = Field(default_factory=list)
    non_destructive_review_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class GitPushPlanRequest(BaseModel):
    actor: str = "github-reviewer"


class GitPushPlanResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class RepositoryAutomationPlanRequest(BaseModel):
    actor: str = "repo-automation-reviewer"
    target_branch: str = "main"
    include_mutating_commands: bool = False


class RepositoryAutomationTask(BaseModel):
    task_id: str
    title: str
    action_class: InvocationSandboxActionClass
    sandbox_decision: InvocationSandboxDecisionValue
    dry_run_only: bool = True
    changed_paths: list[str] = Field(default_factory=list)
    planned_commands: list[str] = Field(default_factory=list)
    required_checks: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    timeline: list[JsonDict] = Field(default_factory=list)
    manual_approval_required: bool = True


class RepositoryAutomationPlanResult(BaseModel):
    plan_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    repository: JsonDict
    sandbox_policy: JsonDict
    automation_tasks: list[RepositoryAutomationTask] = Field(default_factory=list)
    transparent_runbook: list[JsonDict] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RepositoryAutomationPackRequest(BaseModel):
    actor: str = "repo-automation-reviewer"
    target_branch: str = "main"


class RepositoryAutomationPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class SmokeMatrixEndpoint(BaseModel):
    area: str
    method: str
    path: str
    auth_required: bool
    expected_status: int
    sample_command: str
    artifact_expectations: list[str] = Field(default_factory=list)
    readiness_signal: str


class SmokeMatrixResult(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    endpoint_matrix: list[SmokeMatrixEndpoint]
    artifact_expectations: list[JsonDict] = Field(default_factory=list)
    readiness_summary: JsonDict
    verification_commands: list[str] = Field(default_factory=list)


class LaunchChecklistRequest(BaseModel):
    actor: str = "launch-reviewer"


class LaunchChecklistResult(BaseModel):
    checklist_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class DashboardSmokeCheck(BaseModel):
    id: str
    category: str
    status: CiDoctorCheckStatus
    title: str
    detail: str
    evidence: list[str] = Field(default_factory=list)
    remediation: str | None = None


class DashboardSmokeResult(BaseModel):
    smoke_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    checks: list[DashboardSmokeCheck] = Field(default_factory=list)
    expected_views: list[JsonDict] = Field(default_factory=list)
    endpoint_references: list[JsonDict] = Field(default_factory=list)
    generated_artifact_tabs: list[JsonDict] = Field(default_factory=list)
    local_run_commands: list[str] = Field(default_factory=list)
    mcp_proof_surfaces: list[JsonDict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class UiVerificationPackRequest(BaseModel):
    actor: str = "github-reviewer"


class UiVerificationPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class RuntimeDemoReadinessResult(BaseModel):
    readiness_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    local_run_commands: list[str] = Field(default_factory=list)
    start_commands: list[JsonDict] = Field(default_factory=list)
    stop_commands: list[JsonDict] = Field(default_factory=list)
    expected_ports: list[JsonDict] = Field(default_factory=list)
    env_requirements: list[JsonDict] = Field(default_factory=list)
    dependency_checks: list[JsonDict] = Field(default_factory=list)
    port_checks: list[JsonDict] = Field(default_factory=list)
    health_urls: list[JsonDict] = Field(default_factory=list)
    smoke_urls: list[JsonDict] = Field(default_factory=list)
    mcp_verification_commands: list[JsonDict] = Field(default_factory=list)
    demo_flow_order: list[JsonDict] = Field(default_factory=list)
    troubleshooting: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)


class RuntimeDemoPackRequest(BaseModel):
    actor: str = "runtime-demo-reviewer"


class RuntimeDemoPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class DependencyNode(BaseModel):
    id: str
    type: DependencyNodeType
    label: str
    metadata: JsonDict = Field(default_factory=dict)


class DependencyEdge(BaseModel):
    source: str
    target: str
    type: str
    evidence: str
    weight: int = 1
    metadata: JsonDict = Field(default_factory=dict)


class DependencyMapResult(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    nodes: list[DependencyNode]
    edges: list[DependencyEdge]
    counts_by_node_type: dict[str, int]
    high_centrality_skills: list[JsonDict]
    orphaned_resources: list[str] = Field(default_factory=list)
    orphaned_prompts: list[str] = Field(default_factory=list)
    excluded_skills: JsonDict = Field(default_factory=dict)
    summary: JsonDict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class BlastRadiusRequest(BaseModel):
    skill_id: str | None = None
    prompt_id: str | None = None
    resource_uri: str | None = None
    workflow_template_id: str | None = None
    actor: str = "dependency-reviewer"

    @model_validator(mode="after")
    def one_changed_item(self) -> BlastRadiusRequest:
        changed = [
            self.skill_id,
            self.prompt_id,
            self.resource_uri,
            self.workflow_template_id,
        ]
        if sum(1 for item in changed if item) != 1:
            raise ValueError(
                "Provide exactly one changed item: skill_id, prompt_id, resource_uri, or workflow_template_id."
            )
        return self


class BlastRadiusResult(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    changed_item: JsonDict
    impacted_skills: list[str] = Field(default_factory=list)
    impacted_workflows: list[str] = Field(default_factory=list)
    impacted_prompts: list[str] = Field(default_factory=list)
    impacted_resources: list[str] = Field(default_factory=list)
    likely_agents: list[JsonDict] = Field(default_factory=list)
    likely_tool_calls: list[JsonDict] = Field(default_factory=list)
    capacity_impact: JsonDict = Field(default_factory=dict)
    conformance_tests_to_run: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    recommended_rollout_action: str
    graph_paths: list[JsonDict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DependencyReportRequest(BaseModel):
    actor: str = "dependency-reviewer"
    scenarios: list[BlastRadiusRequest] = Field(default_factory=list)


class DependencyReportResult(BaseModel):
    report_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class SkillIncidentDrillRequest(BaseModel):
    scenario: SkillIncidentScenario = "schema_breakage"
    actor: str = "platform-owner"


class SkillIncidentDrillResult(BaseModel):
    drill_id: str
    generated_at: datetime
    scenario: SkillIncidentScenario
    affected_skills: list[str] = Field(default_factory=list)
    affected_workflows: list[str] = Field(default_factory=list)
    affected_prompts: list[str] = Field(default_factory=list)
    affected_resources: list[str] = Field(default_factory=list)
    simulated_symptoms: list[str] = Field(default_factory=list)
    severity: SkillIncidentSeverity
    containment_actions: list[str] = Field(default_factory=list)
    rollback_canary_plan: list[str] = Field(default_factory=list)
    conformance_eval_commands: list[str] = Field(default_factory=list)
    audit_evidence: JsonDict = Field(default_factory=dict)
    capacity_links: JsonDict = Field(default_factory=dict)
    dependency_links: JsonDict = Field(default_factory=dict)
    mcp_capabilities_affected: JsonDict = Field(default_factory=dict)
    readiness_status: SecurityReadinessStatus
    excluded_skills: JsonDict = Field(default_factory=dict)


class SkillIncidentRunbookRequest(BaseModel):
    scenario: SkillIncidentScenario = "schema_breakage"
    actor: str = "platform-owner"


class SkillIncidentRunbookResult(BaseModel):
    runbook_id: str
    generated_at: datetime
    scenario: SkillIncidentScenario
    readiness_status: SecurityReadinessStatus
    severity: SkillIncidentSeverity
    json_path: str
    markdown_path: str
    summary: JsonDict


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
    tenant_scenario_id: str = "internal_ops_local"
    require_marketplace_approval: bool = True


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
    tenant_id: str = "internal_demo"
    user_id: str = "demo-user"
    user_scopes: list[str] = Field(default_factory=lambda: ["skill.invoke"])
    enforce_entitlements: bool = False
    enforce_sandbox: bool = False
    action_class: InvocationSandboxActionClass = "skill_invocation"
    endpoint: str | None = None


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


class PolicyReplayRecord(BaseModel):
    record_id: str
    source_type: Literal["historical_invocation", "baseline_scenario"]
    skill_id: str
    version: str
    policy_context: PolicyInvocationContext
    original_decision: str
    replay_decision: PolicyDecisionValue
    same_decision: bool
    status: Literal["stable", "drift", "needs_evidence"]
    original_rules: list[str] = Field(default_factory=list)
    replay_rules: list[str] = Field(default_factory=list)
    reviewer_action: str
    replay_command: str
    invocation_id: str | None = None
    trace_id: str | None = None


class PolicyReplayDriftReport(BaseModel):
    report_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    records: list[PolicyReplayRecord]
    drift_records: list[PolicyReplayRecord] = Field(default_factory=list)
    approval_queue: list[JsonDict] = Field(default_factory=list)
    state_observations: list[JsonDict] = Field(default_factory=list)
    bounded_review_steps: list[JsonDict] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PolicyReplayPackRequest(BaseModel):
    actor: str = "policy-replay-reviewer"


class PolicyReplayPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class InvocationSandboxLimits(BaseModel):
    max_payload_bytes: int = 4096
    max_string_chars: int = 3000
    max_array_items: int = 50
    max_object_depth: int = 6
    max_estimated_input_tokens: int = 900


class InvocationSandboxDecision(BaseModel):
    skill_id: str
    actor: str
    provider: str
    endpoint: str
    action_class: InvocationSandboxActionClass
    decision: InvocationSandboxDecisionValue
    risk_label: InvocationSandboxRiskLabel
    reasons: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    limits: InvocationSandboxLimits
    observed: JsonDict = Field(default_factory=dict)
    trace_id: str
    generated_at: datetime


class InvocationSandboxEvaluateRequest(BaseModel):
    skill_id: str = "search_knowledge_base"
    input: JsonDict = Field(default_factory=dict)
    actor: str = "sandbox-reviewer"
    policy_context: PolicyInvocationContext | None = None
    action_class: InvocationSandboxActionClass = "skill_invocation"
    endpoint: str = "fastapi:/skills/{skill_id}/invoke"
    enforce: bool = False


class InvocationSandboxReport(BaseModel):
    report_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    limits: InvocationSandboxLimits
    blocked_action_classes: list[InvocationSandboxActionClass]
    endpoint_policy: list[JsonDict] = Field(default_factory=list)
    skill_risk_labels: list[JsonDict] = Field(default_factory=list)
    decisions: list[InvocationSandboxDecision] = Field(default_factory=list)
    audit_evidence: list[JsonDict] = Field(default_factory=list)
    reviewer_checklist: list[JsonDict] = Field(default_factory=list)
    local_verification_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class InvocationSandboxPackRequest(BaseModel):
    actor: str = "sandbox-policy-reviewer"
    scenarios: list[InvocationSandboxEvaluateRequest] = Field(default_factory=list)


class InvocationSandboxPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class SandboxExceptionSubmitRequest(BaseModel):
    skill_id: str = "search_knowledge_base"
    input: JsonDict = Field(default_factory=dict)
    requested_by: str = "sandbox-exception-requester"
    business_justification: str = "Need reviewer approval for a blocked local sandbox action."
    action_class: InvocationSandboxActionClass = "filesystem_write"
    endpoint: str = "fastapi:/skills/{skill_id}/invoke"
    policy_context: PolicyInvocationContext | None = None


class SandboxExceptionDecisionRequest(BaseModel):
    reviewer: str = "sandbox-reviewer"
    decision: SandboxExceptionDecision = "deny"
    notes: str = "Deny by default until the policy owner narrows the request."


class SandboxExceptionRecord(BaseModel):
    exception_id: str
    status: SandboxExceptionStatus
    requested_by: str
    reviewer: str | None = None
    skill_id: str
    action_class: InvocationSandboxActionClass
    endpoint: str
    business_justification: str
    sandbox_decision: InvocationSandboxDecision
    reviewer_notes: str | None = None
    approval_conditions: list[str] = Field(default_factory=list)
    governance_patterns: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    trace_id: str


class SandboxExceptionQueueResult(BaseModel):
    queue_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    records: list[SandboxExceptionRecord] = Field(default_factory=list)
    governance_policy: list[JsonDict] = Field(default_factory=list)
    audit_evidence: list[JsonDict] = Field(default_factory=list)
    local_verification_commands: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SandboxExceptionPackRequest(BaseModel):
    actor: str = "sandbox-exception-reviewer"
    include_closed: bool = True


class SandboxExceptionPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class WorkflowTemplate(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str
    description: str
    ordered_skill_ids: list[str]
    required_role: PolicyRole
    default_sensitivity: DataSensitivity = "internal"
    expected_outputs: list[str]


class WorkflowTemplateValidation(BaseModel):
    template_id: str
    validation_status: WorkflowValidationStatus
    valid: bool
    required_role: PolicyRole
    sensitivity: DataSensitivity
    missing_skills: list[str] = Field(default_factory=list)
    invalid_skills: list[str] = Field(default_factory=list)
    policy_warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class WorkflowTemplateReview(BaseModel):
    template_id: str
    template: WorkflowTemplate
    status: WorkflowReviewStatus
    submitted_by: str
    submitted_at: datetime
    updated_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    validation: WorkflowTemplateValidation


class WorkflowReviewDecisionRequest(BaseModel):
    actor: str = "workflow-reviewer"
    note: str | None = None


class WorkflowReviewEvidenceResult(BaseModel):
    template_id: str
    generated_at: datetime
    status: WorkflowReviewStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class WorkflowSimulationRequest(BaseModel):
    input_text: str = Field(min_length=1)
    role: PolicyRole = "agent"
    data_sensitivity: DataSensitivity | None = None
    environment: str = "local"


class WorkflowStepResult(BaseModel):
    step_index: int
    skill_id: str
    status: Literal["succeeded", "denied", "blocked"]
    policy_decision: PolicySimulationResult
    output: JsonDict | None = None
    trace_id: str
    reason: str


class WorkflowSimulationResult(BaseModel):
    id: str
    template_id: str
    template_name: str
    selected_skills: list[str]
    step_outputs: list[WorkflowStepResult]
    trace: list[JsonDict]
    final_output: str
    blocked_steps: list[WorkflowStepResult]
    data_sensitivity: DataSensitivity
    environment: str
    role: PolicyRole


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


class ConformanceSkillRecord(BaseModel):
    skill_id: str
    version: str
    schema_valid: bool
    sample_invocation_passed: bool
    output_schema_valid: bool
    policy_checked: bool
    mcp_exposed: bool
    prompt_refs: list[str] = Field(default_factory=list)
    resource_refs: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


class ConformanceReport(BaseModel):
    generated_at: datetime
    status: Literal["pass", "fail"]
    promoted_skill_count: int
    passed_skill_count: int
    failed_skill_count: int
    skills: list[ConformanceSkillRecord]


class EvidenceExportResult(BaseModel):
    bundle_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    summary: JsonDict


class SecurityReviewSummary(BaseModel):
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    policy_denial_count: int
    promoted_skill_count: int
    conformance_pass_count: int
    high_risk_flags: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class ReleaseDiffItem(BaseModel):
    id: str
    name: str
    change_type: ReleaseChangeType
    current_version: str | None = None
    previous_version: str | None = None
    details: list[str] = Field(default_factory=list)
    current: JsonDict | None = None
    previous: JsonDict | None = None


class ReleaseMcpCapabilities(BaseModel):
    tools: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    prompts: list[str] = Field(default_factory=list)
    affected_tools: list[str] = Field(default_factory=list)
    affected_resources: list[str] = Field(default_factory=list)
    affected_prompts: list[str] = Field(default_factory=list)


class ReleasePreview(BaseModel):
    release_id: str
    generated_at: datetime
    snapshot_source: str
    readiness_status: SecurityReadinessStatus
    summary: JsonDict
    skills_added: list[ReleaseDiffItem] = Field(default_factory=list)
    skills_changed: list[ReleaseDiffItem] = Field(default_factory=list)
    skills_removed: list[ReleaseDiffItem] = Field(default_factory=list)
    workflow_templates_added: list[ReleaseDiffItem] = Field(default_factory=list)
    workflow_templates_changed: list[ReleaseDiffItem] = Field(default_factory=list)
    workflow_templates_removed: list[ReleaseDiffItem] = Field(default_factory=list)
    policy_conformance_status: JsonDict
    risk_flags: list[str] = Field(default_factory=list)
    recommended_regression_tests: list[str] = Field(default_factory=list)
    mcp_capabilities: ReleaseMcpCapabilities
    governance_events: list[JsonDict] = Field(default_factory=list)
    excluded_skills: JsonDict = Field(default_factory=dict)


class ReleaseExportResult(BaseModel):
    release_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    json_path: str
    markdown_path: str
    snapshot_path: str
    summary: JsonDict


class ReleaseQualityGate(BaseModel):
    gate_id: str
    generated_at: datetime
    status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    verification_checklist: list[JsonDict] = Field(default_factory=list)
    coverage: JsonDict
    artifact_coverage: list[JsonDict] = Field(default_factory=list)
    local_runtime_notes: list[str] = Field(default_factory=list)
    publish_readiness: JsonDict
    endpoint_inventory: list[JsonDict] = Field(default_factory=list)
    mcp_capability_inventory: JsonDict
    summary: JsonDict = Field(default_factory=dict)


class ReleasePublishPackRequest(BaseModel):
    actor: str = "release-publisher"


class ReleasePublishPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class CiDoctorCheck(BaseModel):
    id: str
    category: str
    status: CiDoctorCheckStatus
    title: str
    detail: str
    evidence: list[str] = Field(default_factory=list)
    command: str | None = None
    remediation: str | None = None


class CiDoctorResult(BaseModel):
    doctor_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    checks: list[CiDoctorCheck]
    command_checks: list[CiDoctorCheck] = Field(default_factory=list)
    dependency_inventory: JsonDict = Field(default_factory=dict)
    secret_scan_summary: JsonDict = Field(default_factory=dict)
    local_runtime_notes: list[str] = Field(default_factory=list)
    publish_safety_checklist: list[JsonDict] = Field(default_factory=list)


class AuditPackRequest(BaseModel):
    actor: str = "ci-doctor"


class AuditPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class SupplyChainPackageRecord(BaseModel):
    package_id: str
    name: str
    ecosystem: str
    source: str
    scope: str
    specifier: str
    version_constraint: str
    version_pinned: bool
    license: str
    license_status: Literal["allowed", "review_required", "blocked", "unknown"]
    risk_flags: list[str] = Field(default_factory=list)
    approval_required: bool = False
    reviewer_notes: list[str] = Field(default_factory=list)


class SupplyChainReport(BaseModel):
    report_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    manifests: list[JsonDict]
    packages: list[SupplyChainPackageRecord]
    policy_checks: list[JsonDict]
    license_policy: JsonDict
    approval_gates: list[JsonDict]
    local_verification_commands: list[str]
    limitations: list[str]


class SupplyChainPackRequest(BaseModel):
    actor: str = "supply-chain-reviewer"


class SupplyChainPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict


class InvocationReplayResult(BaseModel):
    invocation_id: str
    skill_id: str
    version: str
    original_input: JsonDict
    original_output: JsonDict | None
    replay_output: JsonDict | None
    same_output: bool
    drift_notes: list[str] = Field(default_factory=list)
    original_status: InvocationStatus
    replay_status: InvocationStatus
    original_error: str | None = None
    replay_error: str | None = None


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


class EvalRegressionCaseRecord(BaseModel):
    case_id: str
    skill_id: str
    status: Literal["pass", "fail"]
    score: float
    latency_ms: float
    trace_id: str | None = None
    severity: Literal["none", "low", "medium", "high", "critical"]
    recommended_action: str
    failed_expectations: list[str] = Field(default_factory=list)


class EvalRegressionGateResult(BaseModel):
    gate_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    summary: JsonDict
    golden_eval: GoldenEvalSuiteResult
    conformance_status: str
    release_readiness: SecurityReadinessStatus
    reliability_readiness: SecurityReadinessStatus
    slo_release_gate: str
    regression_cases: list[EvalRegressionCaseRecord]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    state_observations: list[JsonDict] = Field(default_factory=list)
    bounded_remediation_steps: list[JsonDict] = Field(default_factory=list)
    local_proof_commands: list[str] = Field(default_factory=list)
    architecture_patterns: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EvalRegressionPackRequest(BaseModel):
    actor: str = "eval-regression-reviewer"


class EvalRegressionPackResult(BaseModel):
    pack_id: str
    generated_at: datetime
    readiness_status: SecurityReadinessStatus
    score: int = Field(ge=0, le=100)
    json_path: str
    markdown_path: str
    summary: JsonDict
