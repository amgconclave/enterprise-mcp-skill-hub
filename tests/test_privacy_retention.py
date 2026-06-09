from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import PrivacyRedactionRequest, PrivacyRetentionPackRequest
from app.services import PrivacyRetentionService

HEADERS = {"X-API-Key": "dev-local-token"}


def privacy_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.privacy_retention = PrivacyRetentionService(
            state,
            output_dir=tmp_path / "privacy_packs",
        )
    return state


def test_privacy_retention_report_scans_fixture_and_returns_redacted_preview() -> None:
    state = privacy_state()

    report = state.privacy_retention.report(actor="pytest-privacy-reviewer")
    fixture = next(record for record in report.records if record.source_id == "privacy_red_team_fixture")

    assert report.summary["source_count"] >= 1
    assert report.summary["finding_count"] >= 5
    assert report.readiness_status == "blocked"
    assert fixture.max_severity == "critical"
    assert {"email", "ssn", "health_context", "credential_like"} <= set(fixture.categories)
    assert fixture.redacted_preview["email"] == "[REDACTED_EMAIL]"
    assert fixture.redacted_preview["ssn"] == "[REDACTED_SSN]"
    assert report.deletion_candidates
    assert any(event.action == "privacy_retention.report_run" for event in state.audit.events)


def test_privacy_redaction_masks_ad_hoc_json_payload() -> None:
    state = privacy_state()

    result = state.privacy_retention.redact(
        PrivacyRedactionRequest(
            source_id="pytest_payload",
            payload={
                "requester": "Priya Shah",
                "email": "priya.shah@atlas.example",
                "notes": "Patient diagnosis requires treatment follow-up.",
            },
            actor="pytest-privacy-reviewer",
        )
    )

    assert result.readiness_status == "needs_review"
    assert result.redacted_payload["requester"] == "[REDACTED_PERSON]"
    assert result.redacted_payload["email"] == "[REDACTED_EMAIL]"
    assert "[REDACTED_HEALTH_CONTEXT]" in result.redacted_payload["notes"]
    assert {"sample_person_name", "email", "health_context"} <= set(result.summary["categories"])
    assert any(event.action == "privacy_retention.content_redacted" for event in state.audit.events)


def test_privacy_retention_pack_exports_reviewer_artifacts(tmp_path: Path) -> None:
    state = privacy_state(tmp_path)

    export = state.privacy_retention.pack(
        PrivacyRetentionPackRequest(actor="pytest-privacy-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "privacy_retention_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    serialized = json.dumps(bundle)
    assert bundle["summary"]["audit_event_count"] >= 1
    assert "retention_policy" in bundle
    assert "priya.shah@atlas.example" not in serialized
    assert "123-45-6789" not in serialized
    assert "Privacy Retention + Redaction Pack" in markdown
    assert "High-Risk Findings" in markdown


def test_privacy_retention_endpoints_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = privacy_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/privacy/retention-report", headers=HEADERS)
    redaction = client.post(
        "/privacy/redact",
        json={
            "source_id": "api_payload",
            "payload": {"email": "priya.shah@atlas.example", "notes": "Patient diagnosis"},
            "actor": "pytest-privacy-reviewer",
        },
        headers=HEADERS,
    )
    export = client.post(
        "/privacy/retention-pack",
        json={"actor": "pytest-privacy-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()
    matrix = state.smoke._endpoint_matrix()

    assert report.status_code == 200
    assert report.json()["summary"]["finding_count"] >= 1
    assert redaction.status_code == 200
    assert redaction.json()["redacted_payload"]["email"] == "[REDACTED_EMAIL]"
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Privacy Retention" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/privacy/retention-report" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/privacy_packs/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/privacy_packs" for item in inventory.items)
    assert any(item["path"] == "/privacy/retention-report" for item in api_contract.docs_api_coverage)
    assert any(endpoint.path == "/privacy/retention-report" for endpoint in matrix)
