from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import McpToolAdmissionPackRequest

HEADERS = {"X-API-Key": "dev-local-token"}


def test_mcp_admission_report_uses_sandbox_and_step_verification() -> None:
    state = create_state()

    report = asyncio.run(state.mcp_admission.report())

    assert report.summary["tool_count"] == len(state.registry.list())
    assert report.summary["mcp_exposed_tool_count"] == 6
    assert report.summary["admitted_tool_count"] >= 1
    assert "task sandbox" in report.architecture_patterns
    assert "state observation" in report.architecture_patterns
    assert "step verification" in report.architecture_patterns
    assert any(record.skill_id == "search_knowledge_base" for record in report.records)
    retrieval_record = next(record for record in report.records if record.skill_id == "search_knowledge_base")
    assert retrieval_record.sandbox_decision.decision == "allow"
    assert retrieval_record.risk_label == "medium"
    assert "context_boundary_review" in retrieval_record.risk_flags
    assert any(step["step"] == "Evaluate MCP sandbox preflight" for step in retrieval_record.step_verifications)
    assert any(observation["signal"] == "sandbox_preflight" for observation in retrieval_record.state_observations)


def test_mcp_admission_endpoints_pack_dashboard_inventory_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.mcp_admission.output_dir = tmp_path / "mcp_admission"
    state.artifacts.output_dir = tmp_path / "artifact_indexes"
    main_module.state = state
    client = TestClient(app)

    report_response = client.get("/mcp/admission", headers=HEADERS)
    pack_response = client.post(
        "/mcp/admission-pack",
        headers=HEADERS,
        json={"actor": "pytest-mcp-admission-reviewer"},
    )
    pack = asyncio.run(state.mcp_admission.pack(McpToolAdmissionPackRequest(actor="pytest-reviewer")))
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report_response.status_code == 200
    assert report_response.json()["summary"]["tool_count"] == 6
    assert report_response.json()["summary"]["advisory_only"] is True
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    bundle = json.loads(Path(pack.json_path).read_text(encoding="utf-8"))
    assert bundle["summary"]["tool_count"] == 6
    assert bundle["architecture_patterns"]
    assert any(view["label"] == "MCP Admission" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/mcp/admission" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/mcp_admission/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/mcp_admission" for item in inventory.items)
    assert any(item["path"] == "/mcp/admission" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /mcp/admission-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
