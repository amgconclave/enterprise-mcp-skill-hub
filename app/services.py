from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.models import (
    AgentRun,
    AuditEvent,
    GovernanceCheck,
    GovernanceReport,
    JsonDict,
    LocalSnapshot,
    McpToolDefinition,
    PolicyInvocationContext,
    PromptArgument,
    PromptDefinition,
    ResourceDefinition,
    ResourcePayload,
    SkillGovernanceRecord,
    SkillInvocation,
    SkillManifest,
    SkillVersion,
    TokenUsage,
    UsageMetric,
    UsageSummary,
)
from app.policy import PolicyService
from app.providers import BaseLLMProvider
from app.skills import BUILTIN_HANDLERS
from app.utils import Timer, manifest_hash, new_id, new_trace_id, utc_now
from app.validator import SkillValidator


class AuditService:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        trace_id: str,
        actor: str = "system",
        metadata: JsonDict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=new_id("aud"),
            trace_id=trace_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            created_at=utc_now(),
            metadata=metadata or {},
        )
        self.events.append(event)
        return event


class MetricsService:
    def __init__(self) -> None:
        self.metrics: list[UsageMetric] = []

    def record(self, metric: UsageMetric) -> None:
        self.metrics.append(metric)

    def summary(self) -> UsageSummary:
        count = len(self.metrics)
        failures = sum(1 for metric in self.metrics if metric.status == "failed")
        latency = sum(metric.latency_ms for metric in self.metrics)
        by_skill: dict[str, int] = {}
        for metric in self.metrics:
            if metric.skill_id:
                by_skill[metric.skill_id] = by_skill.get(metric.skill_id, 0) + 1
        return UsageSummary(
            invocation_count=count,
            failure_count=failures,
            average_latency_ms=round(latency / count, 2) if count else 0.0,
            input_tokens=sum(metric.input_tokens for metric in self.metrics),
            output_tokens=sum(metric.output_tokens for metric in self.metrics),
            estimated_cost=round(sum(metric.estimated_cost for metric in self.metrics), 6),
            by_skill=by_skill,
        )


class SkillRegistry:
    def __init__(self, audit: AuditService) -> None:
        self.audit = audit
        self._skills: dict[str, SkillManifest] = {}
        self._versions: dict[str, list[SkillVersion]] = {}

    def register(self, manifest: SkillManifest, actor: str = "system") -> SkillManifest:
        manifest = self._normalize_manifest(manifest)
        version = SkillVersion(
            skill_id=manifest.id,
            version=manifest.version,
            manifest_hash=manifest_hash(manifest.model_dump(mode="json")),
            created_at=utc_now(),
            status=manifest.status,
        )
        self._skills[manifest.id] = manifest
        self._versions.setdefault(manifest.id, []).append(version)
        self.audit.record(
            "skill.registered",
            "skill",
            manifest.id,
            new_trace_id(),
            actor,
            {"version": manifest.version, "status": manifest.status, "enabled": manifest.enabled},
        )
        return manifest

    def list(self) -> list[SkillManifest]:
        return sorted(self._skills.values(), key=lambda skill: skill.id)

    def enabled(self) -> list[SkillManifest]:
        return [skill for skill in self.list() if skill.enabled]

    def mcp_exposed(self) -> list[SkillManifest]:
        return [skill for skill in self.list() if self.is_mcp_exposed(skill)]

    def is_mcp_exposed(self, skill: SkillManifest) -> bool:
        return skill.enabled and skill.status == "promoted"

    def get(self, skill_id: str) -> SkillManifest:
        if skill_id not in self._skills:
            raise KeyError(f"Unknown skill: {skill_id}")
        return self._skills[skill_id]

    def set_status(self, skill_id: str, enabled: bool, actor: str = "system") -> SkillManifest:
        status = "promoted" if enabled else "disabled"
        manifest = self.get(skill_id).model_copy(update={"enabled": enabled, "status": status})
        self._skills[skill_id] = manifest
        self._update_latest_version_status(skill_id, manifest.status)
        self.audit.record(
            "skill.enabled" if enabled else "skill.disabled",
            "skill",
            skill_id,
            new_trace_id(),
            actor,
            {"status": manifest.status},
        )
        return manifest

    def promote(self, skill_id: str, actor: str = "system") -> SkillManifest:
        manifest = self.get(skill_id).model_copy(update={"enabled": True, "status": "promoted"})
        self._skills[skill_id] = manifest
        self._update_latest_version_status(skill_id, manifest.status)
        self.audit.record(
            "skill.promoted",
            "skill",
            skill_id,
            new_trace_id(),
            actor,
            {"version": manifest.version, "status": manifest.status, "enabled": manifest.enabled},
        )
        return manifest

    def versions(self, skill_id: str) -> list[SkillVersion]:
        self.get(skill_id)
        return self._versions.get(skill_id, [])

    def _normalize_manifest(self, manifest: SkillManifest) -> SkillManifest:
        if not manifest.enabled or manifest.status == "disabled":
            return manifest.model_copy(update={"enabled": False, "status": "disabled"})
        if manifest.status == "promoted":
            return manifest.model_copy(update={"enabled": True})
        return manifest

    def _update_latest_version_status(self, skill_id: str, status: str) -> None:
        versions = self._versions.get(skill_id, [])
        if versions:
            versions[-1] = versions[-1].model_copy(update={"status": status})


