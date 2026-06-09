from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import BlastRadiusRequest, DependencyReportRequest, SkillManifest
from app.services import CapacityPlanningService, DependencyMapService, ReleaseService

HEADERS = {"X-API-Key": "dev-local-token"}


def dependency_state(tmp_path: Path):
    state = create_state()
    state.releases = ReleaseService(
        state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )
    state.capacity = CapacityPlanningService(state, output_dir=tmp_path / "capacity")
    state.dependencies = DependencyMapService(state, output_dir=tmp_path / "dependencies")
    return state


def draft_manifest() -> SkillManifest:
    return SkillManifest(
        id="draft_dependency_candidate",
        name="Draft Dependency Candidate",
        version="1.0.0",
        description="Draft skill that should not become an active dependency node.",
        provider="mock",
        enabled=True,
        status="draft",
        tags=["dependencies"],
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


def test_dependency_map_graph_shape_and_centrality(tmp_path: Path) -> None:
    state = dependency_state(tmp_path)

    dependency_map = asyncio.run(state.dependencies.build_map())

    node_ids = {node.id for node in dependency_map.nodes}
    edge_pairs = {(edge.source, edge.target, edge.type) for edge in dependency_map.edges}
    assert dependency_map.readiness_status in {"ready", "needs_review", "blocked"}
    assert dependency_map.counts_by_node_type["skill"] == 6
    assert dependency_map.counts_by_node_type["tool"] == 6
    assert "skill:search_knowledge_base" in node_ids
    assert (
        "skill:search_knowledge_base",
        "tool:search_knowledge_base",
        "exposes_as_mcp_tool",
    ) in edge_pairs
    assert (
        "workflow:support_triage",
        "skill:search_knowledge_base",
        "uses_skill",
    ) in edge_pairs
    assert "search_knowledge_base" in {
        item["skill_id"] for item in dependency_map.high_centrality_skills
    }
    assert dependency_map.orphaned_prompts == []


def test_dependency_blast_radius_for_known_skill(tmp_path: Path) -> None:
    state = dependency_state(tmp_path)

    blast = asyncio.run(
        state.dependencies.blast_radius(
            BlastRadiusRequest(skill_id="search_knowledge_base", actor="pytest-dependency")
        )
    )

    assert blast.changed_item == {"type": "skill", "id": "search_knowledge_base"}
    assert "search_knowledge_base" in blast.impacted_skills
    assert {"support_triage", "rfp_answer_pack"} <= set(blast.impacted_workflows)
    assert {"support_reply", "rfp_answer"} <= set(blast.impacted_prompts)
    assert "resource://policy/ai-governance" in blast.impacted_resources
    assert blast.capacity_impact["forecasted_invocations"] > 0
    assert any(call["tool_name"] == "search_knowledge_base" for call in blast.likely_tool_calls)
    assert any("high_centrality_skill" in flag for flag in blast.risk_flags)
    assert blast.recommended_rollout_action in {
        "review_gate_then_canary_rollout",
        "standard_release_with_targeted_regression",
    }


def test_dependency_blast_radius_unknown_item_warns(tmp_path: Path) -> None:
    state = dependency_state(tmp_path)

    blast = asyncio.run(
        state.dependencies.blast_radius(
            BlastRadiusRequest(prompt_id="missing_prompt", actor="pytest-dependency")
        )
    )

    assert blast.readiness_status == "needs_review"
    assert blast.impacted_skills == []
    assert "unknown_or_excluded_changed_item" in blast.risk_flags
    assert any("not in the active dependency graph" in warning for warning in blast.warnings)
    assert blast.recommended_rollout_action == "block_until_registered_or_promoted"


def test_dependency_report_export_writes_markdown_and_json(tmp_path: Path) -> None:
    state = dependency_state(tmp_path)

    export = asyncio.run(
        state.dependencies.report(
            DependencyReportRequest(
                actor="pytest-dependency",
                scenarios=[
                    BlastRadiusRequest(skill_id="search_knowledge_base"),
                    BlastRadiusRequest(resource_uri="resource://workflow-templates"),
                ],
            )
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["report_id"] == "dependency_report_latest"
    assert len(bundle["scenarios"]) == 2
    assert len(bundle["interviewer_talking_points"]) == 5
    assert "python -m app.mcp_server tools" in bundle["mcp_commands"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Dependency Map and Blast Radius Report" in markdown
    assert "Rollout Checklist" in markdown


def test_dependency_endpoints_return_map_blast_and_report(tmp_path: Path) -> None:
    main_module.state = dependency_state(tmp_path)
    client = TestClient(app)

    dependency_map = client.get("/dependencies/map", headers=HEADERS)
    blast = client.post(
        "/dependencies/blast-radius",
        headers=HEADERS,
        json={"workflow_template_id": "support_triage"},
    )
    report = client.post("/dependencies/report", headers=HEADERS)

    assert dependency_map.status_code == 200
    assert dependency_map.json()["nodes"]
    assert dependency_map.json()["edges"]
    assert blast.status_code == 200
    assert "support_triage" in blast.json()["impacted_workflows"]
    assert report.status_code == 200
    assert Path(report.json()["json_path"]).exists()
    assert Path(report.json()["markdown_path"]).exists()


def test_dependency_map_excludes_disabled_and_draft_skills(tmp_path: Path) -> None:
    state = dependency_state(tmp_path)
    state.registry.set_status("translate_text", False, "pytest")
    state.registry.register(draft_manifest(), "pytest")

    dependency_map = asyncio.run(state.dependencies.build_map())

    node_ids = {node.id for node in dependency_map.nodes}
    assert "skill:translate_text" not in node_ids
    assert "tool:translate_text" not in node_ids
    assert "skill:draft_dependency_candidate" not in node_ids
    assert "translate_text" in {
        skill["id"] for skill in dependency_map.excluded_skills["disabled"]
    }
    assert "draft_dependency_candidate" in {
        skill["id"] for skill in dependency_map.excluded_skills["draft"]
    }
