from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, Request

from app import __version__
from app.bootstrap import create_state
from app.config import get_settings
from app.evals.golden import GoldenEvalRunner
from app.models import (
    AgentRun,
    AgentRunRequest,
    ApiContractAuditResult,
    ApiReviewerCollectionRequest,
    ApiReviewerCollectionResult,
    ArtifactInventoryResult,
    ArtifactReadmeChecklistRequest,
    ArtifactReadmeChecklistResult,
    AuditEvent,
    AuditPackRequest,
    AuditPackResult,
    AuditQueryRequest,
    AuditQueryResult,
    BlastRadiusRequest,
    BlastRadiusResult,
    CapacityForecastRequest,
    CapacityForecastResult,
    CapacityGuardrailsRequest,
    CapacityGuardrailsResult,
    CapacityPlanExportRequest,
    CapacityPlanExportResult,
    CiDoctorResult,
    CircuitBreakerActionRequest,
    ComplianceAttestationRequest,
    ComplianceAttestationResult,
    ConformanceReport,
    DashboardSmokeResult,
    DependencyMapResult,
    DependencyReportRequest,
    DependencyReportResult,
    EnterprisePortfolioDemoPackRequest,
    EnterprisePortfolioDemoPackResult,
    EnterpriseReadinessScorecard,
    EvidenceExportResult,
    FinalAuditResult,
    FinalHandoffPackRequest,
    FinalHandoffPackResult,
    GitPushPlanRequest,
    GitPushPlanResult,
    GitReadinessResult,
    GoldenEvalSuiteResult,
    GovernanceReport,
    HealthResponse,
    InvocationReplayResult,
    InvokeSkillRequest,
    LaunchChecklistRequest,
    LaunchChecklistResult,
    LocalSnapshot,
    MarketplaceCatalogResult,
    MarketplaceRolloutPackRequest,
    MarketplaceRolloutPackResult,
    McpToolDefinition,
    PolicyInvocationContext,
    PolicySimulationRequest,
    PolicySimulationResult,
    PortfolioEvidenceIndexResult,
    PortfolioInterviewPackRequest,
    PortfolioInterviewPackResult,
    PrivacyRedactionRequest,
    PrivacyRedactionResult,
    PrivacyRetentionPackRequest,
    PrivacyRetentionPackResult,
    PrivacyRetentionReport,
    PromoteSkillRequest,
    PromptDefinition,
    PromptGovernancePackRequest,
    PromptGovernancePackResult,
    PromptGovernanceReport,
    PromptGovernanceTargetResult,
    PromptGovernanceValidationRequest,
    RegisterSkillRequest,
    ReleaseExportResult,
    ReleasePreview,
    ReleasePublishPackRequest,
    ReleasePublishPackResult,
    ReleaseQualityGate,
    ResourceDefinition,
    ResourcePayload,
    ReviewerQuickstartResult,
    ReviewerWalkthroughPackRequest,
    ReviewerWalkthroughPackResult,
    RuntimeDemoPackRequest,
    RuntimeDemoPackResult,
    RuntimeDemoReadinessResult,
    SecurityReviewSummary,
    SkillIncidentDrillRequest,
    SkillIncidentDrillResult,
    SkillIncidentRunbookRequest,
    SkillIncidentRunbookResult,
    SkillInvocation,
    SkillManifest,
    SkillReliabilityPackRequest,
    SkillReliabilityPackResult,
    SkillReliabilityRecord,
    SkillReliabilityReport,
    SkillStatusRequest,
    SkillVersion,
    SmokeMatrixResult,
    TenantEntitlementMatrixRequest,
    TenantEntitlementMatrixResult,
    TenantEntitlementPackRequest,
    TenantEntitlementPackResult,
    TenantPolicySimulationRequest,
    TenantPolicySimulationResult,
    TenantSandboxExportRequest,
    TenantSandboxExportResult,
    TenantSkillEntitlementPolicy,
    UiVerificationPackRequest,
    UiVerificationPackResult,
    UsageAnalyticsResult,
    UsageChargebackPackRequest,
    UsageChargebackPackResult,
    UsageSummary,
    ValidateSkillRequest,
    ValidationResult,
    WorkflowReviewDecisionRequest,
    WorkflowReviewEvidenceResult,
    WorkflowSimulationRequest,
    WorkflowSimulationResult,
    WorkflowTemplate,
    WorkflowTemplateReview,
)
from app.security import require_api_key
from app.utils import configure_logging, new_trace_id

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
app = FastAPI(
    title="Enterprise MCP Skill Hub",
    description="Governed reusable AI skills exposed through FastAPI and MCP-compatible adapters.",
    version=__version__,
)
state = create_state()


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", new_trace_id())
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    logger.info(
        "request completed method=%s path=%s status=%s",
        request.method,
        request.url.path,
        response.status_code,
        extra={"trace_id": trace_id},
    )
    return response


