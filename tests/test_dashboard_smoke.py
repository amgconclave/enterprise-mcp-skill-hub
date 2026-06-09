from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import UiVerificationPackRequest
from app.services import DashboardSmokeService

HEADERS = {"X-API-Key": "dev-local-token"}


def ui_state(tmp_path: Path):
    state = create_state()
    state.ui_verification = DashboardSmokeService(state, output_dir=tmp_path / "ui_verification")
    return state


def test_dashboard_smoke_checks_expected_views_and_endpoints(tmp_path: Path) -> None:
    state = ui_state(tmp_path)

    smoke = state.ui_verification.dashboard_smoke()

    assert smoke.smoke_id == "dashboard_smoke_latest"
    assert smoke.readiness_status == "ready"
    assert smoke.summary["fail_count"] == 0
    assert any(view["label"] == "UI Verification" for view in smoke.expected_views)
    assert any(endpoint["path"] == "/ui/dashboard-smoke" for endpoint in smoke.endpoint_references)
    assert any(endpoint["path"] == "/ui/verification-pack" for endpoint in smoke.endpoint_references)
    assert any(tab["artifact_dir"] == "data/ui_verification/" for tab in smoke.generated_artifact_tabs)
    assert any(surface["dashboard_label"] == "MCP Inspector" for surface in smoke.mcp_proof_surfaces)
    assert "python scripts\\dashboard_smoke.py" in smoke.local_run_commands


def test_ui_verification_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = ui_state(tmp_path)

    export = state.ui_verification.verification_pack(
        UiVerificationPackRequest(actor="pytest-github-reviewer")
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert export.pack_id == "ui_verification_pack_latest"
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "dashboard_smoke" in bundle
    assert "reviewer_checklist" in bundle
    assert "screenshot_placeholders" in bundle
    assert bundle["streamlit_run_command"] == "python -m streamlit run dashboard/streamlit_app.py"
    assert "UI Verification Pack" in markdown
    assert "Dashboard Smoke" in markdown
    assert "Screenshot Placeholders" in markdown


def test_ui_endpoints_return_dashboard_smoke_and_pack(tmp_path: Path) -> None:
    main_module.state = ui_state(tmp_path)
    client = TestClient(app)

    smoke = client.get("/ui/dashboard-smoke", headers=HEADERS)
    export = client.post(
        "/ui/verification-pack",
        json={"actor": "pytest-github-reviewer"},
        headers=HEADERS,
    )

    assert smoke.status_code == 200
    assert smoke.json()["smoke_id"] == "dashboard_smoke_latest"
    assert smoke.json()["summary"]["fail_count"] == 0
    assert export.status_code == 200
    assert export.json()["pack_id"] == "ui_verification_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
