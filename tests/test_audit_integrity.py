from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import AuditIntegrityPackRequest
from app.services import AuditIntegrityService

HEADERS = {"X-API-Key": "dev-local-token"}


def integrity_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.audit_integrity = AuditIntegrityService(
            state,
            output_dir=tmp_path / "audit_integrity",
        )
    return state


async def test_audit_integrity_builds_hash_chain_for_audit_and_invocations() -> None:
    state = integrity_state()

    invocation = await state.invocation_service.invoke(
        "summarize_document",
        {"text": "Atlas Labs needs audit-integrity proof for a governed skill run."},
        "pytest-audit-integrity",
    )
    report = state.audit_integrity.report()
    invocation_record = next(record for record in report.records if record.record_id == invocation.id)

    assert report.root_hash == report.records[-1].chain_hash
    assert report.summary["record_count"] == len(report.records)
    assert report.summary["skill_invocation_count"] >= 1
    assert invocation_record.previous_hash
    assert invocation_record.content_hash
    assert invocation_record.chain_hash
    assert invocation_record.verification_status == "valid"
    assert any("durable workflows" in pattern for pattern in report.patterns_used)
    assert any("governance" in pattern for pattern in report.patterns_used)
    assert any("invocations" in command for command in invocation_record.replay_commands)


async def test_audit_integrity_flags_invocation_without_matching_audit_event() -> None:
    state = integrity_state()

    invocation = await state.invocation_service.invoke(
        "classify_request",
        {"request": "Need a governed support triage path."},
        "pytest-audit-integrity",
    )
    state.audit.events = [
        event
        for event in state.audit.events
        if not (event.trace_id == invocation.trace_id and event.action == "skill.invoked")
    ]

    report = state.audit_integrity.report()

    assert report.readiness_status == "needs_review"
    assert any(gap["gap_id"] == f"missing_invocation_audit:{invocation.trace_id}" for gap in report.gaps)
    assert any("missing_invocation_audit" in warning["gap_id"] for warning in report.tamper_warnings)


async def test_audit_integrity_pack_writes_reviewer_artifacts(tmp_path: Path) -> None:
    state = integrity_state(tmp_path)
    await state.invocation_service.invoke(
        "extract_entities",
        {"text": "Priya Shah at Atlas Labs needs integrity pack evidence."},
        "pytest-audit-integrity",
    )

    export = state.audit_integrity.pack(
        AuditIntegrityPackRequest(actor="pytest-audit-integrity-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "audit_integrity_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "audit_integrity_report" in bundle
    assert "chain_policy" in bundle
    assert "reviewer_checklist" in bundle
    assert "Audit Integrity Pack" in markdown
    assert "Hash Chain Policy" in markdown
    assert any(event.action == "audit_integrity.pack_exported" for event in state.audit.events)


def test_audit_integrity_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = integrity_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/audit/integrity", headers=HEADERS)
    export = client.post(
        "/audit/integrity-pack",
        json={"actor": "pytest-audit-integrity-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["record_count"] >= 1
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Audit Integrity" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/audit/integrity" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/audit_integrity/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/audit_integrity" for item in inventory.items)
    assert any(item["path"] == "/audit/integrity" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /audit/integrity-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
