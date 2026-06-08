from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException, Request

from app import __version__
from app.bootstrap import create_state
from app.config import get_settings
from app.models import (
    AgentRun,
    AgentRunRequest,
    AuditEvent,
    HealthResponse,
    InvokeSkillRequest,
    McpToolDefinition,
    PromptDefinition,
    RegisterSkillRequest,
    ResourceDefinition,
    ResourcePayload,
    SkillInvocation,
    SkillManifest,
    SkillStatusRequest,
    SkillVersion,
    UsageSummary,
    ValidateSkillRequest,
    ValidationResult,
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


@app.post("/skills/register", response_model=SkillManifest)
def register_skill(request: RegisterSkillRequest, _: str = Depends(require_api_key)) -> SkillManifest:
    result = state.validator.validate_manifest(request.manifest.model_dump(mode="json"))
    if not result.valid:
        raise HTTPException(status_code=422, detail=result.errors)
    return state.registry.register(request.manifest, actor="api-user")


@app.post("/skills/{skill_id}/invoke", response_model=SkillInvocation)
async def invoke_skill(
    skill_id: str,
    request: InvokeSkillRequest,
    _: str = Depends(require_api_key),
) -> SkillInvocation:
    try:
        invocation = await state.invocation_service.invoke(skill_id, request.input, request.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if invocation.status == "failed":
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


@app.get("/audit/events", response_model=list[AuditEvent])
def audit_events(_: str = Depends(require_api_key)) -> list[AuditEvent]:
    return state.audit.events


@app.get("/metrics/usage", response_model=UsageSummary)
def usage(_: str = Depends(require_api_key)) -> UsageSummary:
    return state.metrics.summary()


@app.get("/invocations", response_model=list[SkillInvocation])
def invocations(_: str = Depends(require_api_key)) -> list[SkillInvocation]:
    return state.invocation_service.invocations


@app.get("/mcp/tools", response_model=list[McpToolDefinition])
def mcp_tools(_: str = Depends(require_api_key)) -> list[McpToolDefinition]:
    return state.mcp.list_tools()


@app.post("/mcp/tools/{tool_name}/call")
async def mcp_call_tool(
    tool_name: str,
    request: InvokeSkillRequest,
    _: str = Depends(require_api_key),
) -> dict:
    return await state.mcp.call_tool(tool_name, request.input, request.actor)


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
