from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import EnterprisePortfolioDemoPackRequest
from app.services import EnterpriseReadinessService

HEADERS = {"X-API-Key": "dev-local-token"}


def enterprise_state(tmp_path: Path):
    state = create_state()
    state.enterprise = EnterpriseReadinessService(state, output_dir=tmp_path / "portfolio_demo")
    return state


def test_enterprise_readiness_scorecard_aggregates_portfolio_categories(tmp_path: Path) -> None:
    state = enterprise_state(tmp_path)

    scorecard = asyncio.run(state.enterprise.scorecard())

    categories = {category.category for category in scorecard.category_scores}
    assert {
        "Governance",
        "Conformance",
        "Release Readiness",
        "Audit And Attestation",
        "Capacity",
        "Dependency Blast Radius",
        "Incident Drill",
        "Tenant Sandbox",
        "Demo Agent Behavior",
    } <= categories
    assert scorecard.readiness_status in {"ready", "needs_review", "blocked"}
    assert 0 <= scorecard.overall_score <= 100
    assert scorecard.mcp_capability_counts["tool_count"] == 6
    assert "python -m app.evals.run_conformance" in scorecard.verification_commands
    assert any(
        item["endpoint"] == "POST /enterprise/portfolio-demo-pack"
        for item in scorecard.artifact_links
    )
    assert any(
        "portfolio demo pack" in action.lower()
        for action in scorecard.recommended_actions
    )


def test_portfolio_demo_pack_writes_json_and_markdown(tmp_path: Path) -> None:
    state = enterprise_state(tmp_path)

    export = asyncio.run(
        state.enterprise.portfolio_demo_pack(
            EnterprisePortfolioDemoPackRequest(actor="pytest-portfolio-reviewer")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["pack_id"] == "portfolio_demo_pack_latest"
    assert "scorecard" in bundle
    assert len(bundle["architecture_talking_points"]) == 5
    assert len(bundle["interviewer_talking_points"]) == 5
    assert any(item["path"] == "/enterprise/readiness-scorecard" for item in bundle["endpoint_map"])
    assert any("python -m app.demo" in command for command in bundle["local_demo_commands"])
    assert "jd_skills_demonstrated" in bundle
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Enterprise Readiness Portfolio Demo Pack" in markdown
    assert "Enterprise Readiness Scorecard" in markdown
    assert "Interviewer Talking Points" in markdown


def test_enterprise_endpoints_return_scorecard_and_export(tmp_path: Path) -> None:
    main_module.state = enterprise_state(tmp_path)
    client = TestClient(app)

    scorecard = client.get("/enterprise/readiness-scorecard", headers=HEADERS)
    export = client.post("/enterprise/portfolio-demo-pack", headers=HEADERS)

    assert scorecard.status_code == 200
    assert scorecard.json()["category_scores"]
    assert scorecard.json()["mcp_capability_counts"]["resource_count"] >= 1
    assert export.status_code == 200
    assert export.json()["pack_id"] == "portfolio_demo_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
