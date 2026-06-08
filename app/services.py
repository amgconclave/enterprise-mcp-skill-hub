from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import (
    AgentRun,
    AuditEvent,
    JsonDict,
    McpToolDefinition,
    PromptArgument,
    PromptDefinition,
    ResourceDefinition,
    ResourcePayload,
    SkillInvocation,
    SkillManifest,
    SkillVersion,
    TokenUsage,
    UsageMetric,
    UsageSummary,
)
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
        status = "enabled" if manifest.enabled else "disabled"
        version = SkillVersion(
            skill_id=manifest.id,
            version=manifest.version,
            manifest_hash=manifest_hash(manifest.model_dump(mode="json")),
            created_at=utc_now(),
            status=status,
        )
        self._skills[manifest.id] = manifest
        self._versions.setdefault(manifest.id, []).append(version)
        self.audit.record("skill.registered", "skill", manifest.id, new_trace_id(), actor, {"version": manifest.version})
        return manifest

    def list(self) -> list[SkillManifest]:
        return sorted(self._skills.values(), key=lambda skill: skill.id)

    def enabled(self) -> list[SkillManifest]:
        return [skill for skill in self.list() if skill.enabled]

    def get(self, skill_id: str) -> SkillManifest:
        if skill_id not in self._skills:
            raise KeyError(f"Unknown skill: {skill_id}")
        return self._skills[skill_id]

    def set_status(self, skill_id: str, enabled: bool, actor: str = "system") -> SkillManifest:
        manifest = self.get(skill_id).model_copy(update={"enabled": enabled})
        self._skills[skill_id] = manifest
        self.audit.record(
            "skill.enabled" if enabled else "skill.disabled",
            "skill",
            skill_id,
            new_trace_id(),
            actor,
        )
        return manifest

    def versions(self, skill_id: str) -> list[SkillVersion]:
        self.get(skill_id)
        return self._versions.get(skill_id, [])


class SkillInvocationService:
    def __init__(
        self,
        registry: SkillRegistry,
        validator: SkillValidator,
        audit: AuditService,
        metrics: MetricsService,
        provider: BaseLLMProvider,
    ) -> None:
        self.registry = registry
        self.validator = validator
        self.audit = audit
        self.metrics = metrics
        self.provider = provider
        self.invocations: list[SkillInvocation] = []

    async def invoke(self, skill_id: str, payload: JsonDict, actor: str = "demo-user") -> SkillInvocation:
        trace_id = new_trace_id()
        manifest = self.registry.get(skill_id)
        if not manifest.enabled:
            return self._record_failure(manifest, payload, trace_id, actor, "Skill is disabled.", 0.0)
        errors = self.validator.validate_invocation(manifest, payload)
        if errors:
            return self._record_failure(manifest, payload, trace_id, actor, "; ".join(errors), 0.0)
        handler = BUILTIN_HANDLERS.get(skill_id)
        if not handler:
            return self._record_failure(manifest, payload, trace_id, actor, "No handler registered.", 0.0)

        with Timer() as timer:
            output = await handler(payload)
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

    def _record_failure(
        self,
        manifest: SkillManifest,
        payload: JsonDict,
        trace_id: str,
        actor: str,
        error: str,
        latency_ms: float,
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
        self.audit.record("skill.invoked", "skill", manifest.id, trace_id, actor, {"status": "failed", "error": error})
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
        self.resources = [
            ResourcePayload(
                definition=ResourceDefinition(
                    uri="resource://policy/ai-governance",
                    name="AI Governance Policy",
                    description="Fake policy covering approved AI skill use, auditability, and data handling.",
                    content_ref="sample_data/policy_ai_governance.md",
                    annotations={"kind": "policy"},
                ),
                content="AI skills must be approved, schema validated, traceable, and reviewed before production use.",
            ),
            ResourcePayload(
                definition=ResourceDefinition(
                    uri="resource://product/skill-hub",
                    name="Skill Hub Product Brief",
                    description="Fake product brief for the governed MCP skill hub.",
                    content_ref="sample_data/product_skill_hub.md",
                    annotations={"kind": "product"},
                ),
                content="Enterprise MCP Skill Hub exposes reusable, governed AI capabilities to agents and apps.",
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
                content="\n".join(f"{skill.id} v{skill.version} enabled={skill.enabled}" for skill in self.registry.list()),
            )
        for resource in self.resources:
            if resource.definition.uri == uri:
                return resource
        raise KeyError(f"Unknown resource: {uri}")


class McpToolAdapter:
    def __init__(
        self,
        registry: SkillRegistry,
        invocation_service: SkillInvocationService,
        resources: ResourceRegistry,
        prompts: PromptRegistry,
    ) -> None:
        self.registry = registry
        self.invocation_service = invocation_service
        self.resources = resources
        self.prompts = prompts

    def list_tools(self) -> list[McpToolDefinition]:
        return [
            McpToolDefinition(
                name=skill.id,
                description=skill.description,
                input_schema=skill.input_schema,
                output_schema=skill.output_schema,
                annotations={"version": skill.version, "tags": skill.tags, "provider": skill.provider},
            )
            for skill in self.registry.enabled()
        ]

    async def call_tool(self, name: str, arguments: JsonDict, actor: str = "mcp-client") -> JsonDict:
        invocation = await self.invocation_service.invoke(name, arguments, actor)
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
                    metadata = result["result"].get("metadata", {})
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
        selected: list[tuple[str, JsonDict]] = []
        selected.append(("classify_request", {"request": prompt}))
        if any(term in lower for term in ["summarize", "meeting", "document", "notes"]):
            selected.append(("summarize_document", {"text": prompt}))
        if any(term in lower for term in ["action", "owner", "next step", "meeting"]):
            selected.append(("generate_action_items", {"text": prompt}))
        if any(term in lower for term in ["policy", "rfp", "knowledge", "approved"]):
            selected.append(("search_knowledge_base", {"query": prompt, "limit": 3}))
        if any(term in lower for term in ["entity", "extract", "people", "company"]):
            selected.append(("extract_entities", {"text": prompt}))
        if len(selected) < 2:
            selected.append(("search_knowledge_base", {"query": prompt, "limit": 2}))
        return selected

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


@dataclass
class AppState:
    validator: SkillValidator
    audit: AuditService
    metrics: MetricsService
    provider: BaseLLMProvider
    registry: SkillRegistry = field(init=False)
    invocation_service: SkillInvocationService = field(init=False)
    prompts: PromptRegistry = field(init=False)
    resources: ResourceRegistry = field(init=False)
    mcp: McpToolAdapter = field(init=False)
    agent: AgentRunner = field(init=False)

    def __post_init__(self) -> None:
        self.registry = SkillRegistry(self.audit)
        self.invocation_service = SkillInvocationService(
            self.registry, self.validator, self.audit, self.metrics, self.provider
        )
        self.prompts = PromptRegistry()
        self.resources = ResourceRegistry(self.registry)
        self.mcp = McpToolAdapter(self.registry, self.invocation_service, self.resources, self.prompts)
        self.agent = AgentRunner(self.mcp)
