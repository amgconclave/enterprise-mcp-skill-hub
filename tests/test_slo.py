from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import SkillSloPackRequest
from app.services import SkillSloService

HEADERS = {"X-API-Key": "dev-local-token"}


def slo_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.slo = SkillSloService(state, output_dir=tmp_path / "slo_packs")
    return state


def test_slo_report_derives_error_budget_and_release_gates() -> None:
    state = slo_state()

    report = state.slo.report()
    by_skill = {skill.skill_id: skill for skill in report.skills}

    assert report.summary["skill_count"] == len(state.registry.list())
    assert report.objectives["default_local_skill_slo"]["availability_slo_pct"] == 99.0
    assert by_skill["search_knowledge_base"].error_budget_status == "breached"
    assert by_skill["search_knowledge_base"].release_gate == "block_release"
    assert by_skill["translate_text"].release_gate == "needs_review"
    assert report.release_gate["blocking_skill_ids"]
    assert any("python -m app.evals.run_conformance" in command for command in report.local_proof_commands)


def test_slo_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = slo_state(tmp_path)

    export = state.slo.pack(SkillSloPackRequest(actor="pytest-slo-reviewer"))

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "slo_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "slo_report" in bundle
    assert "release_gate" in bundle
    assert "reviewer_checklist" in bundle
    assert "Skill SLO + Error Budget Pack" in markdown
    assert "Release Gate" in markdown


def test_slo_endpoints_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = slo_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/slo/report", headers=HEADERS)
    export = client.post(
        "/slo/pack",
        json={"actor": "pytest-slo-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()
    matrix = asyncio.run(state.smoke.smoke_matrix())

    assert report.status_code == 200
    assert report.json()["release_gate"]["blocking_skill_ids"]
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Skill SLO" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/slo/report" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/slo_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/slo_packs" for item in inventory.items)
    assert any(item["path"] == "/slo/report" for item in api_contract.docs_api_coverage)
    assert any(endpoint.path == "/slo/report" for endpoint in matrix.endpoint_matrix)
