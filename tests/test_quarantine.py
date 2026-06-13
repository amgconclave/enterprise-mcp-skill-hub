from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import SkillQuarantineApplyRequest, SkillQuarantinePackRequest

HEADERS = {"X-API-Key": "dev-local-token"}


def test_quarantine_report_aggregates_runtime_kill_switch_evidence() -> None:
    state = create_state()

    report = state.quarantine.report(actor="pytest-platform-sre")

    assert report.report_id == "skill_quarantine_report_latest"
    assert report.readiness_status in {"blocked", "needs_review", "ready"}
    assert {"governance", "human-in-the-loop", "tool governance", "provider flexibility"} <= set(
        report.architecture_patterns
    )
    by_skill = {record.skill_id: record for record in report.decisions}
    assert by_skill["search_knowledge_base"].decision == "quarantine_recommended"
    assert by_skill["search_knowledge_base"].requires_human_review
    assert "slo_release_gate_block" in by_skill["search_knowledge_base"].trigger_sources
    assert report.kill_switch_plan
    assert any(item["skill_id"] == "search_knowledge_base" for item in report.human_review_queue)
    assert report.summary["quarantine_recommended_count"] >= 1


def test_quarantine_pack_export_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.quarantine.output_dir = tmp_path / "quarantine_packs"

    export = state.quarantine.pack(SkillQuarantinePackRequest(actor="pytest-platform-sre"))

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "skill_quarantine_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "quarantine_report" in bundle
    assert "kill_switch_plan" in bundle
    assert "Runtime Skill Quarantine Pack" in markdown
    assert any(event.action == "quarantine.pack_exported" for event in state.audit.events)


def test_quarantine_apply_disables_only_recommended_skills() -> None:
    state = create_state()

    result = state.quarantine.apply(
        SkillQuarantineApplyRequest(
            actor="pytest-platform-sre",
            skill_ids=["search_knowledge_base", "summarize_document"],
            reason="pytest kill-switch drill",
        )
    )

    assert result.applied_skill_ids == ["search_knowledge_base"]
    assert result.skipped_skill_ids == ["summarize_document"]
    disabled = state.registry.get("search_knowledge_base")
    assert disabled.enabled is False
    assert disabled.status == "disabled"
    assert any(event.action == "quarantine.skill_disabled" for event in state.audit.events)


def test_quarantine_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.quarantine.output_dir = tmp_path / "quarantine_packs"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/quarantine/report", headers=HEADERS)
    export = client.post(
        "/quarantine/pack",
        json={"actor": "pytest-platform-sre"},
        headers=HEADERS,
    )
    apply = client.post(
        "/quarantine/apply",
        json={
            "actor": "pytest-platform-sre",
            "skill_ids": ["search_knowledge_base"],
            "reason": "pytest API kill-switch drill",
        },
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["quarantine_recommended_count"] >= 1
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert apply.status_code == 200
    assert apply.json()["applied_skill_ids"] == ["search_knowledge_base"]
    assert any(view["label"] == "Skill Quarantine" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/quarantine/report" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/quarantine_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/quarantine_packs" for item in inventory.items)
    assert any(item["path"] == "/quarantine/report" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /quarantine/pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
