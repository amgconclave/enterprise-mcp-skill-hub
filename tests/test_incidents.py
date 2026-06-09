from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    SkillIncidentDrillRequest,
    SkillIncidentRunbookRequest,
    SkillIncidentScenario,
    SkillManifest,
)
from app.services import (
    CapacityPlanningService,
    DependencyMapService,
    ReleaseService,
    SkillIncidentDrillService,
)

HEADERS = {"X-API-Key": "dev-local-token"}
SCENARIOS: list[SkillIncidentScenario] = [
    "schema_breakage",
    "disabled_skill_invoked",
    "policy_denial_spike",
    "latency_capacity_breach",
    "workflow_dependency_failure",
]


def incident_state(tmp_path: Path):
    state = create_state()
    state.releases = ReleaseService(
        state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )
    state.capacity = CapacityPlanningService(state, output_dir=tmp_path / "capacity")
    state.dependencies = DependencyMapService(state, output_dir=tmp_path / "dependencies")
    state.incidents = SkillIncidentDrillService(state, output_dir=tmp_path / "incident_runbooks")
    return state


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_incident_drill_scenarios_return_recovery_evidence(
    tmp_path: Path,
    scenario: SkillIncidentScenario,
) -> None:
    state = incident_state(tmp_path)

    drill = asyncio.run(
        state.incidents.drill(SkillIncidentDrillRequest(scenario=scenario, actor="pytest-incident"))
    )

    assert drill.scenario == scenario
    assert drill.severity in {"sev1", "sev2", "sev3"}
    assert drill.readiness_status in {"ready", "needs_review", "blocked"}
    assert drill.simulated_symptoms
    assert drill.containment_actions
    assert drill.rollback_canary_plan
    assert "python -m app.evals.run_conformance" in drill.conformance_eval_commands
    assert "query_endpoint" in drill.audit_evidence
    assert drill.capacity_links["forecast_endpoint"] == "/capacity/forecast"
    assert drill.dependency_links["map_endpoint"] == "/dependencies/map"
    assert set(drill.mcp_capabilities_affected) == {
        "tools",
        "workflows",
        "prompts",
        "resources",
        "likely_tool_calls",
    }


def test_incident_endpoints_return_drill_and_runbook(tmp_path: Path) -> None:
    main_module.state = incident_state(tmp_path)
    client = TestClient(app)

    drill = client.post(
        "/incidents/drill",
        headers=HEADERS,
        json={"scenario": "policy_denial_spike", "actor": "pytest-incident"},
    )
    runbook = client.post(
        "/incidents/runbook",
        headers=HEADERS,
        json={"scenario": "schema_breakage", "actor": "pytest-incident"},
    )

    assert drill.status_code == 200
    assert drill.json()["scenario"] == "policy_denial_spike"
    assert "search_knowledge_base" in drill.json()["affected_skills"]
    assert runbook.status_code == 200
    assert runbook.json()["scenario"] == "schema_breakage"
    assert Path(runbook.json()["json_path"]).exists()
    assert Path(runbook.json()["markdown_path"]).exists()


def test_incident_runbook_export_writes_markdown_and_json(tmp_path: Path) -> None:
    state = incident_state(tmp_path)

    export = asyncio.run(
        state.incidents.runbook(
            SkillIncidentRunbookRequest(
                scenario="workflow_dependency_failure",
                actor="pytest-incident",
            )
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["scenario"] == "workflow_dependency_failure"
    assert "drill_summary" in bundle
    assert "timeline" in bundle
    assert "owner_matrix" in bundle
    assert "verification_commands" in bundle
    assert "mcp_capabilities_affected" in bundle
    assert len(bundle["interviewer_talking_points"]) == 5
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Skill Incident Recovery Runbook" in markdown
    assert "MCP Capabilities Affected" in markdown


def test_incident_drill_excludes_disabled_and_draft_skills(tmp_path: Path) -> None:
    state = incident_state(tmp_path)
    state.registry.set_status("translate_text", False, "pytest")
    draft = SkillManifest(
        id="draft_incident_candidate",
        name="Draft Incident Candidate",
        version="1.0.0",
        description="Draft skill that should not affect incident blast radius.",
        provider="mock",
        enabled=True,
        status="draft",
        tags=["incident"],
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    )
    state.registry.register(draft, "pytest")

    drill = asyncio.run(
        state.incidents.drill(
            SkillIncidentDrillRequest(
                scenario="disabled_skill_invoked",
                actor="pytest-incident",
            )
        )
    )

    assert "translate_text" not in drill.affected_skills
    assert "draft_incident_candidate" not in drill.affected_skills
    assert "translate_text" in {skill["id"] for skill in drill.excluded_skills["disabled"]}
    assert "draft_incident_candidate" in {skill["id"] for skill in drill.excluded_skills["draft"]}