class SkillInvocationService:
    def __init__(
        self,
        registry: SkillRegistry,
        validator: SkillValidator,
        audit: AuditService,
        metrics: MetricsService,
        provider: BaseLLMProvider,
        policy: PolicyService,
    ) -> None:
        self.registry = registry
        self.validator = validator
        self.audit = audit
        self.metrics = metrics
        self.provider = provider
        self.policy = policy
        self.invocations: list[SkillInvocation] = []

    async def invoke(
        self,
        skill_id: str,
        payload: JsonDict,
        actor: str = "demo-user",
        policy_context: PolicyInvocationContext | None = None,
    ) -> SkillInvocation:
        trace_id = new_trace_id()
        manifest = self.registry.get(skill_id)
        if policy_context and policy_context.enforce:
            decision = self.policy.simulate(manifest, policy_context)
            if decision.decision == "deny":
                return self._record_failure(
                    manifest,
                    payload,
                    trace_id,
                    actor,
                    f"Policy denied invocation: {'; '.join(decision.reasons)}",
                    0.0,
                    audit_action="policy.denied",
                    metadata={
                        "status": "failed",
                        "policy_decision": decision.model_dump(mode="json"),
                    },
                )
        if not manifest.enabled:
            return self._record_failure(manifest, payload, trace_id, actor, "Skill is disabled.", 0.0)
        errors = self.validator.validate_invocation(manifest, payload)
        if errors:
            return self._record_failure(manifest, payload, trace_id, actor, "; ".join(errors), 0.0)
        with Timer() as timer:
            handler = BUILTIN_HANDLERS.get(skill_id)
            output = await handler(payload) if handler else await self._invoke_manifest_backed_skill(manifest, payload)
        output_errors = self.validator.validate_output(manifest, output)
        if output_errors:
            return self._record_failure(
                manifest,
                payload,
                trace_id,
                actor,
                f"Output schema validation failed: {'; '.join(output_errors)}",
                round(timer.elapsed_ms, 2),
            )
        usage = TokenUsage(
            input_tokens=sum(len(str(value).split()) for value in payload.values()),
            output_tokens=sum(len(str(value).split()) for value in output.values()),
            estimated_cost=0.0,
        )
        invocation = SkillInvocation(
            id=new_id("inv"),
            skill_id=skill_id,
            version=manifest.version,
            input=payload,
            output={**output, "metadata": {"trace_id": trace_id, "provider": self.provider.name}},
            status="succeeded",
            trace_id=trace_id,
            latency_ms=round(timer.elapsed_ms, 2),
            token_usage=usage,
            created_at=utc_now(),
        )
        self.invocations.append(invocation)
        self.audit.record("skill.invoked", "skill", skill_id, trace_id, actor, {"status": "succeeded"})
        self.metrics.record(
            UsageMetric(
                trace_id=trace_id,
                provider=self.provider.name,
                model=self.provider.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                latency_ms=invocation.latency_ms,
                estimated_cost=usage.estimated_cost,
                skill_id=skill_id,
                status="succeeded",
            )
        )
        return invocation

    async def _invoke_manifest_backed_skill(self, manifest: SkillManifest, payload: JsonDict) -> JsonDict:
        response, _usage = await self.provider.complete(
            f"Run governed skill {manifest.id}: {manifest.description}",
            {"input": payload, "schema": manifest.output_schema},
        )
        output: JsonDict = {}
        for field_name, definition in manifest.output_schema.get("properties", {}).items():
            schema_type = definition.get("type")
            if schema_type == "string":
                output[field_name] = response
            elif schema_type == "integer":
                output[field_name] = 0
            elif schema_type == "number":
                output[field_name] = 0.0
            elif schema_type == "boolean":
                output[field_name] = True
            elif schema_type == "array":
                output[field_name] = []
            elif schema_type == "object":
                output[field_name] = {}
        return output

    def _record_failure(
        self,
        manifest: SkillManifest,
        payload: JsonDict,
        trace_id: str,
        actor: str,
        error: str,
        latency_ms: float,
        audit_action: str = "skill.invoked",
        metadata: JsonDict | None = None,
    ) -> SkillInvocation:
        usage = TokenUsage()
        invocation = SkillInvocation(
            id=new_id("inv"),
            skill_id=manifest.id,
            version=manifest.version,
            input=payload,
            output=None,
            status="failed",
            trace_id=trace_id,
            latency_ms=latency_ms,
            token_usage=usage,
            created_at=utc_now(),
            error=error,
        )
        self.invocations.append(invocation)
        self.audit.record(
            audit_action,
            "skill",
            manifest.id,
            trace_id,
            actor,
            metadata or {"status": "failed", "error": error},
        )
        self.metrics.record(
            UsageMetric(
                trace_id=trace_id,
                provider=self.provider.name,
                model=self.provider.model,
                input_tokens=0,
                output_tokens=0,
                latency_ms=latency_ms,
                estimated_cost=0.0,
                skill_id=manifest.id,
                status="failed",
            )
        )
        return invocation


