from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import (
    SandboxExceptionSubmitRequest,
    TaskRunTransparencyPackRequest,
    WorkerSkillRunRequest,
)

HEADERS = {"X-API-Key": "dev-local-token"}


async def test_task_run_ledger_normalizes_transparent_runtime_evidence() -> None:
    state = create_state()

    await state.invocation_service.invoke(
        "summarize_document",
        {"text": "Atlas Labs needs a governed summary and audit trace."},
        "pytest-runner",
    )
    await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="search_knowledge_base",
            input={"query": "AI governance policy", "limit": 2},
            actor="pytest-worker",
            worker_pool="retrieval_heavy",
            enforce_sandbox=True,
        )
    )
    state.sandbox_exceptions.submit(
        SandboxExceptionSubmitRequest(
            skill_id="extract_entities",
            input={"text": "Attempt to write a local file."},
            requested_by="pytest-security",
            action_class="filesystem_write",
        )
    )

    ledger = state.task_runs.ledger()
    run_types = {entry.run_type for entry in ledger.ledger}

    assert {"skill_invocation", "worker_run", "sandbox_decision", "sandbox_exception"} <= run_types
    assert "run transparency" in ledger.patterns_used
    assert "state observation" in ledger.patterns_used
    assert "bounded action loop" in ledger.patterns_used
    assert ledger.observations["trace_id_count"] >= 3
    assert any(entry.replay_commands for entry in ledger.ledger)
    assert any(step["pattern"] == "step verification" for step in ledger.bounded_action_loop)


async def test_task_run_transparency_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.task_runs.output_dir = tmp_path / "run_transparency"

    await state.worker_scaleout.submit_run(
        WorkerSkillRunRequest(
            skill_id="classify_request",
            input={"request": "Need a governed support triage path."},
            actor="pytest-worker",
            worker_pool="governance_review",
            enforce_sandbox=True,
        )
    )
    export = state.task_runs.transparency_pack(
        TaskRunTransparencyPackRequest(actor="pytest-run-transparency-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "task_run_transparency_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    assert "Task Run Transparency Pack" in markdown_path.read_text(encoding="utf-8")
    assert any(event.action == "runs.transparency_pack_exported" for event in state.audit.events)


def test_run_transparency_endpoints_dashboard_artifacts_and_contract(tmp_path: Path) -> None:
    state = create_state()
    state.task_runs.output_dir = tmp_path / "run_transparency"
    main_module.state = state
    client = TestClient(app)

    ledger_response = client.get("/runs/ledger", headers=HEADERS)
    pack_response = client.post(
        "/runs/transparency-pack",
        json={"actor": "pytest-run-transparency-reviewer"},
        headers=HEADERS,
    )
    smoke = state.ui_verification.dashboard_smoke()
    inventory = state.artifacts.inventory()
    api_contract = state.api_contracts.contract_audit()

    assert ledger_response.status_code == 200
    assert ledger_response.json()["summary"]["ledger_entry_count"] >= 1
    assert pack_response.status_code == 200
    assert Path(pack_response.json()["json_path"]).exists()
    assert any(view["label"] == "Run Transparency" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/runs/ledger" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/run_transparency/" for tab in smoke.generated_artifact_tabs)
    assert any(item.directory == "data/run_transparency" for item in inventory.items)
    assert any(item["path"] == "/runs/ledger" for item in api_contract.docs_api_coverage)
    assert any(
        item["producer_endpoint"] == "POST /runs/transparency-pack"
        for item in api_contract.generated_artifact_endpoint_coverage
    )
