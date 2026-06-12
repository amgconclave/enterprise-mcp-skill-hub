from __future__ import annotations

import asyncio
import json

from app.bootstrap import create_state
from app.models import (
    AgentCollaborationPackRequest,
    AgentCollaborationRequest,
    AgentSocietyEvalRequest,
    ApiContractDriftPackRequest,
    ApiContractRemediationPackRequest,
    ApiReviewerCollectionRequest,
    ArtifactReadmeChecklistRequest,
    AuditIntegrityPackRequest,
    AuditPackRequest,
    BlastRadiusRequest,
    CapacityPlanExportRequest,
    ComplianceAttestationRequest,
    ConfigHygienePackRequest,
    DependencyReportRequest,
    EnterprisePortfolioDemoPackRequest,
    EvalRegressionPackRequest,
    FinalHandoffPackRequest,
    GitPushPlanRequest,
    GovernedSkillPlatformPackRequest,
    InvocationSandboxPackRequest,
    LaunchChecklistRequest,
    MarketplaceApprovalPackRequest,
    MarketplaceApprovalSubmitRequest,
    MarketplaceRolloutPackRequest,
    PolicyReplayPackRequest,
    PolicySimulationRequest,
    PortfolioInterviewPackRequest,
    PrivacyRetentionPackRequest,
    PromptGovernancePackRequest,
    PromptGovernanceRemediationRequest,
    ProviderFailoverDrillRequest,
    ProviderFailoverPackRequest,
    ProviderFallbackPackRequest,
    ReleasePublishPackRequest,
    RepositoryAutomationPackRequest,
    ReviewerWalkthroughPackRequest,
    ReviewSlaPackRequest,
    RuntimeDemoPackRequest,
    SandboxExceptionDecisionRequest,
    SandboxExceptionPackRequest,
    SandboxExceptionSubmitRequest,
    SkillCompatibilityPackRequest,
    SkillIncidentDrillRequest,
    SkillIncidentRunbookRequest,
    SkillReliabilityPackRequest,
    SkillSloPackRequest,
    SupplyChainPackRequest,
    TaskRunTransparencyPackRequest,
    TenantEntitlementAccessReviewPackRequest,
    TenantEntitlementPackRequest,
    TenantEntitlementReviewPackRequest,
    TenantSandboxExportRequest,
    UiVerificationPackRequest,
    UsageChargebackPackRequest,
    WorkerQueueAdmissionPackRequest,
    WorkerRunbookPackRequest,
    WorkerSkillRunRequest,
    WorkflowSimulationRequest,
    WorkflowTemplate,
)