class PromptRegistry:
    def __init__(self) -> None:
        self.prompts = [
            PromptDefinition(
                id="support_reply",
                name="Support Reply",
                description="Draft a grounded support response from ticket details and policy context.",
                arguments=[
                    PromptArgument(name="ticket", description="Support ticket text"),
                    PromptArgument(name="policy_context", description="Relevant policy snippets", required=False),
                ],
                template="Use the ticket and policy context to draft a concise, empathetic support reply.",
            ),
            PromptDefinition(
                id="rfp_answer",
                name="RFP Answer",
                description="Answer procurement questions using approved product and governance context.",
                arguments=[PromptArgument(name="question", description="RFP question")],
                template="Answer the RFP question with approved capabilities, limits, and audit controls.",
            ),
            PromptDefinition(
                id="meeting_summary",
                name="Meeting Summary",
                description="Summarize meeting notes into decisions, risks, and action items.",
                arguments=[PromptArgument(name="notes", description="Meeting notes")],
                template="Create a meeting summary with decisions, risks, owners, and next actions.",
            ),
        ]

    def list(self) -> list[PromptDefinition]:
        return self.prompts

    def get(self, prompt_id: str) -> PromptDefinition:
        for prompt in self.prompts:
            if prompt.id == prompt_id:
                return prompt
        raise KeyError(f"Unknown prompt: {prompt_id}")


