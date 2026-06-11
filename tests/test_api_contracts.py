from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.api_contracts import ApiContractService
from app.bootstrap import create_state
from app.main import app
from app.models import (
    ApiContractDriftPackRequest,
    ApiContractRemediationPackRequest,
    ApiContractRemediationRunRequest,
    ApiReviewerCollectionRequest,
)

HEADERS = {"X-API-Key": "dev-local-token"}


def contract_state(tmp_path: Path):
    state = create_state()
    state.api_contracts = ApiContractService(state, output_dir=tmp_path / "api_contracts")
    return state


def test_api_contract_audit_returns_structured_contract_checks(tmp_path: Path) -> None:
    state = contract_state(tmp_path)

    audit = state.api_contracts.contract_audit()

    check_ids = {check.id for check in audit.checks}
    assert audit.audit_id == "api_contract_audit_latest"
    assert audit.openapi_route_count >= 50
    assert audit.auth_protected_endpoint_count >= 40
    assert {
        "openapi_route_count",
        "auth_protected_endpoint_count",
        "important_endpoint_docs_api_coverage",
        "dashboard_smoke_alignment",
        "generated_artifact_endpoint_coverage",
        "demo_flow_endpoint_coverage",
        "mcp_tools_resources_prompts_coverage",
        "tool_contract_drift",
        "missing_docs_warnings",
        "deprecated_duplicate_route_warnings",
        "local_only_limitations",
    } <= check_ids
    assert "api contract" in audit.endpoint_inventory_by_domain
    assert any(item["path"] == "/api/contract-audit" for item in audit.docs_api_coverage)
    assert audit.dashboard_smoke_alignment["aligned"]
    assert any(
        item["producer_endpoint"] == "POST /api/reviewer-collection"
        for item in audit.generated_artifact_endpoint_coverage
    )
    assert any(item["path"] == "/api/reviewer-collection" for item in audit.demo_flow_endpoint_coverage)
    assert audit.mcp_inventory["tool_count"] == 6
    assert audit.mcp_inventory["resource_count"] >= 1
    assert audit.mcp_inventory["prompt_count"] >= 1
    assert audit.contract_drift["status"] == "aligned"
    assert audit.contract_drift["drift_count"] == 0
    assert audit.contract_drift["aligned_count"] == 6
    assert audit.contract_drift["fastapi_contract"]["status"] == "aligned"
    assert all(
        item["manifest_input_schema_hash"] == item["mcp_input_schema_hash"]
        for item in audit.contract_drift["mcp_manifest_matrix"]
    )
    assert any("tool registry" in pattern for pattern in audit.contract_drift["governance_patterns"])
    assert any("api/reviewer-collection" in command for command in audit.verification_commands)
    assert any("api/contract-drift-pack" in command for command in audit.verification_commands)
    assert any("api/contract-remediation-pack" in command for command in audit.verification_commands)


