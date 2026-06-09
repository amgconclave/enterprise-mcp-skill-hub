from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.api_contracts import ApiContractService
from app.bootstrap import create_state
from app.main import app
from app.models import ApiReviewerCollectionRequest

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
    assert any("api/reviewer-collection" in command for command in audit.verification_commands)


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


def test_api_contract_endpoints_return_audit_and_collection(tmp_path: Path) -> None:
    main_module.state = contract_state(tmp_path)
    client = TestClient(app)

    audit = client.get("/api/contract-audit", headers=HEADERS)
    export = client.post(
        "/api/reviewer-collection",
        json={"actor": "pytest-api-contract-reviewer"},
        headers=HEADERS,
    )

    assert audit.status_code == 200
    assert audit.json()["audit_id"] == "api_contract_audit_latest"
    assert audit.json()["openapi_route_count"] >= 50
    assert export.status_code == 200
    assert export.json()["collection_id"] == "reviewer_collection_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