class ResourceRegistry:
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry
        self.root = Path(__file__).resolve().parents[1]
        self.resources = [
            ResourcePayload(
                definition=ResourceDefinition(
                    uri="resource://policy/ai-governance",
                    name="AI Governance Policy",
                    description="Fake policy covering approved AI skill use, auditability, and data handling.",
                    content_ref="sample_data/policy_ai_governance.md",
                    annotations={"kind": "policy"},
                ),
                content="",
            ),
            ResourcePayload(
                definition=ResourceDefinition(
                    uri="resource://product/skill-hub",
                    name="Skill Hub Product Brief",
                    description="Fake product brief for the governed MCP skill hub.",
                    content_ref="sample_data/product_skill_hub.md",
                    annotations={"kind": "product"},
                ),
                content="",
            ),
            ResourcePayload(
                definition=ResourceDefinition(
                    uri="resource://policy/vendor-risk",
                    name="Vendor Risk Policy",
                    description="Fake vendor risk policy for third-party LLM and tool provider reviews.",
                    content_ref="sample_data/vendor_risk_policy.md",
                    annotations={"kind": "policy"},
                ),
                content="",
            ),
        ]

    def list(self) -> list[ResourceDefinition]:
        catalog = ResourceDefinition(
            uri="resource://skill-catalog",
            name="Skill Catalog",
            description="Current enabled and disabled skill catalog.",
            mime_type="application/json",
            content_ref="dynamic:skill_registry",
            annotations={"kind": "catalog"},
        )
        return [resource.definition for resource in self.resources] + [catalog]

    def read(self, uri: str) -> ResourcePayload:
        if uri == "resource://skill-catalog":
            return ResourcePayload(
                definition=self.list()[-1],
                content="\n".join(
                    f"{skill.id} v{skill.version} status={skill.status} enabled={skill.enabled} "
                    f"mcp_exposed={self.registry.is_mcp_exposed(skill)}"
                    for skill in self.registry.list()
                ),
            )
        for resource in self.resources:
            if resource.definition.uri == uri:
                return resource.model_copy(update={"content": self._load_content(resource)})
        raise KeyError(f"Unknown resource: {uri}")

    def _load_content(self, resource: ResourcePayload) -> str:
        if resource.content:
            return resource.content
        path = self.root / resource.definition.content_ref
        if path.exists():
            return path.read_text(encoding="utf-8")
        return f"Resource file not found: {resource.definition.content_ref}"


class McpToolAdapter:
    def __init__(
        self,
        registry: SkillRegistry,
        invocation_service: SkillInvocationService,
        resources: ResourceRegistry,
        prompts: PromptRegistry,
        validator: SkillValidator,
    ) -> None:
        self.registry = registry
        self.invocation_service = invocation_service
        self.resources = resources
        self.prompts = prompts
        self.validator = validator

    def list_tools(self) -> list[McpToolDefinition]:
        return [
            McpToolDefinition(
                name=skill.id,
                description=skill.description,
                input_schema=skill.input_schema,
                output_schema=skill.output_schema,
                annotations={
                    "version": skill.version,
                    "tags": skill.tags,
                    "provider": skill.provider,
                    "status": skill.status,
                },
            )
            for skill in self.registry.mcp_exposed()
            if self.validator.validate_manifest(skill.model_dump(mode="json")).valid
        ]

    async def call_tool(
        self,
        name: str,
        arguments: JsonDict,
        actor: str = "mcp-client",
        policy_context: PolicyInvocationContext | None = None,
    ) -> JsonDict:
        try:
            manifest = self.registry.get(name)
        except KeyError:
            return {"status": "failed", "trace_id": new_trace_id(), "error": f"Unknown tool: {name}"}
        schema_valid = self.validator.validate_manifest(manifest.model_dump(mode="json")).valid
        if not self.registry.is_mcp_exposed(manifest) or not schema_valid:
            return {
                "status": "failed",
                "trace_id": new_trace_id(),
                "error": "Skill is not promoted and enabled for MCP exposure.",
            }
        invocation = await self.invocation_service.invoke(name, arguments, actor, policy_context)
        if invocation.status == "failed":
            return {"status": "failed", "trace_id": invocation.trace_id, "error": invocation.error}
        return {"status": "succeeded", "trace_id": invocation.trace_id, "result": invocation.output}

    def list_resources(self) -> list[ResourceDefinition]:
        return self.resources.list()

    def read_resource(self, uri: str) -> ResourcePayload:
        return self.resources.read(uri)

    def list_prompts(self) -> list[PromptDefinition]:
        return self.prompts.list()


