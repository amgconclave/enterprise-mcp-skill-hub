from __future__ import annotations

import asyncio
import json

from app.bootstrap import create_state
from app.models import (
    ApiReviewerCollectionRequest,
    ArtifactReadmeChecklistRequest,
    AuditPackRequest,
    BlastRadiusRequest,
    CapacityPlanExportRequest,
    ComplianceAttestationRequest,
    DependencyReportRequest,
    EnterprisePortfolioDemoPackRequest,
    FinalHandoffPackRequest,
    GitPushPlanRequest,
    LaunchChecklistRequest,
    MarketplaceRolloutPackRequest,
    PolicySimulationRequest,
    PortfolioInterviewPackRequest,
    ReleasePublishPackRequest,
    ReviewerWalkthroughPackRequest,
    RuntimeDemoPackRequest,
    SkillIncidentDrillRequest,
    SkillIncidentRunbookRequest,
    SkillReliabilityPackRequest,
    TenantSandboxExportRequest,
    UiVerificationPackRequest,
    UsageChargebackPackRequest,
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
    marketplace_catalog = await state.marketplace.catalog()
    marketplace_pack = await state.marketplace.rollout_pack(
        MarketplaceRolloutPackRequest(actor="demo-marketplace-reviewer")
    )
    usage_analytics = state.usage.analytics()
    usage_chargeback_pack = state.usage.chargeback_pack(
        UsageChargebackPackRequest(actor="demo-finops-reviewer")
    )
    reliability_report = state.reliability.report()
    reliability_pack = state.reliability.pack(
        SkillReliabilityPackRequest(actor="demo-platform-sre")
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
    runtime_readiness = state.runtime_demo.readiness()
    runtime_pack = state.runtime_demo.demo_pack(
        RuntimeDemoPackRequest(actor="demo-runtime-reviewer")
    )
    api_contract_audit = state.api_contracts.contract_audit()
    api_reviewer_collection = state.api_contracts.reviewer_collection(
        ApiReviewerCollectionRequest(actor="demo-api-contract-reviewer")
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
                "skill marketplace readiness": marketplace_catalog.readiness_status,
                "skill_marketplace_readiness": marketplace_catalog.readiness_status,
                "marketplace catalog listings": marketplace_catalog.coverage_summary["listing_count"],
                "marketplace_catalog_listings": marketplace_catalog.coverage_summary["listing_count"],
                "tenant rollout approval pack path": marketplace_pack.markdown_path,
                "tenant_rollout_approval_pack_path": marketplace_pack.markdown_path,
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
                "runtime demo readiness": runtime_readiness.readiness_status,
                "runtime_demo_readiness": runtime_readiness.readiness_status,
                "runtime demo pack path": runtime_pack.markdown_path,
                "runtime_demo_pack_path": runtime_pack.markdown_path,
                "api contract audit status": api_contract_audit.readiness_status,
                "api_contract_audit_status": api_contract_audit.readiness_status,
                "api contract route count": api_contract_audit.openapi_route_count,
                "api_contract_route_count": api_contract_audit.openapi_route_count,
                "reviewer collection path": api_reviewer_collection.markdown_path,
                "reviewer_collection_path": api_reviewer_collection.markdown_path,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