@app.post("/auth/demo-token")
def demo_token() -> dict[str, str]:
    return {"token": get_settings().api_key, "header": "X-API-Key"}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        provider_mode=state.provider.name,
        mcp_mode="compatible-tools-resources-prompts",
        version=__version__,
    )


@app.get("/skills", response_model=list[SkillManifest])
def list_skills(_: str = Depends(require_api_key)) -> list[SkillManifest]:
    return state.registry.list()


@app.post("/skills/validate", response_model=ValidationResult)
def validate_skill(request: ValidateSkillRequest, _: str = Depends(require_api_key)) -> ValidationResult:
    result = state.validator.validate_manifest(request.manifest)
    state.audit.record("skill.validated", "skill", result.manifest_id or "unknown", "api-validation")
    return result


@app.post("/policy/simulate", response_model=PolicySimulationResult)
def simulate_policy(
    request: PolicySimulationRequest,
    _: str = Depends(require_api_key),
) -> PolicySimulationResult:
    try:
        manifest = state.registry.get(request.skill_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return state.policy.simulate(manifest, request)


@app.post("/tenants/policy-simulate", response_model=TenantPolicySimulationResult)
def tenant_policy_simulate(
    request: TenantPolicySimulationRequest,
    _: str = Depends(require_api_key),
) -> TenantPolicySimulationResult:
    return state.tenant_sandbox.simulate(request)


@app.post("/tenants/sandbox-export", response_model=TenantSandboxExportResult)
def tenant_sandbox_export(
    request: TenantSandboxExportRequest | None = None,
    _: str = Depends(require_api_key),
) -> TenantSandboxExportResult:
    return state.tenant_sandbox.export(request or TenantSandboxExportRequest())


@app.get("/tenants/entitlements/policies", response_model=list[TenantSkillEntitlementPolicy])
def tenant_entitlement_policies(_: str = Depends(require_api_key)) -> list[TenantSkillEntitlementPolicy]:
    return state.entitlements.list_policies()


@app.post("/tenants/entitlements/evaluate", response_model=TenantEntitlementMatrixResult)
def tenant_entitlement_evaluate(
    request: TenantEntitlementMatrixRequest | None = None,
    _: str = Depends(require_api_key),
) -> TenantEntitlementMatrixResult:
    return state.entitlements.matrix(request or TenantEntitlementMatrixRequest())


@app.post("/tenants/entitlements/pack", response_model=TenantEntitlementPackResult)
async def tenant_entitlement_pack(
    request: TenantEntitlementPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> TenantEntitlementPackResult:
    return await state.entitlements.export_pack(request or TenantEntitlementPackRequest())


@app.get("/marketplace/catalog", response_model=MarketplaceCatalogResult)
async def marketplace_catalog(_: str = Depends(require_api_key)) -> MarketplaceCatalogResult:
    return await state.marketplace.catalog()


@app.post("/marketplace/rollout-pack", response_model=MarketplaceRolloutPackResult)
async def marketplace_rollout_pack(
    request: MarketplaceRolloutPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> MarketplaceRolloutPackResult:
    return await state.marketplace.rollout_pack(request or MarketplaceRolloutPackRequest())


@app.get("/usage/analytics", response_model=UsageAnalyticsResult)
def usage_analytics(_: str = Depends(require_api_key)) -> UsageAnalyticsResult:
    return state.usage.analytics()


@app.post("/usage/chargeback-pack", response_model=UsageChargebackPackResult)
def usage_chargeback_pack(
    request: UsageChargebackPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> UsageChargebackPackResult:
    return state.usage.chargeback_pack(request or UsageChargebackPackRequest())


@app.get("/reliability/skills", response_model=SkillReliabilityReport)
def skill_reliability(_: str = Depends(require_api_key)) -> SkillReliabilityReport:
    return state.reliability.report()


@app.patch("/reliability/circuit-breakers/{skill_id}", response_model=SkillReliabilityRecord)
def set_circuit_breaker(
    skill_id: str,
    request: CircuitBreakerActionRequest,
    _: str = Depends(require_api_key),
) -> SkillReliabilityRecord:
    try:
        return state.reliability.set_breaker(skill_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/reliability/pack", response_model=SkillReliabilityPackResult)
def skill_reliability_pack(
    request: SkillReliabilityPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> SkillReliabilityPackResult:
    return state.reliability.pack(request or SkillReliabilityPackRequest())


@app.get("/prompt-governance/report", response_model=PromptGovernanceReport)
def prompt_governance_report(_: str = Depends(require_api_key)) -> PromptGovernanceReport:
    return state.prompt_governance.report(actor="api-prompt-governance")


@app.post("/prompt-governance/validate", response_model=PromptGovernanceTargetResult)
def prompt_governance_validate(
    request: PromptGovernanceValidationRequest,
    _: str = Depends(require_api_key),
) -> PromptGovernanceTargetResult:
    return state.prompt_governance.validate(request)


@app.post("/prompt-governance/pack", response_model=PromptGovernancePackResult)
def prompt_governance_pack(
    request: PromptGovernancePackRequest | None = None,
    _: str = Depends(require_api_key),
) -> PromptGovernancePackResult:
    return state.prompt_governance.pack(request or PromptGovernancePackRequest())


@app.get("/privacy/retention-report", response_model=PrivacyRetentionReport)
def privacy_retention_report(_: str = Depends(require_api_key)) -> PrivacyRetentionReport:
    return state.privacy_retention.report()


@app.post("/privacy/redact", response_model=PrivacyRedactionResult)
def privacy_redact(
    request: PrivacyRedactionRequest,
    _: str = Depends(require_api_key),
) -> PrivacyRedactionResult:
    return state.privacy_retention.redact(request)


@app.post("/privacy/retention-pack", response_model=PrivacyRetentionPackResult)
def privacy_retention_pack(
    request: PrivacyRetentionPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> PrivacyRetentionPackResult:
    return state.privacy_retention.pack(request or PrivacyRetentionPackRequest())


@app.get("/enterprise/readiness-scorecard", response_model=EnterpriseReadinessScorecard)
async def enterprise_readiness_scorecard(_: str = Depends(require_api_key)) -> EnterpriseReadinessScorecard:
    return await state.enterprise.scorecard()


@app.post("/enterprise/portfolio-demo-pack", response_model=EnterprisePortfolioDemoPackResult)
async def enterprise_portfolio_demo_pack(
    request: EnterprisePortfolioDemoPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> EnterprisePortfolioDemoPackResult:
    return await state.enterprise.portfolio_demo_pack(request or EnterprisePortfolioDemoPackRequest())


@app.get("/portfolio/evidence-index", response_model=PortfolioEvidenceIndexResult)
async def portfolio_evidence_index(_: str = Depends(require_api_key)) -> PortfolioEvidenceIndexResult:
    return await state.portfolio.evidence_index()


@app.post("/portfolio/interview-pack", response_model=PortfolioInterviewPackResult)
async def portfolio_interview_pack(
    request: PortfolioInterviewPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> PortfolioInterviewPackResult:
    return await state.portfolio.interview_pack(request or PortfolioInterviewPackRequest())


@app.get("/reviewer/quickstart", response_model=ReviewerQuickstartResult)
async def reviewer_quickstart(_: str = Depends(require_api_key)) -> ReviewerQuickstartResult:
    return await state.reviewer.quickstart()


@app.post("/reviewer/walkthrough-pack", response_model=ReviewerWalkthroughPackResult)
async def reviewer_walkthrough_pack(
    request: ReviewerWalkthroughPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> ReviewerWalkthroughPackResult:
    return await state.reviewer.walkthrough_pack(request or ReviewerWalkthroughPackRequest())


@app.get("/api/contract-audit", response_model=ApiContractAuditResult)
def api_contract_audit(_: str = Depends(require_api_key)) -> ApiContractAuditResult:
    return state.api_contracts.contract_audit()


@app.post("/api/reviewer-collection", response_model=ApiReviewerCollectionResult)
def api_reviewer_collection(
    request: ApiReviewerCollectionRequest | None = None,
    _: str = Depends(require_api_key),
) -> ApiReviewerCollectionResult:
    return state.api_contracts.reviewer_collection(request or ApiReviewerCollectionRequest())


@app.get("/artifacts/inventory", response_model=ArtifactInventoryResult)
def artifacts_inventory(_: str = Depends(require_api_key)) -> ArtifactInventoryResult:
    return state.artifacts.inventory()


@app.post("/artifacts/readme-checklist", response_model=ArtifactReadmeChecklistResult)
def artifacts_readme_checklist(
    request: ArtifactReadmeChecklistRequest | None = None,
    _: str = Depends(require_api_key),
) -> ArtifactReadmeChecklistResult:
    return state.artifacts.readme_checklist(request or ArtifactReadmeChecklistRequest())


@app.get("/handoff/final-audit", response_model=FinalAuditResult)
def handoff_final_audit(_: str = Depends(require_api_key)) -> FinalAuditResult:
    return state.final_handoff.final_audit()


@app.post("/handoff/final-pack", response_model=FinalHandoffPackResult)
async def handoff_final_pack(
    request: FinalHandoffPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> FinalHandoffPackResult:
    return await state.final_handoff.final_pack(request or FinalHandoffPackRequest())


@app.get("/ops/smoke-matrix", response_model=SmokeMatrixResult)
async def ops_smoke_matrix(_: str = Depends(require_api_key)) -> SmokeMatrixResult:
    return await state.smoke.smoke_matrix()


@app.post("/ops/launch-checklist", response_model=LaunchChecklistResult)
async def ops_launch_checklist(
    request: LaunchChecklistRequest | None = None,
    _: str = Depends(require_api_key),
) -> LaunchChecklistResult:
    return await state.smoke.launch_checklist(request or LaunchChecklistRequest())


@app.get("/ops/ci-doctor", response_model=CiDoctorResult)
async def ops_ci_doctor(_: str = Depends(require_api_key)) -> CiDoctorResult:
    return await state.ci_doctor.ci_doctor()


@app.post("/ops/audit-pack", response_model=AuditPackResult)
async def ops_audit_pack(
    request: AuditPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> AuditPackResult:
    return await state.ci_doctor.audit_pack(request or AuditPackRequest())


@app.get("/ui/dashboard-smoke", response_model=DashboardSmokeResult)
def ui_dashboard_smoke(_: str = Depends(require_api_key)) -> DashboardSmokeResult:
    return state.ui_verification.dashboard_smoke()


@app.post("/ui/verification-pack", response_model=UiVerificationPackResult)
def ui_verification_pack(
    request: UiVerificationPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> UiVerificationPackResult:
    return state.ui_verification.verification_pack(request or UiVerificationPackRequest())


@app.get("/git/readiness", response_model=GitReadinessResult)
def git_readiness(_: str = Depends(require_api_key)) -> GitReadinessResult:
    return state.git_readiness.readiness()


@app.post("/git/push-plan", response_model=GitPushPlanResult)
def git_push_plan(
    request: GitPushPlanRequest | None = None,
    _: str = Depends(require_api_key),
) -> GitPushPlanResult:
    return state.git_readiness.push_plan(request or GitPushPlanRequest())


@app.get("/runtime/demo-readiness", response_model=RuntimeDemoReadinessResult)
def runtime_demo_readiness(_: str = Depends(require_api_key)) -> RuntimeDemoReadinessResult:
    return state.runtime_demo.readiness()


@app.post("/runtime/demo-pack", response_model=RuntimeDemoPackResult)
def runtime_demo_pack(
    request: RuntimeDemoPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> RuntimeDemoPackResult:
    return state.runtime_demo.demo_pack(request or RuntimeDemoPackRequest())


@app.post("/skills/register", response_model=SkillManifest)
def register_skill(request: RegisterSkillRequest, _: str = Depends(require_api_key)) -> SkillManifest:
    result = state.validator.validate_manifest(request.manifest.model_dump(mode="json"))
    if not result.valid:
        raise HTTPException(status_code=422, detail=result.errors)
    manifest = request.manifest
    if "status" not in manifest.model_fields_set and manifest.status == "draft":
        manifest = manifest.model_copy(update={"status": "validated"})
    return state.registry.register(manifest, actor="api-user")


@app.post("/skills/{skill_id}/promote", response_model=SkillManifest)
def promote_skill(
    skill_id: str,
    request: PromoteSkillRequest,
    _: str = Depends(require_api_key),
) -> SkillManifest:
    try:
        manifest = state.registry.get(skill_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = state.validator.validate_manifest(manifest.model_dump(mode="json"))
    state.audit.record("skill.validated", "skill", skill_id, new_trace_id(), request.actor)
    if not result.valid:
        raise HTTPException(status_code=422, detail=result.errors)
    return state.registry.promote(skill_id, request.actor)


@app.post("/skills/{skill_id}/invoke", response_model=SkillInvocation)
async def invoke_skill(
    skill_id: str,
    request: InvokeSkillRequest,
    http_request: Request,
    _: str = Depends(require_api_key),
) -> SkillInvocation:
    try:
        invocation = await state.invocation_service.invoke(
            skill_id,
            request.input,
            request.actor,
            _policy_context_from_request(http_request, request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if invocation.status == "failed":
        if invocation.error and invocation.error.startswith(("Policy denied", "Entitlement denied")):
            raise HTTPException(status_code=403, detail=invocation.error)
        raise HTTPException(status_code=422, detail=invocation.error)
    return invocation


@app.patch("/skills/{skill_id}/status", response_model=SkillManifest)
def set_skill_status(
    skill_id: str,
    request: SkillStatusRequest,
    _: str = Depends(require_api_key),
) -> SkillManifest:
    try:
        return state.registry.set_status(skill_id, request.enabled, request.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/skills/{skill_id}/versions", response_model=list[SkillVersion])
def skill_versions(skill_id: str, _: str = Depends(require_api_key)) -> list[SkillVersion]:
    try:
        return state.registry.versions(skill_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/agents/run", response_model=AgentRun)
async def run_agent(request: AgentRunRequest, _: str = Depends(require_api_key)) -> AgentRun:
    return await state.agent.run(request.prompt, request.actor)


@app.get("/workflows/templates", response_model=list[WorkflowTemplate])
def workflow_templates(_: str = Depends(require_api_key)) -> list[WorkflowTemplate]:
    return state.workflows.list()


@app.post("/workflows/templates/submit", response_model=WorkflowTemplateReview)
def submit_workflow_template(
    request: WorkflowTemplate,
    actor: str = "api-user",
    _: str = Depends(require_api_key),
) -> WorkflowTemplateReview:
    try:
        return state.workflows.submit(request, actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/workflows/reviews", response_model=list[WorkflowTemplateReview])
def workflow_reviews(_: str = Depends(require_api_key)) -> list[WorkflowTemplateReview]:
    return state.workflows.reviews()


@app.post("/workflows/{template_id}/approve", response_model=WorkflowTemplateReview)
def approve_workflow_template(
    template_id: str,
    request: WorkflowReviewDecisionRequest,
    _: str = Depends(require_api_key),
) -> WorkflowTemplateReview:
    try:
        return state.workflows.approve(template_id, request.actor, request.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/workflows/{template_id}/reject", response_model=WorkflowTemplateReview)
def reject_workflow_template(
    template_id: str,
    request: WorkflowReviewDecisionRequest,
    _: str = Depends(require_api_key),
) -> WorkflowTemplateReview:
    try:
        return state.workflows.reject(template_id, request.actor, request.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/workflows/{template_id}/simulate", response_model=WorkflowSimulationResult)
async def simulate_workflow(
    template_id: str,
    request: WorkflowSimulationRequest,
    _: str = Depends(require_api_key),
) -> WorkflowSimulationResult:
    try:
        return await state.workflows.simulate(template_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/workflows/{template_id}/review-evidence", response_model=WorkflowReviewEvidenceResult)
async def export_workflow_review_evidence(
    template_id: str,
    actor: str = "workflow-reviewer",
    _: str = Depends(require_api_key),
) -> WorkflowReviewEvidenceResult:
    try:
        return await state.workflows.export_review_evidence(template_id, actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/audit/events", response_model=list[AuditEvent])
def audit_events(_: str = Depends(require_api_key)) -> list[AuditEvent]:
    return state.audit.events


@app.post("/audit/query", response_model=AuditQueryResult)
async def audit_query(
    request: AuditQueryRequest,
    _: str = Depends(require_api_key),
) -> AuditQueryResult:
    return await state.audit_query.query(request)


@app.post("/compliance/attestation", response_model=ComplianceAttestationResult)
async def compliance_attestation(
    request: ComplianceAttestationRequest | None = None,
    _: str = Depends(require_api_key),
) -> ComplianceAttestationResult:
    return await state.attestations.export(request or ComplianceAttestationRequest())


@app.post("/capacity/forecast", response_model=CapacityForecastResult)
async def capacity_forecast(
    request: CapacityForecastRequest | None = None,
    _: str = Depends(require_api_key),
) -> CapacityForecastResult:
    return await state.capacity.forecast(request or CapacityForecastRequest())


@app.post("/capacity/guardrails", response_model=CapacityGuardrailsResult)
def capacity_guardrails(
    request: CapacityGuardrailsRequest | None = None,
    _: str = Depends(require_api_key),
) -> CapacityGuardrailsResult:
    return state.capacity.guardrails(request or CapacityGuardrailsRequest())


@app.post("/capacity/plan-export", response_model=CapacityPlanExportResult)
async def capacity_plan_export(
    request: CapacityPlanExportRequest | None = None,
    _: str = Depends(require_api_key),
) -> CapacityPlanExportResult:
    return await state.capacity.plan_export(request or CapacityPlanExportRequest())


@app.get("/dependencies/map", response_model=DependencyMapResult)
async def dependency_map(_: str = Depends(require_api_key)) -> DependencyMapResult:
    return await state.dependencies.build_map()


@app.post("/dependencies/blast-radius", response_model=BlastRadiusResult)
async def dependency_blast_radius(
    request: BlastRadiusRequest,
    _: str = Depends(require_api_key),
) -> BlastRadiusResult:
    return await state.dependencies.blast_radius(request)


@app.post("/dependencies/report", response_model=DependencyReportResult)
async def dependency_report(
    request: DependencyReportRequest | None = None,
    _: str = Depends(require_api_key),
) -> DependencyReportResult:
    return await state.dependencies.report(request or DependencyReportRequest())


@app.post("/incidents/drill", response_model=SkillIncidentDrillResult)
async def incident_drill(
    request: SkillIncidentDrillRequest | None = None,
    _: str = Depends(require_api_key),
) -> SkillIncidentDrillResult:
    return await state.incidents.drill(request or SkillIncidentDrillRequest())


@app.post("/incidents/runbook", response_model=SkillIncidentRunbookResult)
async def incident_runbook(
    request: SkillIncidentRunbookRequest | None = None,
    _: str = Depends(require_api_key),
) -> SkillIncidentRunbookResult:
    return await state.incidents.runbook(request or SkillIncidentRunbookRequest())


@app.get("/metrics/usage", response_model=UsageSummary)
def usage(_: str = Depends(require_api_key)) -> UsageSummary:
    return state.metrics.summary()


@app.get("/invocations", response_model=list[SkillInvocation])
def invocations(_: str = Depends(require_api_key)) -> list[SkillInvocation]:
    return state.invocation_service.invocations


@app.get("/governance/report", response_model=GovernanceReport)
def governance_report(_: str = Depends(require_api_key)) -> GovernanceReport:
    return state.governance.generate()


@app.get("/conformance/report", response_model=ConformanceReport)
async def conformance_report(_: str = Depends(require_api_key)) -> ConformanceReport:
    return await state.conformance.generate()


@app.post("/evidence/export", response_model=EvidenceExportResult)
async def export_evidence(
    actor: str = "security-reviewer",
    _: str = Depends(require_api_key),
) -> EvidenceExportResult:
    return await state.evidence.export(actor)


@app.get("/security/review-summary", response_model=SecurityReviewSummary)
async def security_review_summary(_: str = Depends(require_api_key)) -> SecurityReviewSummary:
    return await state.evidence.security_review_summary()


@app.post("/releases/preview", response_model=ReleasePreview)
async def release_preview(
    actor: str = "release-manager",
    _: str = Depends(require_api_key),
) -> ReleasePreview:
    return await state.releases.preview(actor)


@app.post("/releases/export", response_model=ReleaseExportResult)
async def release_export(
    actor: str = "release-manager",
    _: str = Depends(require_api_key),
) -> ReleaseExportResult:
    return await state.releases.export(actor)


@app.get("/release/quality-gate", response_model=ReleaseQualityGate)
async def release_quality_gate(_: str = Depends(require_api_key)) -> ReleaseQualityGate:
    return await state.release_candidate.quality_gate()


@app.post("/release/publish-pack", response_model=ReleasePublishPackResult)
async def release_publish_pack(
    request: ReleasePublishPackRequest | None = None,
    _: str = Depends(require_api_key),
) -> ReleasePublishPackResult:
    return await state.release_candidate.publish_pack(request or ReleasePublishPackRequest())


@app.post("/invocations/{invocation_id}/replay", response_model=InvocationReplayResult)
async def replay_invocation(
    invocation_id: str,
    _: str = Depends(require_api_key),
) -> InvocationReplayResult:
    try:
        return await state.invocation_service.replay(invocation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/evals/golden", response_model=GoldenEvalSuiteResult)
async def run_golden_evals(_: str = Depends(require_api_key)) -> GoldenEvalSuiteResult:
    return await GoldenEvalRunner(state).run()


@app.post("/snapshots/local", response_model=LocalSnapshot)
def save_local_snapshot(_: str = Depends(require_api_key)) -> LocalSnapshot:
    return state.persistence.save(state)


@app.get("/snapshots/local")
def read_local_snapshot(_: str = Depends(require_api_key)) -> dict:
    return state.persistence.load()


@app.get("/mcp/tools", response_model=list[McpToolDefinition])
def mcp_tools(_: str = Depends(require_api_key)) -> list[McpToolDefinition]:
    return state.mcp.list_tools()


@app.post("/mcp/tools/{tool_name}/call")
async def mcp_call_tool(
    tool_name: str,
    request: InvokeSkillRequest,
    http_request: Request,
    _: str = Depends(require_api_key),
) -> dict:
    return await state.mcp.call_tool(
        tool_name,
        request.input,
        request.actor,
        _policy_context_from_request(http_request, request),
    )


@app.get("/mcp/resources", response_model=list[ResourceDefinition])
def mcp_resources(_: str = Depends(require_api_key)) -> list[ResourceDefinition]:
    return state.mcp.list_resources()


@app.get("/mcp/resources/read", response_model=ResourcePayload)
def mcp_read_resource(uri: str, _: str = Depends(require_api_key)) -> ResourcePayload:
    try:
        return state.mcp.read_resource(uri)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/mcp/prompts", response_model=list[PromptDefinition])
def mcp_prompts(_: str = Depends(require_api_key)) -> list[PromptDefinition]:
    return state.mcp.list_prompts()


def _policy_context_from_request(
    http_request: Request,
    request: InvokeSkillRequest,
) -> PolicyInvocationContext | None:
    header_map = {
        "role": "x-policy-role",
        "environment": "x-policy-environment",
        "data_sensitivity": "x-data-sensitivity",
        "requested_action": "x-requested-action",
        "enforce": "x-policy-enforce",
        "tenant_id": "x-tenant-id",
        "user_id": "x-user-id",
        "user_scopes": "x-user-scopes",
        "enforce_entitlements": "x-entitlement-enforce",
    }
    header_values = {
        field: http_request.headers.get(header)
        for field, header in header_map.items()
        if http_request.headers.get(header) is not None
    }
    if not header_values:
        return request.policy_context

    data = request.policy_context.model_dump() if request.policy_context else {}
    if "enforce" in header_values:
        header_values["enforce"] = header_values["enforce"].lower() in {"1", "true", "yes", "on"}
    if "enforce_entitlements" in header_values:
        header_values["enforce_entitlements"] = header_values["enforce_entitlements"].lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    if "user_scopes" in header_values:
        header_values["user_scopes"] = [
            scope.strip() for scope in header_values["user_scopes"].split(",") if scope.strip()
        ]
    data.update(header_values)
    return PolicyInvocationContext.model_validate(data)