class AgentRunner:
    def __init__(self, mcp: McpToolAdapter) -> None:
        self.mcp = mcp

    async def run(self, prompt: str, actor: str = "demo-user") -> AgentRun:
        selected = self._select_skills(prompt)
        trace = []
        usage = TokenUsage()
        with Timer() as timer:
            for skill_id, payload in selected:
                result = await self.mcp.call_tool(skill_id, payload, actor)
                trace.append({"skill": skill_id, "reason": self._reason(skill_id), "result": result})
                if result.get("status") == "succeeded":
                    usage.input_tokens += len(str(payload).split())
                    usage.output_tokens += len(str(result["result"]).split())
        final_output = self._compose_final(prompt, trace)
        return AgentRun(
            id=new_id("run"),
            prompt=prompt,
            selected_skills=[skill_id for skill_id, _ in selected],
            final_output=final_output,
            trace=trace,
            token_usage=usage,
            latency_ms=round(timer.elapsed_ms, 2),
        )

    def _select_skills(self, prompt: str) -> list[tuple[str, JsonDict]]:
        lower = prompt.lower()
        available = {tool.name for tool in self.mcp.list_tools()}
        selected: list[tuple[str, JsonDict]] = []
        self._append_if_available(selected, available, "classify_request", {"request": prompt})
        if any(term in lower for term in ["summarize", "meeting", "document", "notes"]):
            self._append_if_available(selected, available, "summarize_document", {"text": prompt})
        if any(term in lower for term in ["action", "owner", "next step", "meeting"]):
            self._append_if_available(selected, available, "generate_action_items", {"text": prompt})
        if any(term in lower for term in ["policy", "rfp", "knowledge", "approved"]):
            self._append_if_available(selected, available, "search_knowledge_base", {"query": prompt, "limit": 3})
        if any(term in lower for term in ["entity", "extract", "people", "company"]):
            self._append_if_available(selected, available, "extract_entities", {"text": prompt})
        if len(selected) < 2:
            self._append_if_available(selected, available, "search_knowledge_base", {"query": prompt, "limit": 2})
        return selected

    def _append_if_available(
        self,
        selected: list[tuple[str, JsonDict]],
        available: set[str],
        skill_id: str,
        payload: JsonDict,
    ) -> None:
        if skill_id in available and skill_id not in {name for name, _ in selected}:
            selected.append((skill_id, payload))

    def _reason(self, skill_id: str) -> str:
        reasons = {
            "classify_request": "Classify the task before routing follow-on skills.",
            "summarize_document": "Condense supplied context into a reusable brief.",
            "generate_action_items": "Extract owners and next steps for handoff.",
            "search_knowledge_base": "Ground the answer in approved internal resources.",
            "extract_entities": "Identify business entities and risks.",
        }
        return reasons.get(skill_id, "Selected by deterministic demo policy.")

    def _compose_final(self, prompt: str, trace: list[JsonDict]) -> str:
        skill_names = ", ".join(step["skill"] for step in trace)
        return f"Processed compound task with {len(trace)} governed skills: {skill_names}. Original task: {prompt[:160]}"


