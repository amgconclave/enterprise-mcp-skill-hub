from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state, schema
from app.main import app
from app.models import AuditQueryRequest, ComplianceAttestationRequest, SkillManifest
from app.services import ComplianceAttestationService, ReleaseService

HEADERS = {"X-API-Key": "dev-local-token"}


def test_audit_query_filters_by_action_actor_skill_and_status(tmp_path: Path) -> None:
    state = create_state()
    state.releases = ReleaseService(
        state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )
    invocation = asyncio.run(
        state.invocation_service.invoke(
            "classify_request",
            {"request": "Security review is blocking the RFP."},
            "pytest-auditor",
        )
    )

    result = asyncio.run(
        state.audit_query.query(
            AuditQueryRequest(
                action="skill.invoked",
                actor="pytest-auditor",
                skill_id="classify_request",
                status="succeeded",
            )
        )
    )

    assert result.matched_events
    assert result.counts_by_action["skill.invoked"] == 1
    assert invocation.id in {item.id for item in result.related_invocations}
    assert invocation.trace_id in result.trace_ids


def test_audit_query_warns_on_empty_missing_evidence(tmp_path: Path) -> None:
    state = create_state()
    state.audit.events.clear()
    state.invocation_service.invocations.clear()
    state.releases = ReleaseService(
        state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )

    result = asyncio.run(
        state.audit_query.query(AuditQueryRequest(action="missing.action", query="not-present"))
    )

    assert result.matched_events == []
    assert any("No audit events" in warning for warning in result.warnings)
    assert any("No skill invocation history" in warning for warning in result.warnings)
    assert any("No evidence matched" in warning for warning in result.warnings)
    assert any("generated preview evidence" in warning for warning in result.warnings)


def test_compliance_attestation_export_writes_json_markdown(tmp_path: Path) -> None:
    state = create_state()
    state.releases = ReleaseService(
        state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )
    state.attestations = ComplianceAttestationService(state, tmp_path / "attestations")

    export = asyncio.run(
        state.attestations.export(ComplianceAttestationRequest(actor="pytest-compliance"))
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["summary"]["promoted_skill_count"] == 6
    assert len(bundle["interviewer_talking_points"]) == 5
    assert "python -m app.mcp_server tools" in bundle["local_verification_commands"]
    assert bundle["mcp_tools"]
    assert "Compliance Attestation Pack" in markdown_path.read_text(encoding="utf-8")


def test_audit_query_and_attestation_endpoints(tmp_path: Path) -> None:
    main_module.state = create_state()
    main_module.state.releases = ReleaseService(
        main_module.state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )
    main_module.state.attestations = ComplianceAttestationService(
        main_module.state,
        tmp_path / "attestations",
    )
    client = TestClient(app)

    query = client.post(
        "/audit/query",
        headers=HEADERS,
        json={"action": "skill.registered", "type": "skill", "limit": 25},
    )
    attestation = client.post(
        "/compliance/attestation",
        headers=HEADERS,
        json={"actor": "pytest-compliance"},
    )

    assert query.status_code == 200
    assert query.json()["matched_events"]
    assert query.json()["counts_by_action"]["skill.registered"] >= 6
    assert attestation.status_code == 200
    assert Path(attestation.json()["json_path"]).exists()
    assert Path(attestation.json()["markdown_path"]).exists()


def test_disabled_and_draft_skills_are_attestation_exclusions(tmp_path: Path) -> None:
    state = create_state()
    state.registry.set_status("translate_text", False, "pytest")
    draft = SkillManifest(
        id="draft_attestation_candidate",
        name="Draft Attestation Candidate",
        version="1.0.0",
        description="Draft skill that should not be attested as a promoted capability.",
        provider="mock",
        enabled=True,
        status="draft",
        tags=["attestation"],
        input_schema=schema({"text": {"type": "string"}}, ["text"]),
        output_schema=schema({"summary": {"type": "string"}}, ["summary"]),
    )
    state.registry.register(draft, "pytest")
    state.releases = ReleaseService(
        state,
        output_dir=tmp_path / "releases",
        snapshot_path=tmp_path / "releases" / "current_snapshot.json",
    )
    state.attestations = ComplianceAttestationService(state, tmp_path / "attestations")

    export = asyncio.run(
        state.attestations.export(ComplianceAttestationRequest(actor="pytest-compliance"))
    )
    bundle = json.loads(Path(export.json_path).read_text(encoding="utf-8"))

    promoted_ids = {skill["id"] for skill in bundle["enabled_promoted_skills"]}
    disabled_ids = {skill["id"] for skill in bundle["exclusions"]["disabled"]}
    draft_ids = {skill["id"] for skill in bundle["exclusions"]["draft"]}
    assert "translate_text" not in promoted_ids
    assert "draft_attestation_candidate" not in promoted_ids
    assert "translate_text" in disabled_ids
    assert "draft_attestation_candidate" in draft_ids
