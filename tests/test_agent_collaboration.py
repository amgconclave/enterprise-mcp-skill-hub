from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import AgentCollaborationPackRequest, AgentCollaborationRequest

HEADERS = {"X-API-Key": "dev-local-token"}


async def test_agent_collaboration_runs_shared_state_handoffs_and_cost_tracking() -> None:
    state = create_state()

    run = await state.agent_collaboration.run(
        AgentCollaborationRequest(
            prompt=(
                "Classify the RFP, search approved AI governance policy, summarize the answer, "
                "and create action items for Priya Shah."
            ),
            actor="pytest-agent-platform",
        )
    )

    assert run.readiness_status == "ready"
    assert len(run.turns) == 4
    assert [turn.skill_id for turn in run.turns] == [
        "classify_request",
        "search_knowledge_base",
        "summarize_document",
        "generate_action_items",
    ]
    assert all(turn.status == "succeeded" for turn in run.turns)
    assert all(turn.handoff.approved for turn in run.turns)
    assert {"multi-agent conversation", "shared state", "handoffs"} <= set(
        run.governance_summary["architecture_patterns"]
    )
    assert "classify_request" in run.shared_state["artifacts"]
    assert run.token_usage.input_tokens > 0
    assert run.estimated_cost == 0.0
    assert any(event.action == "agents.collaboration_run" for event in state.audit.events)


async def test_agent_collaboration_blocks_policy_denied_handoff_before_tool_execution() -> None:
    state = create_state()

    run = await state.agent_collaboration.run(
        AgentCollaborationRequest(
            prompt="Classify confidential RFP material and search approved governance policy.",
            actor="pytest-agent-platform",
            role="agent",
            data_sensitivity="confidential",
            enforce_policy=True,
        )
    )

    assert run.readiness_status == "needs_review"
    assert len(run.turns) == 1
    assert run.turns[0].status == "failed"
    assert run.turns[0].policy_decision is not None
    assert run.turns[0].policy_decision.decision == "deny"
    assert run.shared_state["artifacts"] == {}


async def test_agent_collaboration_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.agent_collaboration.output_dir = tmp_path / "agent_collaboration"

    export = await state.agent_collaboration.export(
        AgentCollaborationPackRequest(actor="pytest-agent-platform")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "agent_collaboration_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "collaboration_run" in bundle
    assert "multi-agent conversation" in bundle["architecture_patterns"]
    assert "Agent Collaboration Pack" in markdown
    assert any(event.action == "agents.collaboration_pack_exported" for event in state.audit.events)


def test_agent_collaboration_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    original_state = main_module.state
    state = create_state()
    state.agent_collaboration.output_dir = tmp_path / "agent_collaboration"
    main_module.state = state
    client = TestClient(app)

    try:
        run_response = client.post(
            "/agents/collaborate",
            headers=HEADERS,
            json={
                "prompt": "Classify the request, search policy, summarize it, and create action items.",
                "actor": "pytest-agent-platform",
            },
        )
        pack_response = client.post(
            "/agents/collaboration-pack",
            headers=HEADERS,
            json={"actor": "pytest-agent-platform"},
        )
        smoke = state.ui_verification.dashboard_smoke()
        inventory = state.artifacts.inventory()
        api_contract = state.api_contracts.contract_audit()
    finally:
        main_module.state = original_state

    assert run_response.status_code == 200
    assert run_response.json()["governance_summary"]["handoff_count"] >= 3
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Agent Collaboration" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/agents/collaborate" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/agent_collaboration/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/agent_collaboration" for item in inventory.items)
    assert any(item["path"] == "/agents/collaborate" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /agents/collaboration-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