class GovernanceReportService:
    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state

    def generate(self) -> GovernanceReport:
        registry = self.app_state.registry
        metrics = self.app_state.metrics.summary()
        enabled_tools = self.app_state.mcp.list_tools()
        disabled_skills = [skill.id for skill in registry.list() if not skill.enabled]
        skill_records = [self._skill_record(skill) for skill in registry.list()]
        lifecycle_counts = {status: 0 for status in ["draft", "validated", "promoted", "disabled"]}
        for skill in registry.list():
            lifecycle_counts[skill.status] = lifecycle_counts.get(skill.status, 0) + 1
        mcp_exposed_count = sum(record.mcp_exposed for record in skill_records)
        unpromoted_enabled = [
            record.skill_id
            for record in skill_records
            if record.enabled and record.status != "promoted"
        ]
        checks = [
            GovernanceCheck(
                name="Manifest coverage",
                status="pass" if len(registry.list()) >= 6 else "fail",
                detail=f"{len(registry.list())} registered skills found.",
            ),
            GovernanceCheck(
                name="MCP discovery",
                status="pass" if len(enabled_tools) == mcp_exposed_count else "fail",
                detail=f"{len(enabled_tools)} promoted and enabled tools exposed through the MCP adapter.",
            ),
            GovernanceCheck(
                name="Promotion lifecycle",
                status="pass" if not unpromoted_enabled else "warn",
                detail=(
                    "All enabled skills are promoted for agent use."
                    if not unpromoted_enabled
                    else f"{len(unpromoted_enabled)} enabled skills are not promoted: {', '.join(unpromoted_enabled)}."
                ),
            ),
            GovernanceCheck(
                name="Schema validity",
                status="pass" if all(record.schema_valid for record in skill_records) else "fail",
                detail=f"{sum(record.schema_valid for record in skill_records)} of {len(skill_records)} manifests are valid.",
            ),
            GovernanceCheck(
                name="Resources and prompts",
                status="pass"
                if self.app_state.resources.list() and self.app_state.prompts.list()
                else "fail",
                detail=(
                    f"{len(self.app_state.resources.list())} resources and "
                    f"{len(self.app_state.prompts.list())} prompts available."
                ),
            ),
            GovernanceCheck(
                name="Audit trail",
                status="pass" if self.app_state.audit.events else "warn",
                detail=f"{len(self.app_state.audit.events)} audit events recorded.",
            ),
            GovernanceCheck(
                name="Policy access control",
                status="pass",
                detail="Local policy simulator covers admin, reviewer, agent, and viewer invocation decisions.",
            ),
            GovernanceCheck(
                name="Failure rate",
                status="pass" if metrics.failure_count == 0 else "warn",
                detail=f"{metrics.failure_count} failed invocations out of {metrics.invocation_count}.",
            ),
        ]
        if any(check.status == "fail" for check in checks):
            status = "fail"
        elif any(check.status == "warn" for check in checks):
            status = "warn"
        else:
            status = "pass"
        return GovernanceReport(
            generated_at=utc_now(),
            status=status,
            skills_registered=len(registry.list()),
            enabled_tools=len(enabled_tools),
            disabled_skills=disabled_skills,
            resource_count=len(self.app_state.resources.list()),
            prompt_count=len(self.app_state.prompts.list()),
            invocation_count=metrics.invocation_count,
            failure_count=metrics.failure_count,
            average_latency_ms=metrics.average_latency_ms,
            estimated_cost=metrics.estimated_cost,
            checks=checks,
            lifecycle_counts=lifecycle_counts,
            skills=skill_records,
        )

    def _skill_record(self, skill: SkillManifest) -> SkillGovernanceRecord:
        validation = self.app_state.validator.validate_manifest(skill.model_dump(mode="json"))
        invocations = [
            invocation
            for invocation in self.app_state.invocation_service.invocations
            if invocation.skill_id == skill.id
        ]
        failure_count = sum(1 for invocation in invocations if invocation.status == "failed")
        mcp_exposed = self.app_state.registry.is_mcp_exposed(skill) and validation.valid
        risk_flags = self._risk_flags(skill, validation.valid, failure_count, mcp_exposed)
        return SkillGovernanceRecord(
            skill_id=skill.id,
            version=skill.version,
            enabled=skill.enabled,
            status=skill.status,
            schema_valid=validation.valid,
            schema_errors=validation.errors,
            last_invocation=max((invocation.created_at for invocation in invocations), default=None),
            invocation_count=len(invocations),
            failure_count=failure_count,
            provider=skill.provider,
            tags=skill.tags,
            risk_flags=risk_flags,
            policy_access=self.app_state.policy.access_summary(skill),
            mcp_exposed=mcp_exposed,
            mcp_exposure_status="exposed" if mcp_exposed else "not_exposed",
        )

    def _risk_flags(
        self,
        skill: SkillManifest,
        schema_valid: bool,
        failure_count: int,
        mcp_exposed: bool,
    ) -> list[str]:
        flags: list[str] = []
        if not schema_valid:
            flags.append("schema_invalid")
        if skill.status == "disabled" or not skill.enabled:
            flags.append("disabled")
        elif skill.status != "promoted":
            flags.append("not_promoted")
        if not mcp_exposed:
            flags.append("not_exposed")
        if not skill.tags:
            flags.append("untagged")
        if skill.provider != "mock":
            flags.append("external_provider")
        if failure_count:
            flags.append("invocation_failures")
        flags.extend(self.app_state.policy.risk_flags(skill))
        return flags


