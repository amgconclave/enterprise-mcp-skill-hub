from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import CircuitBreakerActionRequest, SkillReliabilityPackRequest
from app.services import SkillReliabilityService

HEADERS = {"X-API-Key": "dev-local-token"}


def reliability_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.reliability = SkillReliabilityService(state, output_dir=tmp_path / "reliability_packs")
        state.invocation_service.reliability = state.reliability
    return state


def test_reliability_report_tracks_skill_failures_latency_and_recommendations() -> None:
    state = reliability_state()

    report = state.reliability.report()
    by_skill = {skill.skill_id: skill for skill in report.skills}

    assert report.summary["skill_count"] == len(state.registry.list())
    assert by_skill["search_knowledge_base"].failure_count >= 2
    assert by_skill["search_knowledge_base"].p95_latency_ms > report.summary["latency_slo_ms"]
    assert by_skill["translate_text"].recommended_action == "keep_enabled"
    assert report.disable_recommendations
    assert report.re_enable_recommendations
    assert any("python -m pytest -q" in command for command in report.local_proof_commands)


def test_circuit_breaker_auto_opens_after_consecutive_skill_failures() -> None:
    state = reliability_state()

    for _ in range(3):
        invocation = asyncio.run(
            state.invocation_service.invoke("classify_request", {}, "pytest-agent")
        )
        assert invocation.status == "failed"

    report = state.reliability.report()
    classify = next(skill for skill in report.skills if skill.skill_id == "classify_request")
    assert classify.circuit_state == "open"
    assert classify.consecutive_failures == 3

    blocked = asyncio.run(
        state.invocation_service.invoke(
            "classify_request",
            {"request": "route this request"},
            "pytest-agent",
        )
    )

    assert blocked.status == "failed"
    assert blocked.error and blocked.error.startswith("Circuit breaker open")
    assert any(event.action == "reliability.circuit_opened" for event in state.audit.events)
    assert any(event.action == "reliability.circuit_breaker_blocked" for event in state.audit.events)


def test_manual_breaker_action_and_reliability_pack_export(tmp_path: Path) -> None:
    state = reliability_state(tmp_path)

    updated = state.reliability.set_breaker(
        "search_knowledge_base",
        CircuitBreakerActionRequest(
            action="half_open",
            actor="pytest-sre",
            reason="canary after retrieval fix",
        ),
    )
    export = state.reliability.pack(
        SkillReliabilityPackRequest(actor="pytest-sre")
    )

    assert updated.circuit_state == "half_open"
    assert export.pack_id == "reliability_pack_latest"
    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "circuit_breaker_policy" in bundle
    assert "reviewer_checklist" in bundle
    assert "Skill Reliability + Circuit Breaker Pack" in markdown
    assert "Circuit Breaker Policy" in markdown


def test_reliability_endpoints_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = reliability_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/reliability/skills", headers=HEADERS)
    breaker = client.patch(
        "/reliability/circuit-breakers/search_knowledge_base",
        json={"action": "half_open", "actor": "pytest-sre", "reason": "canary"},
        headers=HEADERS,
    )
    export = client.post(
        "/reliability/pack",
        json={"actor": "pytest-sre"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()
    matrix = asyncio.run(state.smoke.smoke_matrix())

    assert report.status_code == 200
    assert report.json()["summary"]["skill_count"] == len(state.registry.list())
    assert breaker.status_code == 200
    assert breaker.json()["circuit_state"] == "half_open"
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Skill Reliability" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/reliability/skills" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/reliability_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/reliability_packs" for item in inventory.items)
    assert any(item["path"] == "/reliability/skills" for item in api_contract.docs_api_coverage)
    assert any(endpoint.path == "/reliability/skills" for endpoint in matrix.endpoint_matrix)