def test_reviewer_collection_writes_markdown_and_json(tmp_path: Path) -> None:
    state = contract_state(tmp_path)

    export = state.api_contracts.reviewer_collection(
        ApiReviewerCollectionRequest(actor="pytest-api-contract-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.collection_id == "reviewer_collection_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "contract_audit" in bundle
    assert "endpoint_inventory_grouped_by_domain" in bundle
    assert "mcp_inventory" in bundle
    assert "contract_drift" in bundle
    assert "sample_commands" in bundle
    assert "demo_token_flow" in bundle
    assert "mcp_cli_commands" in bundle
    assert "expected_status_codes" in bundle
    assert "auth_notes" in bundle
    assert "generated_artifact_endpoints" in bundle
    assert "one_command_verification_order" in bundle
    assert "recruiter_engineer_explanation" in bundle
    assert "API Contract Reviewer Collection" in markdown
    assert "OpenAPI route count" in markdown
    assert "X-API-Key" in markdown


def test_contract_drift_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = contract_state(tmp_path)

    export = state.api_contracts.contract_drift_pack(
        ApiContractDriftPackRequest(actor="pytest-contract-drift-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "contract_drift_pack_latest"
    assert export.summary["contract_drift_status"] == "aligned"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "contract_drift" in bundle
    assert "fastapi_contract" in bundle
    assert "mcp_manifest_matrix" in bundle
    assert "remediation_plan" in bundle
    assert "governance_patterns" in bundle
    assert len(bundle["mcp_manifest_matrix"]) == 6
    assert all(item["status"] == "aligned" for item in bundle["mcp_manifest_matrix"])
    assert "Tool Contract Drift Pack" in markdown
    assert "MCP Manifest Matrix" in markdown


def test_contract_remediation_run_is_bounded_and_read_only(tmp_path: Path) -> None:
    state = contract_state(tmp_path)

    run = state.api_contracts.remediation_run(
        ApiContractRemediationRunRequest(actor="pytest-contract-remediation-reviewer", max_steps=4)
    )

    assert run.run_id == "contract_remediation_run_latest"
    assert run.readiness_status in {"ready", "needs_review"}
    assert len(run.bounded_steps) == 4
    assert run.observations["contract_drift_status"] == "aligned"
    assert run.observations["drift_count"] == 0
    assert "state observation" in run.patterns_used
    assert "bounded action loop" in run.patterns_used
    assert "step verification" in run.patterns_used
    assert "task sandbox" in run.patterns_used
    assert run.artifacts == {}
    assert any("contract-remediation-run" in command for command in run.verification_commands)


def test_contract_remediation_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = contract_state(tmp_path)

    export = state.api_contracts.remediation_pack(
        ApiContractRemediationPackRequest(actor="pytest-contract-remediation-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "contract_remediation_pack_latest"
    assert export.summary["step_count"] >= 6
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "remediation_run" in bundle
    assert "observations" in bundle
    assert "bounded_steps" in bundle
    assert "remediation_backlog" in bundle
    assert "Contract Remediation Run Pack" in markdown
    assert "Bounded Action Loop" in markdown


def test_api_contract_endpoints_return_audit_and_collection(tmp_path: Path) -> None:
    main_module.state = contract_state(tmp_path)
    client = TestClient(app)

    audit = client.get("/api/contract-audit", headers=HEADERS)
    export = client.post(
        "/api/reviewer-collection",
        json={"actor": "pytest-api-contract-reviewer"},
        headers=HEADERS,
    )
    drift_pack = client.post(
        "/api/contract-drift-pack",
        json={"actor": "pytest-contract-drift-reviewer"},
        headers=HEADERS,
    )
    remediation_run = client.get("/api/contract-remediation-run", headers=HEADERS)
    remediation_pack = client.post(
        "/api/contract-remediation-pack",
        json={"actor": "pytest-contract-remediation-reviewer"},
        headers=HEADERS,
    )

    assert audit.status_code == 200
    assert audit.json()["audit_id"] == "api_contract_audit_latest"
    assert audit.json()["openapi_route_count"] >= 50
    assert audit.json()["contract_drift"]["status"] == "aligned"
    assert export.status_code == 200
    assert export.json()["collection_id"] == "reviewer_collection_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
    assert drift_pack.status_code == 200
    assert drift_pack.json()["pack_id"] == "contract_drift_pack_latest"
    assert Path(drift_pack.json()["json_path"]).exists()
    assert Path(drift_pack.json()["markdown_path"]).exists()
    assert remediation_run.status_code == 200
    assert remediation_run.json()["run_id"] == "contract_remediation_run_latest"
    assert remediation_run.json()["observations"]["contract_drift_status"] == "aligned"
    assert remediation_pack.status_code == 200
    assert remediation_pack.json()["pack_id"] == "contract_remediation_pack_latest"
    assert Path(remediation_pack.json()["json_path"]).exists()
    assert Path(remediation_pack.json()["markdown_path"]).exists()


def test_contract_drift_is_wired_to_dashboard_and_artifact_inventory(tmp_path: Path) -> None:
    state = contract_state(tmp_path)

    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    audit = state.api_contracts.contract_audit()

    assert any(endpoint["path"] == "/api/contract-drift-pack" for endpoint in smoke.endpoint_references)
    assert any(endpoint["path"] == "/api/contract-remediation-run" for endpoint in smoke.endpoint_references)
    assert any(endpoint["path"] == "/api/contract-remediation-pack" for endpoint in smoke.endpoint_references)
    assert any(
        item.producer_endpoint == "POST /api/contract-drift-pack"
        for item in inventory.items
    )
    assert any(
        item.producer_endpoint == "POST /api/contract-remediation-pack"
        for item in inventory.items
    )
    assert any(
        item["producer_endpoint"] == "POST /api/contract-drift-pack"
        for item in audit.generated_artifact_endpoint_coverage
    )
    assert any(
        item["producer_endpoint"] == "POST /api/contract-remediation-pack"
        for item in audit.generated_artifact_endpoint_coverage
    )
