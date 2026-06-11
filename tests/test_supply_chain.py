from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import SupplyChainPackRequest
from app.services import SupplyChainGovernanceService

HEADERS = {"X-API-Key": "dev-local-token"}


def supply_chain_state(tmp_path: Path | None = None):
    state = create_state()
    if tmp_path:
        state.supply_chain = SupplyChainGovernanceService(
            state,
            output_dir=tmp_path / "supply_chain",
        )
    return state


def test_supply_chain_report_builds_local_sbom_and_policy_decisions() -> None:
    state = supply_chain_state()

    report = state.supply_chain.report(actor="pytest-supply-chain-reviewer")
    package_names = {package.name for package in report.packages}
    check_ids = {check["id"] for check in report.policy_checks}

    assert report.report_id == "supply_chain_report_latest"
    assert report.readiness_status in {"ready", "needs_review", "blocked"}
    assert report.summary["package_count"] >= 10
    assert report.summary["manifest_count"] >= 3
    assert "fastapi" in package_names
    assert "zod-to-json-schema" in package_names
    assert "manifest_presence" in check_ids
    assert "license_policy" in check_ids
    assert "pinning_policy" in check_ids
    assert "external_provider_dependencies" in check_ids
    assert report.license_policy["blocked_licenses"]
    assert any(package.approval_required for package in report.packages)
    assert any(event.action == "supply_chain.report_generated" for event in state.audit.events)


def test_supply_chain_pack_exports_markdown_json_and_audit_evidence(tmp_path: Path) -> None:
    state = supply_chain_state(tmp_path)

    export = state.supply_chain.pack(
        SupplyChainPackRequest(actor="pytest-supply-chain-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "supply_chain_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "report" in bundle
    assert "license_policy" in bundle
    assert "approval_gates" in bundle
    assert "local_verification_commands" in bundle
    assert "Supply Chain SBOM + License Governance Pack" in markdown
    assert "Approval Gates" in markdown
    assert any(
        event.action == "supply_chain.pack_exported"
        and event.resource_id == "supply_chain_pack_latest"
        for event in state.audit.events
    )


def test_supply_chain_endpoints_dashboard_artifacts_and_api_contract(tmp_path: Path) -> None:
    state = supply_chain_state(tmp_path)
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/supply-chain/report", headers=HEADERS)
    export = client.post(
        "/supply-chain/pack",
        json={"actor": "pytest-supply-chain-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["report_id"] == "supply_chain_report_latest"
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Supply Chain" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/supply-chain/report" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/supply_chain/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/supply_chain" for item in inventory.items)
    assert any(item["path"] == "/supply-chain/report" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /supply-chain/pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