class PersistenceService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(".local") / "skill_hub_snapshot.json"

    def save(self, app_state: AppState) -> LocalSnapshot:
        payload = {
            "saved_at": utc_now().isoformat(),
            "skills": [skill.model_dump(mode="json") for skill in app_state.registry.list()],
            "versions": {
                skill.id: [version.model_dump(mode="json") for version in app_state.registry.versions(skill.id)]
                for skill in app_state.registry.list()
            },
            "invocations": [
                invocation.model_dump(mode="json") for invocation in app_state.invocation_service.invocations
            ],
            "audit_events": [event.model_dump(mode="json") for event in app_state.audit.events],
            "metrics": [metric.model_dump(mode="json") for metric in app_state.metrics.metrics],
            "governance_report": app_state.governance.generate().model_dump(mode="json"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return LocalSnapshot(
            path=str(self.path),
            saved_at=utc_now(),
            skills=len(payload["skills"]),
            invocations=len(payload["invocations"]),
            audit_events=len(payload["audit_events"]),
            metrics=len(payload["metrics"]),
        )

    def load(self) -> JsonDict:
        if not self.path.exists():
            return {"path": str(self.path), "exists": False}
        return {"path": str(self.path), "exists": True, "snapshot": json.loads(self.path.read_text(encoding="utf-8"))}


@dataclass
class AppState:
    validator: SkillValidator
    audit: AuditService
    metrics: MetricsService
    provider: BaseLLMProvider
    policy: PolicyService = field(default_factory=PolicyService)
    registry: SkillRegistry = field(init=False)
    invocation_service: SkillInvocationService = field(init=False)
    prompts: PromptRegistry = field(init=False)
    resources: ResourceRegistry = field(init=False)
    mcp: McpToolAdapter = field(init=False)
    agent: AgentRunner = field(init=False)
    governance: GovernanceReportService = field(init=False)
    persistence: PersistenceService = field(init=False)

    def __post_init__(self) -> None:
        self.registry = SkillRegistry(self.audit)
        self.invocation_service = SkillInvocationService(
            self.registry, self.validator, self.audit, self.metrics, self.provider, self.policy
        )
        self.prompts = PromptRegistry()
        self.resources = ResourceRegistry(self.registry)
        self.mcp = McpToolAdapter(
            self.registry,
            self.invocation_service,
            self.resources,
            self.prompts,
            self.validator,
        )
        self.agent = AgentRunner(self.mcp)
        self.governance = GovernanceReportService(self)
        self.persistence = PersistenceService()