async def main() -> None:
    state = create_state()
    prompt = (
        "Summarize this support meeting, classify the request, search approved policy context, "
        "and create action items. Priya Shah from Atlas Labs needs a security review by 2026-06-15."
    )
    result = await state.agent.run(prompt)
    allowed = state.policy.simulate(
        state.registry.get("search_knowledge_base"),
        PolicySimulationRequest(
            skill_id="search_knowledge_base",
            role="reviewer",
            environment="local",
            data_sensitivity="confidential",
            requested_action="invoke",
        ),
    )
    denied = state.policy.simulate(
        state.registry.get("search_knowledge_base"),
        PolicySimulationRequest(
            skill_id="search_knowledge_base",
            role="agent",
            environment="local",
            data_sensitivity="confidential",
            requested_action="invoke",
        ),
    )
    allowed_workflow = await state.workflows.simulate(
        "meeting_to_actions",
        WorkflowSimulationRequest(
            input_text=(
                "Priya Shah from Atlas Labs needs a governed meeting summary. "
                "Action: Devan to send the replay trace by 2026-06-15."
            ),
            role="agent",
            data_sensitivity="internal",
            environment="local",
        ),
        "demo-workflow-runner",
    )
    denied_workflow = await state.workflows.simulate(
        "rfp_answer_pack",
        WorkflowSimulationRequest(
            input_text="Confidential RFP question about governance evidence and audit history.",
            role="agent",
            data_sensitivity="confidential",
            environment="local",
        ),
        "demo-workflow-runner",
    )
    submitted_template = WorkflowTemplate(
        id="reviewed_support_pack",
        name="Reviewed Support Pack",
        description="Classify and summarize a support request after workflow review approval.",
        ordered_skill_ids=["classify_request", "summarize_document"],
        required_role="agent",
        default_sensitivity="internal",
        expected_outputs=["category", "summary"],
    )
    submitted_review = state.workflows.submit(submitted_template, "demo-workflow-reviewer")
    templates_before_approval = [template.id for template in state.workflows.list()]
    approved_review = state.workflows.approve(
        submitted_template.id,
        "demo-workflow-reviewer",
        "Approved after deterministic validation.",
    )
    approved_workflow = await state.workflows.simulate(
        submitted_template.id,
        WorkflowSimulationRequest(
            input_text="Support request: Atlas Labs needs a governed review summary.",
            role="agent",
            data_sensitivity="internal",
            environment="local",
        ),
        "demo-workflow-runner",
    )
    review_evidence = await state.workflows.export_review_evidence(
        submitted_template.id,
        "demo-workflow-reviewer",
    )
    conformance = await state.conformance.generate()
    eval_regression_gate = await state.eval_regression.gate()
    eval_regression_pack = await state.eval_regression.pack(
        EvalRegressionPackRequest(actor="demo-eval-regression-reviewer")
    )
    replay_source = next(
        invocation
        for invocation in state.invocation_service.invocations
        if invocation.status == "succeeded"
    )
    replay = await state.invocation_service.replay(replay_source.id)
    security_review = await state.evidence.security_review_summary()
    evidence_export = await state.evidence.export("demo-security-reviewer")
    release_preview = await state.releases.preview("demo-release-manager")
    release_export = await state.releases.export("demo-release-manager")
    attestation_export = await state.attestations.export(
        ComplianceAttestationRequest(actor="demo-compliance-reviewer")
    )
    capacity_export = await state.capacity.plan_export(
        CapacityPlanExportRequest(actor="demo-capacity-planner")
    )
    dependency_map = await state.dependencies.build_map()
    dependency_blast = await state.dependencies.blast_radius(
        BlastRadiusRequest(skill_id="search_knowledge_base", actor="demo-dependency-reviewer")
    )
    dependency_report = await state.dependencies.report(
        DependencyReportRequest(actor="demo-dependency-reviewer")
    )
    incident_drill = await state.incidents.drill(
        SkillIncidentDrillRequest(
            scenario="latency_capacity_breach",
            actor="demo-incident-commander",
        )
    )
    incident_runbook = await state.incidents.runbook(
        SkillIncidentRunbookRequest(
            scenario="latency_capacity_breach",
            actor="demo-incident-commander",
        )
    )
    tenant_sandbox = state.tenant_sandbox.export(
        TenantSandboxExportRequest(actor="demo-tenant-policy-reviewer")
    )
    entitlement_pack = await state.entitlements.export_pack(
        TenantEntitlementPackRequest(actor="demo-entitlement-reviewer")
    )
    entitlement_coverage = state.entitlements.coverage()
    entitlement_review_pack = await state.entitlements.export_review_pack(
        TenantEntitlementReviewPackRequest(actor="demo-entitlement-reviewer")
    )
    entitlement_access_review = state.entitlements.access_review()
    entitlement_access_review_pack = await state.entitlements.export_access_review_pack(
        TenantEntitlementAccessReviewPackRequest(actor="demo-entitlement-access-reviewer")
    )
    marketplace_catalog = await state.marketplace.catalog()
    marketplace_pack = await state.marketplace.rollout_pack(
        MarketplaceRolloutPackRequest(actor="demo-marketplace-reviewer")
    )
    await state.marketplace.submit_approval(
        MarketplaceApprovalSubmitRequest(
            skill_id="summarize_document",
            tenant_scenario_id="internal_ops_local",
            actor="demo-marketplace-reviewer",
            owner="demo-platform-owner",
            note="Demo marketplace approval workflow.",
        )
    )
    marketplace_promotion_gate = await state.marketplace.promotion_gate(
        "summarize_document",
        "internal_ops_local",
        "demo-marketplace-reviewer",
    )
    marketplace_approval_pack = await state.marketplace.approval_pack(
        MarketplaceApprovalPackRequest(actor="demo-marketplace-reviewer")
    )
    compatibility_report = state.compatibility.report()
    compatibility_pack = state.compatibility.pack(
        SkillCompatibilityPackRequest(actor="demo-compatibility-reviewer")
    )
    usage_analytics = state.usage.analytics()
    usage_chargeback_pack = state.usage.chargeback_pack(
        UsageChargebackPackRequest(actor="demo-finops-reviewer")
    )
    reliability_report = state.reliability.report()
    reliability_pack = state.reliability.pack(
        SkillReliabilityPackRequest(actor="demo-platform-sre")
    )
    slo_report = state.slo.report()
    slo_pack = state.slo.pack(SkillSloPackRequest(actor="demo-slo-reviewer"))
    provider_readiness = state.provider_readiness.readiness(actor="demo-provider-reviewer")
    provider_fallback_pack = state.provider_readiness.fallback_pack(
        ProviderFallbackPackRequest(actor="demo-provider-reviewer")
    )
    provider_failover_drill = state.provider_failover.drill(
        ProviderFailoverDrillRequest(actor="demo-provider-drill-reviewer")
    )
    provider_failover_pack = state.provider_failover.pack(
        ProviderFailoverPackRequest(actor="demo-provider-drill-reviewer")
    )
    config_hygiene_report = state.config_hygiene.report()
    config_hygiene_pack = state.config_hygiene.pack(
        ConfigHygienePackRequest(actor="demo-config-reviewer")
    )
    platform_pack_report = await state.platform_pack.report(actor="demo-platform-owner")
    platform_pack_export = await state.platform_pack.export(
        GovernedSkillPlatformPackRequest(actor="demo-platform-owner")
    )
    review_sla_report = await state.review_sla.report(
        ReviewSlaPackRequest(actor="demo-review-ops")
    )
    review_sla_pack = await state.review_sla.pack(
        ReviewSlaPackRequest(actor="demo-review-ops")
    )
    agent_collaboration_run = await state.agent_collaboration.run(
        AgentCollaborationRequest(
            prompt=(
                "Classify the RFP, search approved AI governance policy, summarize the governed answer, "
                "and create action items for Priya Shah."
            ),
            actor="demo-agent-platform",
        )
    )
    agent_collaboration_pack = await state.agent_collaboration.export(
        AgentCollaborationPackRequest(actor="demo-agent-platform")
    )
    agent_society_eval = await state.agent_society_eval.report(
        AgentSocietyEvalRequest(actor="demo-agent-society-evaluator")
    )
    agent_society_eval_pack = await state.agent_society_eval.pack(
        AgentSocietyEvalRequest(actor="demo-agent-society-evaluator")
    )
    worker_run = await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="search_knowledge_base",
            input={"query": "AI governance policy", "limit": 2},
            actor="demo-platform-sre",
            worker_pool="retrieval_heavy",
            enforce_sandbox=True,
        )
    )
    worker_scale_plan = await state.worker_scaleout.scale_plan()
    worker_queue_admission = state.worker_scaleout.queue_admission_report()
    worker_queue_pack = state.worker_scaleout.queue_admission_pack(
        WorkerQueueAdmissionPackRequest(actor="demo-platform-sre")
    )
    worker_runbook = await state.worker_scaleout.runbook_pack(
        WorkerRunbookPackRequest(actor="demo-platform-sre")
    )
    task_run_ledger = state.task_runs.ledger()
    task_run_transparency_pack = state.task_runs.transparency_pack(
        TaskRunTransparencyPackRequest(actor="demo-run-transparency-reviewer")
    )
    policy_replay_report = state.policy_replay.report(actor="demo-policy-replay-reviewer")
    policy_replay_pack = state.policy_replay.pack(
        PolicyReplayPackRequest(actor="demo-policy-replay-reviewer")
    )
    audit_integrity = state.audit_integrity.report()
    audit_integrity_pack = state.audit_integrity.pack(
        AuditIntegrityPackRequest(actor="demo-audit-integrity-reviewer")
    )
    invocation_sandbox_report = state.invocation_sandbox.report()
    invocation_sandbox_pack = state.invocation_sandbox.pack(
        InvocationSandboxPackRequest(actor="demo-sandbox-reviewer")
    )
    sandbox_exception = state.sandbox_exceptions.submit(
        SandboxExceptionSubmitRequest(
            skill_id="extract_entities",
            input={"text": "Attempt to write a local file from a mock tool."},
            requested_by="demo-platform-engineer",
            business_justification="Show HITL review for a sandbox-denied mock tool action.",
            action_class="filesystem_write",
        )
    )
    sandbox_exception_decision = state.sandbox_exceptions.decide(
        sandbox_exception.exception_id,
        SandboxExceptionDecisionRequest(
            reviewer="demo-security-reviewer",
            decision="deny",
            notes="Deny by default until the sandbox policy owner narrows the requested action.",
        ),
    )
    sandbox_exception_pack = state.sandbox_exceptions.pack(
        SandboxExceptionPackRequest(actor="demo-security-reviewer")
    )
    prompt_governance_report = state.prompt_governance.report(actor="demo-prompt-governance")
    prompt_governance_pack = state.prompt_governance.pack(
        PromptGovernancePackRequest(actor="demo-prompt-security")
    )
    prompt_governance_remediation = state.prompt_governance.remediation_plan(
        PromptGovernanceRemediationRequest(actor="demo-prompt-remediation")
    )
    privacy_retention_report = state.privacy_retention.report(actor="demo-privacy-reviewer")
    privacy_retention_pack = state.privacy_retention.pack(
        PrivacyRetentionPackRequest(actor="demo-privacy-reviewer")
    )
    enterprise_scorecard = await state.enterprise.scorecard()
    portfolio_demo_pack = await state.enterprise.portfolio_demo_pack(
        EnterprisePortfolioDemoPackRequest(actor="demo-portfolio-reviewer")
    )
    portfolio_evidence = await state.portfolio.evidence_index()
    interview_pack = await state.portfolio.interview_pack(
        PortfolioInterviewPackRequest(actor="demo-portfolio-interviewer")
    )
    smoke_matrix = await state.smoke.smoke_matrix()
    launch_checklist = await state.smoke.launch_checklist(
        LaunchChecklistRequest(actor="demo-launch-reviewer")
    )
    release_gate = await state.release_candidate.quality_gate()
    publish_pack = await state.release_candidate.publish_pack(
        ReleasePublishPackRequest(actor="demo-release-publisher")
    )
    ci_doctor = await state.ci_doctor.ci_doctor()
    audit_pack = await state.ci_doctor.audit_pack(
        AuditPackRequest(actor="demo-ci-doctor")
    )
    supply_chain_report = state.supply_chain.report(actor="demo-supply-chain-reviewer")
    supply_chain_pack = state.supply_chain.pack(
        SupplyChainPackRequest(actor="demo-supply-chain-reviewer")
    )
    reviewer_quickstart = await state.reviewer.quickstart()
    walkthrough_pack = await state.reviewer.walkthrough_pack(
        ReviewerWalkthroughPackRequest(actor="demo-github-reviewer")
    )
    artifact_inventory = state.artifacts.inventory()
    readme_checklist = state.artifacts.readme_checklist(
        ArtifactReadmeChecklistRequest(actor="demo-github-reviewer")
    )
    dashboard_smoke = state.ui_verification.dashboard_smoke()
    ui_verification_pack = state.ui_verification.verification_pack(
        UiVerificationPackRequest(actor="demo-github-reviewer")
    )
    final_audit = state.final_handoff.final_audit()
    final_pack = await state.final_handoff.final_pack(
        FinalHandoffPackRequest(actor="demo-final-handoff-reviewer")
    )
    git_readiness = state.git_readiness.readiness()
    git_push_plan = state.git_readiness.push_plan(
        GitPushPlanRequest(actor="demo-github-reviewer")
    )
    repository_automation_plan = state.git_readiness.automation_plan()
    repository_automation_pack = state.git_readiness.automation_pack(
        RepositoryAutomationPackRequest(actor="demo-repo-reviewer")
    )
    runtime_readiness = state.runtime_demo.readiness()
    runtime_pack = state.runtime_demo.demo_pack(
        RuntimeDemoPackRequest(actor="demo-runtime-reviewer")
    )
    api_contract_audit = state.api_contracts.contract_audit()
    api_reviewer_collection = state.api_contracts.reviewer_collection(
        ApiReviewerCollectionRequest(actor="demo-api-contract-reviewer")
    )
    api_contract_drift_pack = state.api_contracts.contract_drift_pack(
        ApiContractDriftPackRequest(actor="demo-contract-drift-reviewer")
    )
    api_contract_remediation = state.api_contracts.remediation_run()
    api_contract_remediation_pack = state.api_contracts.remediation_pack(
        ApiContractRemediationPackRequest(actor="demo-contract-remediation-reviewer")
    )
    print(
        json.dumps(
            {
                "agent_run": result.model_dump(mode="json"),
                "policy_simulations": {
                    "allowed_reviewer_confidential": allowed.model_dump(mode="json"),
                    "denied_agent_confidential": denied.model_dump(mode="json"),
                },
                "workflow_simulations": {
                    "allowed_meeting_to_actions": allowed_workflow.model_dump(mode="json"),
                    "denied_confidential_rfp": denied_workflow.model_dump(mode="json"),
                },
                "workflow_review_queue": {
                    "submitted_review": submitted_review.model_dump(mode="json"),
                    "excluded_before_approval": submitted_template.id not in templates_before_approval,
                    "approved_review": approved_review.model_dump(mode="json"),
                    "approved_workflow_simulation": approved_workflow.model_dump(mode="json"),
                    "review_evidence_artifacts": {
                        "json_path": review_evidence.json_path,
                        "markdown_path": review_evidence.markdown_path,
                    },
                },
                "conformance": conformance.model_dump(mode="json"),
                "eval regression readiness": eval_regression_gate.readiness_status,
                "eval_regression_readiness": eval_regression_gate.readiness_status,
                "eval regression score": eval_regression_gate.score,
                "eval_regression_score": eval_regression_gate.score,
                "eval regression pack path": eval_regression_pack.markdown_path,
                "eval_regression_pack_path": eval_regression_pack.markdown_path,
                "invocation_replay": replay.model_dump(mode="json"),
                "security_review": security_review.model_dump(mode="json"),
                "evidence_artifacts": {
                    "json_path": evidence_export.json_path,
                    "markdown_path": evidence_export.markdown_path,
                },
                "release readiness": release_preview.readiness_status,
                "release_readiness": release_preview.readiness_status,
                "release_notes_artifacts": {
                    "json_path": release_export.json_path,
                    "markdown_path": release_export.markdown_path,
                    "snapshot_path": release_export.snapshot_path,
                },
                "attestation readiness": attestation_export.readiness_status,
                "attestation_readiness": attestation_export.readiness_status,
                "attestation_artifacts": {
                    "json_path": attestation_export.json_path,
                    "markdown_path": attestation_export.markdown_path,
                },
                "capacity readiness": capacity_export.readiness_status,
                "capacity_readiness": capacity_export.readiness_status,
                "capacity_plan_artifacts": {
                    "json_path": capacity_export.json_path,
                    "markdown_path": capacity_export.markdown_path,
                },
                "dependency readiness": dependency_map.readiness_status,
                "dependency_readiness": dependency_map.readiness_status,
                "dependency_blast_radius": dependency_blast.model_dump(mode="json"),
                "dependency_report_artifacts": {
                    "json_path": dependency_report.json_path,
                    "markdown_path": dependency_report.markdown_path,
                },
                "incident drill severity": incident_drill.severity,
                "incident drill readiness": incident_drill.readiness_status,
                "incident_drill": {
                    "scenario": incident_drill.scenario,
                    "severity": incident_drill.severity,
                    "readiness_status": incident_drill.readiness_status,
                    "affected_skills": incident_drill.affected_skills,
                    "affected_workflows": incident_drill.affected_workflows,
                },
                "incident_runbook_artifacts": {
                    "json_path": incident_runbook.json_path,
                    "markdown_path": incident_runbook.markdown_path,
                },
                "tenant sandbox readiness": tenant_sandbox.readiness_status,
                "tenant_sandbox_readiness": tenant_sandbox.readiness_status,
                "tenant_sandbox_artifacts": {
                    "json_path": tenant_sandbox.json_path,
                    "markdown_path": tenant_sandbox.markdown_path,
                },
                "tenant entitlement readiness": entitlement_pack.readiness_status,
                "tenant_entitlement_readiness": entitlement_pack.readiness_status,
                "tenant entitlement pack path": entitlement_pack.markdown_path,
                "tenant_entitlement_pack_path": entitlement_pack.markdown_path,
                "tenant entitlement coverage": entitlement_coverage.readiness_status,
                "tenant_entitlement_coverage": entitlement_coverage.readiness_status,
                "tenant entitlement review rows": entitlement_coverage.summary[
                    "review_required_count"
                ],
                "tenant_entitlement_review_rows": entitlement_coverage.summary[
                    "review_required_count"
                ],
                "tenant entitlement review pack path": entitlement_review_pack.markdown_path,
                "tenant_entitlement_review_pack_path": entitlement_review_pack.markdown_path,
                "tenant entitlement access review": entitlement_access_review.readiness_status,
                "tenant_entitlement_access_review": entitlement_access_review.readiness_status,
                "tenant entitlement privileged policies": entitlement_access_review.summary[
                    "privileged_policy_count"
                ],
                "tenant_entitlement_privileged_policies": entitlement_access_review.summary[
                    "privileged_policy_count"
                ],
                "tenant entitlement access review pack path": entitlement_access_review_pack.markdown_path,
                "tenant_entitlement_access_review_pack_path": entitlement_access_review_pack.markdown_path,
                "skill marketplace readiness": marketplace_catalog.readiness_status,
                "skill_marketplace_readiness": marketplace_catalog.readiness_status,
                "marketplace catalog listings": marketplace_catalog.coverage_summary["listing_count"],
                "marketplace_catalog_listings": marketplace_catalog.coverage_summary["listing_count"],
                "marketplace promotion gate": marketplace_promotion_gate.readiness_status,
                "marketplace_promotion_gate": marketplace_promotion_gate.readiness_status,
                "marketplace promotion can promote": marketplace_promotion_gate.can_promote,
                "marketplace_promotion_can_promote": marketplace_promotion_gate.can_promote,
                "tenant rollout approval pack path": marketplace_pack.markdown_path,
                "tenant_rollout_approval_pack_path": marketplace_pack.markdown_path,
                "marketplace approval workflow pack path": marketplace_approval_pack.markdown_path,
                "marketplace_approval_workflow_pack_path": marketplace_approval_pack.markdown_path,
                "skill compatibility readiness": compatibility_report.readiness_status,
                "skill_compatibility_readiness": compatibility_report.readiness_status,
                "skill compatibility pack path": compatibility_pack.markdown_path,
                "skill_compatibility_pack_path": compatibility_pack.markdown_path,
                "skill usage analytics readiness": usage_analytics.readiness_status,
                "skill_usage_analytics_readiness": usage_analytics.readiness_status,
                "cost chargeback estimated cost": usage_analytics.summary["estimated_cost"],
                "cost_chargeback_estimated_cost": usage_analytics.summary["estimated_cost"],
                "chargeback pack path": usage_chargeback_pack.markdown_path,
                "chargeback_pack_path": usage_chargeback_pack.markdown_path,
                "skill reliability readiness": reliability_report.readiness_status,
                "skill_reliability_readiness": reliability_report.readiness_status,
                "skill reliability open circuits": reliability_report.summary["open_circuit_count"],
                "skill_reliability_open_circuits": reliability_report.summary["open_circuit_count"],
                "skill reliability disable recommendations": reliability_report.summary[
                    "disable_recommendation_count"
                ],
                "skill_reliability_disable_recommendations": reliability_report.summary[
                    "disable_recommendation_count"
                ],
                "reliability pack path": reliability_pack.markdown_path,
                "reliability_pack_path": reliability_pack.markdown_path,
                "skill slo readiness": slo_report.readiness_status,
                "skill_slo_readiness": slo_report.readiness_status,
                "skill slo release gate": slo_report.release_gate["status"],
                "skill_slo_release_gate": slo_report.release_gate["status"],
                "skill slo blocked release skills": slo_report.summary[
                    "blocked_release_skill_count"
                ],
                "skill_slo_blocked_release_skills": slo_report.summary[
                    "blocked_release_skill_count"
                ],
                "slo pack path": slo_pack.markdown_path,
                "slo_pack_path": slo_pack.markdown_path,
                "provider readiness": provider_readiness.readiness_status,
                "provider_readiness": provider_readiness.readiness_status,
                "provider current": provider_readiness.current_provider["name"],
                "provider_current": provider_readiness.current_provider["name"],
                "provider fallback pack path": provider_fallback_pack.markdown_path,
                "provider_fallback_pack_path": provider_fallback_pack.markdown_path,
                "provider failover readiness": provider_failover_drill.readiness_status,
                "provider_failover_readiness": provider_failover_drill.readiness_status,
                "provider failover decisions": provider_failover_drill.summary[
                    "fallback_decision_count"
                ],
                "provider_failover_decisions": provider_failover_drill.summary[
                    "fallback_decision_count"
                ],
                "provider failover pack path": provider_failover_pack.markdown_path,
                "provider_failover_pack_path": provider_failover_pack.markdown_path,
                "config hygiene readiness": config_hygiene_report.readiness_status,
                "config_hygiene_readiness": config_hygiene_report.readiness_status,
                "config hygiene secret findings": config_hygiene_report.summary["secret_finding_count"],
                "config_hygiene_secret_findings": config_hygiene_report.summary["secret_finding_count"],
                "config hygiene pack path": config_hygiene_pack.markdown_path,
                "config_hygiene_pack_path": config_hygiene_pack.markdown_path,
                "platform pack readiness": platform_pack_report.readiness_status,
                "platform_pack_readiness": platform_pack_report.readiness_status,
                "platform pack controls": len(platform_pack_report.capability_controls),
                "platform_pack_controls": len(platform_pack_report.capability_controls),
                "platform pack path": platform_pack_export.markdown_path,
                "platform_pack_path": platform_pack_export.markdown_path,
                "review sla readiness": review_sla_report.readiness_status,
                "review_sla_readiness": review_sla_report.readiness_status,
                "review sla open items": review_sla_report.summary["open_item_count"],
                "review_sla_open_items": review_sla_report.summary["open_item_count"],
                "review sla pack path": review_sla_pack.markdown_path,
                "review_sla_pack_path": review_sla_pack.markdown_path,
                "agent collaboration readiness": agent_collaboration_run.readiness_status,
                "agent_collaboration_readiness": agent_collaboration_run.readiness_status,
                "agent collaboration handoffs": agent_collaboration_run.governance_summary["handoff_count"],
                "agent_collaboration_handoffs": agent_collaboration_run.governance_summary["handoff_count"],
                "agent collaboration pack path": agent_collaboration_pack.markdown_path,
                "agent_collaboration_pack_path": agent_collaboration_pack.markdown_path,
                "agent society eval readiness": agent_society_eval.readiness_status,
                "agent_society_eval_readiness": agent_society_eval.readiness_status,
                "agent society eval score": agent_society_eval.summary["score"],
                "agent_society_eval_score": agent_society_eval.summary["score"],
                "agent society eval pack path": agent_society_eval_pack.markdown_path,
                "agent_society_eval_pack_path": agent_society_eval_pack.markdown_path,
                "worker scaleout readiness": worker_scale_plan.readiness_status,
                "worker_scaleout_readiness": worker_scale_plan.readiness_status,
                "worker run status": worker_run.status,
                "worker_run_status": worker_run.status,
                "worker run timeline stages": len(worker_run.timeline),
                "worker_run_timeline_stages": len(worker_run.timeline),
                "worker queue admission readiness": worker_queue_admission.readiness_status,
                "worker_queue_admission_readiness": worker_queue_admission.readiness_status,
                "worker queue decisions": worker_queue_admission.summary["decision_count"],
                "worker_queue_decisions": worker_queue_admission.summary["decision_count"],
                "worker queue pack path": worker_queue_pack.markdown_path,
                "worker_queue_pack_path": worker_queue_pack.markdown_path,
                "worker runbook path": worker_runbook.markdown_path,
                "worker_runbook_path": worker_runbook.markdown_path,
                "task run ledger readiness": task_run_ledger.readiness_status,
                "task_run_ledger_readiness": task_run_ledger.readiness_status,
                "task run ledger entries": task_run_ledger.summary["ledger_entry_count"],
                "task_run_ledger_entries": task_run_ledger.summary["ledger_entry_count"],
                "task run transparency pack path": task_run_transparency_pack.markdown_path,
                "task_run_transparency_pack_path": task_run_transparency_pack.markdown_path,
                "policy replay readiness": policy_replay_report.readiness_status,
                "policy_replay_readiness": policy_replay_report.readiness_status,
                "policy replay drift count": policy_replay_report.summary["drift_count"],
                "policy_replay_drift_count": policy_replay_report.summary["drift_count"],
                "policy replay pack path": policy_replay_pack.markdown_path,
                "policy_replay_pack_path": policy_replay_pack.markdown_path,
                "audit integrity readiness": audit_integrity.readiness_status,
                "audit_integrity_readiness": audit_integrity.readiness_status,
                "audit integrity records": audit_integrity.summary["record_count"],
                "audit_integrity_records": audit_integrity.summary["record_count"],
                "audit integrity root hash": audit_integrity.root_hash,
                "audit_integrity_root_hash": audit_integrity.root_hash,
                "audit integrity pack path": audit_integrity_pack.markdown_path,
                "audit_integrity_pack_path": audit_integrity_pack.markdown_path,
                "invocation sandbox readiness": invocation_sandbox_report.readiness_status,
                "invocation_sandbox_readiness": invocation_sandbox_report.readiness_status,
                "invocation sandbox denied decisions": invocation_sandbox_report.summary[
                    "denied_decision_count"
                ],
                "invocation_sandbox_denied_decisions": invocation_sandbox_report.summary[
                    "denied_decision_count"
                ],
                "invocation sandbox pack path": invocation_sandbox_pack.markdown_path,
                "invocation_sandbox_pack_path": invocation_sandbox_pack.markdown_path,
                "sandbox exception status": sandbox_exception_decision.status,
                "sandbox_exception_status": sandbox_exception_decision.status,
                "sandbox exception pack path": sandbox_exception_pack.markdown_path,
                "sandbox_exception_pack_path": sandbox_exception_pack.markdown_path,
                "prompt governance readiness": prompt_governance_report.readiness_status,
                "prompt_governance_readiness": prompt_governance_report.readiness_status,
                "prompt governance findings": prompt_governance_report.summary["finding_count"],
                "prompt_governance_findings": prompt_governance_report.summary["finding_count"],
                "prompt governance approvals": prompt_governance_report.summary[
                    "approval_required_count"
                ],
                "prompt_governance_approvals": prompt_governance_report.summary[
                    "approval_required_count"
                ],
                "prompt governance pack path": prompt_governance_pack.markdown_path,
                "prompt_governance_pack_path": prompt_governance_pack.markdown_path,
                "prompt governance remediation plan path": prompt_governance_remediation.markdown_path,
                "prompt_governance_remediation_plan_path": prompt_governance_remediation.markdown_path,
                "prompt governance remediation steps": prompt_governance_remediation.summary[
                    "step_count"
                ],
                "prompt_governance_remediation_steps": prompt_governance_remediation.summary[
                    "step_count"
                ],
                "privacy retention readiness": privacy_retention_report.readiness_status,
                "privacy_retention_readiness": privacy_retention_report.readiness_status,
                "privacy retention findings": privacy_retention_report.summary["finding_count"],
                "privacy_retention_findings": privacy_retention_report.summary["finding_count"],
                "privacy retention pack path": privacy_retention_pack.markdown_path,
                "privacy_retention_pack_path": privacy_retention_pack.markdown_path,
                "enterprise readiness": enterprise_scorecard.readiness_status,
                "enterprise_readiness": enterprise_scorecard.readiness_status,
                "enterprise_readiness_score": enterprise_scorecard.overall_score,
                "portfolio demo pack path": portfolio_demo_pack.markdown_path,
                "portfolio_demo_pack_path": portfolio_demo_pack.markdown_path,
                "portfolio evidence score": portfolio_evidence.evidence_score,
                "portfolio_evidence_score": portfolio_evidence.evidence_score,
                "portfolio evidence count": portfolio_evidence.proof_count,
                "portfolio_evidence_count": portfolio_evidence.proof_count,
                "interview pack path": interview_pack.markdown_path,
                "interview_pack_path": interview_pack.markdown_path,
                "smoke readiness": smoke_matrix.readiness_status,
                "smoke_readiness": smoke_matrix.readiness_status,
                "launch checklist path": launch_checklist.markdown_path,
                "launch_checklist_path": launch_checklist.markdown_path,
                "release gate status": release_gate.status,
                "release_gate_status": release_gate.status,
                "release gate score": release_gate.score,
                "release_gate_score": release_gate.score,
                "publish pack path": publish_pack.markdown_path,
                "publish_pack_path": publish_pack.markdown_path,
                "ci doctor status": ci_doctor.readiness_status,
                "ci_doctor_status": ci_doctor.readiness_status,
                "ci doctor score": ci_doctor.score,
                "ci_doctor_score": ci_doctor.score,
                "audit pack path": audit_pack.markdown_path,
                "audit_pack_path": audit_pack.markdown_path,
                "supply chain readiness": supply_chain_report.readiness_status,
                "supply_chain_readiness": supply_chain_report.readiness_status,
                "supply chain package count": supply_chain_report.summary["package_count"],
                "supply_chain_package_count": supply_chain_report.summary["package_count"],
                "supply chain pack path": supply_chain_pack.markdown_path,
                "supply_chain_pack_path": supply_chain_pack.markdown_path,
                "reviewer quickstart status": reviewer_quickstart.readiness_status,
                "reviewer_quickstart_status": reviewer_quickstart.readiness_status,
                "reviewer quickstart count": reviewer_quickstart.summary["quickstart_item_count"],
                "reviewer_quickstart_count": reviewer_quickstart.summary["quickstart_item_count"],
                "walkthrough pack path": walkthrough_pack.markdown_path,
                "walkthrough_pack_path": walkthrough_pack.markdown_path,
                "artifact inventory count": artifact_inventory.artifact_count,
                "artifact_inventory_count": artifact_inventory.artifact_count,
                "readme checklist path": readme_checklist.markdown_path,
                "readme_checklist_path": readme_checklist.markdown_path,
                "dashboard smoke status": dashboard_smoke.readiness_status,
                "dashboard_smoke_status": dashboard_smoke.readiness_status,
                "dashboard smoke checks": dashboard_smoke.summary["check_count"],
                "dashboard_smoke_checks": dashboard_smoke.summary["check_count"],
                "ui verification pack path": ui_verification_pack.markdown_path,
                "ui_verification_pack_path": ui_verification_pack.markdown_path,
                "final audit status": final_audit.readiness_status,
                "final_audit_status": final_audit.readiness_status,
                "final audit score": final_audit.score,
                "final_audit_score": final_audit.score,
                "final pack path": final_pack.markdown_path,
                "final_pack_path": final_pack.markdown_path,
                "git readiness status": git_readiness.readiness_status,
                "git_readiness_status": git_readiness.readiness_status,
                "git readiness branch": git_readiness.git_repository["current_branch"],
                "git_readiness_branch": git_readiness.git_repository["current_branch"],
                "git push plan path": git_push_plan.markdown_path,
                "git_push_plan_path": git_push_plan.markdown_path,
                "repository automation readiness": repository_automation_plan.readiness_status,
                "repository_automation_readiness": repository_automation_plan.readiness_status,
                "repository automation tasks": repository_automation_plan.summary[
                    "planned_task_count"
                ],
                "repository_automation_tasks": repository_automation_plan.summary[
                    "planned_task_count"
                ],
                "repository automation pack path": repository_automation_pack.markdown_path,
                "repository_automation_pack_path": repository_automation_pack.markdown_path,
                "runtime demo readiness": runtime_readiness.readiness_status,
                "runtime_demo_readiness": runtime_readiness.readiness_status,
                "runtime demo pack path": runtime_pack.markdown_path,
                "runtime_demo_pack_path": runtime_pack.markdown_path,
                "api contract audit status": api_contract_audit.readiness_status,
                "api_contract_audit_status": api_contract_audit.readiness_status,
                "api contract route count": api_contract_audit.openapi_route_count,
                "api_contract_route_count": api_contract_audit.openapi_route_count,
                "api contract drift status": api_contract_audit.contract_drift["status"],
                "api_contract_drift_status": api_contract_audit.contract_drift["status"],
                "reviewer collection path": api_reviewer_collection.markdown_path,
                "reviewer_collection_path": api_reviewer_collection.markdown_path,
                "contract drift pack path": api_contract_drift_pack.markdown_path,
                "contract_drift_pack_path": api_contract_drift_pack.markdown_path,
                "contract remediation readiness": api_contract_remediation.readiness_status,
                "contract_remediation_readiness": api_contract_remediation.readiness_status,
                "contract remediation steps": len(api_contract_remediation.bounded_steps),
                "contract_remediation_steps": len(api_contract_remediation.bounded_steps),
                "contract remediation pack path": api_contract_remediation_pack.markdown_path,
                "contract_remediation_pack_path": api_contract_remediation_pack.markdown_path,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
