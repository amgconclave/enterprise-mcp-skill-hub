from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    MarketplaceApprovalSubmitRequest,
    ReviewSlaPackRequest,
    SandboxExceptionSubmitRequest,
    WorkflowTemplate,
)

HEADERS = {"X-API-Key": "dev-local-token"}


async def seed_review_queues(state) -> None:
    state.workflows.submit(
        WorkflowTemplate(
            id="sla_support_pack",
            name="SLA Support Pack",
            description="Pending workflow review used to prove review SLA escalation.",
            ordered_skill_ids=["classify_request", "summarize_document"],
            required_role="agent",
            default_sensitivity="internal",
            expected_outputs=["category", "summary"],
        ),
        "pytest-workflow-owner",
    )
    await state.marketplace.submit_approval(
        MarketplaceApprovalSubmitRequest(
            skill_id="summarize_document",
            tenant_scenario_id="internal_ops_local",
            actor="pytest-marketplace-reviewer",
            owner="pytest-platform-owner",
            note="SLA test marketplace approval.",
        )
    )
    state.sandbox_exceptions.submit(
        SandboxExceptionSubmitRequest(
            skill_id="extract_entities",
            input={"text": "Attempt to write a governed local file."},
            requested_by="pytest-security",
            action_class="filesystem_write",
        )
    )


async def test_review_sla_normalizes_and_escalates_all_human_review_queues() -> None:
    state = create_state()
    await seed_review_queues(state)

    report = await state.review_sla.report(
        ReviewSlaPackRequest(
            actor="pytest-review-ops",
            workflow_review_sla_hours=0,
            marketplace_approval_sla_hours=0,
            sandbox_exception_sla_hours=0,
        )
    )

    queues = {item.queue for item in report.items}
    assert {"workflow_review", "marketplace_approval", "sandbox_exception"} <= queues
    assert report.readiness_status == "blocked"
    assert report.summary["breached_count"] >= 3
    assert report.summary["escalation_count"] >= 3
    assert "human-in-the-loop" in report.architecture_patterns
    assert all(item.recommended_action for item in report.items)
    assert any(item.evidence_refs for item in report.items)


async def test_review_sla_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.review_sla.output_dir = tmp_path / "review_sla"
    await seed_review_queues(state)

    export = await state.review_sla.pack(
        ReviewSlaPackRequest(
            actor="pytest-review-ops",
            workflow_review_sla_hours=0,
            marketplace_approval_sla_hours=0,
            sandbox_exception_sla_hours=0,
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "human_review_sla_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert "review_sla" in bundle
    assert "Human Review SLA Pack" in markdown_path.read_text(encoding="utf-8")
    assert any(event.action == "review_sla.pack_exported" for event in state.audit.events)


async def test_review_sla_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.review_sla.output_dir = tmp_path / "review_sla"
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    await seed_review_queues(state)
    main_module.state = state
    client = TestClient(app)

    report = client.get("/reviews/sla", headers=HEADERS)
    export = client.post(
        "/reviews/sla-pack",
        headers=HEADERS,
        json={
            "actor": "pytest-review-ops",
            "workflow_review_sla_hours": 0,
            "marketplace_approval_sla_hours": 0,
            "sandbox_exception_sla_hours": 0,
        },
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["open_item_count"] >= 3
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Review SLA" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/reviews/sla" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/review_sla/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/review_sla" for item in inventory.items)
    assert any(item["path"] == "/reviews/sla" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /reviews/sla-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
