from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import PlatformOperationsDrillRequest

HEADERS = {"X-API-Key": "dev-local-token"}


async def test_platform_operations_drill_aggregates_operator_state() -> None:
    state = create_state()

    drill = await state.platform_operations.drill(
        PlatformOperationsDrillRequest(actor="pytest-platform-operator")
    )

    assert drill.drill_id == "platform_operations_drill_latest"
    assert drill.readiness_status in {"ready", "needs_review", "blocked"}
    assert {
        "task sandbox",
        "run transparency",
        "repository automation",
        "worker scale-out",
        "state observation",
        "bounded action loop",
        "step verification",
    } <= set(drill.architecture_patterns)
    observation_ids = {item["id"] for item in drill.state_observations}
    assert {
        "platform_controls",
        "worker_capacity",
        "queue_admission",
        "run_transparency",
        "sandbox_policy",
        "policy_replay",
        "repository_automation",
    } <= observation_ids
    assert any(step["pattern"] == "bounded action loop" for step in drill.action_loop)
    assert any(step["id"] == "repository_automation" for step in drill.step_verification)


async def test_platform_operations_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.platform_operations.output_dir = tmp_path / "platform_operations"

    export = await state.platform_operations.pack(
        PlatformOperationsDrillRequest(actor="pytest-platform-operator")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "platform_operations_drill_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "platform_operations_drill" in bundle
    assert "State Observations" in markdown
    assert "Bounded Action Loop" in markdown
    assert any(event.action == "platform_operations.drill_pack_exported" for event in state.audit.events)


def test_platform_operations_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.platform_operations.output_dir = tmp_path / "platform_operations"
    main_module.state = state
    client = TestClient(app)

    report = client.get("/platform/operations-drill", headers=HEADERS)
    export = client.post(
        "/platform/operations-pack",
        json={"actor": "pytest-platform-operator"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert report.status_code == 200
    assert report.json()["summary"]["observation_count"] >= 6
    assert export.status_code == 200
    assert Path(export.json()["json_path"]).exists()
    assert any(view["label"] == "Platform Operations" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/platform/operations-drill" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/platform_operations/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/platform_operations" for item in inventory.items)
    assert any(item["path"] == "/platform/operations-drill" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /platform/operations-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
