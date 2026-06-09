from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import RuntimeDemoPackRequest
from app.services import RuntimeDemoService

HEADERS = {"X-API-Key": "dev-local-token"}


def runtime_state(tmp_path: Path):
    state = create_state()
    state.runtime_demo = RuntimeDemoService(state, output_dir=tmp_path / "runtime_packs")
    return state


def test_runtime_demo_readiness_returns_commands_checks_and_mcp_order(tmp_path: Path) -> None:
    state = runtime_state(tmp_path)

    readiness = state.runtime_demo.readiness()

    assert readiness.readiness_id == "runtime_demo_readiness_latest"
    assert readiness.readiness_status in {"ready", "needs_review", "blocked"}
    assert any(command == "python scripts\\runtime_check.py" for command in readiness.local_run_commands)
    assert any(item["command"].startswith("python -m uvicorn") for item in readiness.start_commands)
    assert any(item["service"] == "FastAPI" and item["port"] == 8000 for item in readiness.expected_ports)
    assert any(check["name"] == "FastAPI" and check["status"] == "pass" for check in readiness.dependency_checks)
    assert any(check["service"] == "Streamlit" and "process_check_command" in check for check in readiness.port_checks)
    assert any(item["path"] == "/runtime/demo-readiness" for item in readiness.smoke_urls)
    assert [item["command"] for item in readiness.mcp_verification_commands] == [
        "python -m app.mcp_server tools",
        "python -m app.mcp_server resources",
        "python -m app.mcp_server prompts",
    ]
    assert readiness.summary["local_only"] is True
    assert readiness.summary["mcp_tool_count"] == 6


def test_runtime_demo_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = runtime_state(tmp_path)

    export = state.runtime_demo.demo_pack(RuntimeDemoPackRequest(actor="pytest-runtime-reviewer"))

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "runtime_demo_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert bundle["pack_id"] == "runtime_demo_pack_latest"
    assert "runtime_readiness" in bundle
    assert "mcp_cli_verification_order" in bundle
    assert "screenshot_checklist_placeholders" in bundle
    assert "recruiter_explanation" in bundle
    assert "engineer_explanation" in bundle
    assert "Runtime Demo Server Pack" in markdown
    assert "MCP CLI Verification Order" in markdown
    assert "Manual Stop Commands" in markdown


def test_runtime_demo_endpoints_return_readiness_and_pack(tmp_path: Path) -> None:
    main_module.state = runtime_state(tmp_path)
    client = TestClient(app)

    readiness = client.get("/runtime/demo-readiness", headers=HEADERS)
    export = client.post(
        "/runtime/demo-pack",
        json={"actor": "pytest-runtime-reviewer"},
        headers=HEADERS,
    )

    assert readiness.status_code == 200
    assert readiness.json()["readiness_id"] == "runtime_demo_readiness_latest"
    assert any(item["path"] == "/runtime/demo-pack" for item in readiness.json()["smoke_urls"])
    assert export.status_code == 200
    assert export.json()["pack_id"] == "runtime_demo_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
