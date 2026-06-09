from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app
from app.models import PortfolioInterviewPackRequest
from app.services import PortfolioEvidenceService

HEADERS = {"X-API-Key": "dev-local-token"}


def portfolio_state(tmp_path: Path):
    state = create_state()
    state.portfolio = PortfolioEvidenceService(state, output_dir=tmp_path / "portfolio_packs")
    return state


def test_portfolio_evidence_index_maps_jd_skills_to_proof(tmp_path: Path) -> None:
    state = portfolio_state(tmp_path)

    index = asyncio.run(state.portfolio.evidence_index())

    skills = {item["jd_skill"] for item in index.jd_coverage}
    assert "MCP tools/resources/prompts" in skills
    assert "Portfolio Evidence and Interview Pack" in skills
    assert index.evidence_score >= 80
    assert index.jd_skill_count == len(index.jd_coverage)
    assert index.proof_count == len(index.proof_matrix)
    assert index.mcp_capability_counts["tool_count"] == 6
    assert any(row["proof"] == "/portfolio/evidence-index" for row in index.proof_matrix)
    assert any("portfolio/interview-pack" in command for command in index.verification_commands)
    assert index.summary["local_only"] is True


def test_portfolio_interview_pack_writes_markdown_and_json(tmp_path: Path) -> None:
    state = portfolio_state(tmp_path)

    export = asyncio.run(
        state.portfolio.interview_pack(
            PortfolioInterviewPackRequest(actor="pytest-portfolio-interviewer")
        )
    )

    json_path = Path(export.json_path)
    markdown_path = Path(export.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["pack_id"] == "interview_pack_latest"
    assert "evidence_index" in bundle
    assert len(bundle["three_minute_demo_script"]) >= 5
    assert 8 <= len(bundle["technical_talking_points"]) <= 10
    assert "architecture_walkthrough" in bundle
    assert "governance_failure_mode_story" in bundle
    assert "metrics_eval_summary" in bundle
    assert "resume_bullets" in bundle
    assert "github_readme_bullets" in bundle
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Portfolio Evidence Interview Pack" in markdown
    assert "3-Minute Demo Script" in markdown
    assert "Technical Talking Points" in markdown
    assert "Evidence score" in markdown


def test_portfolio_endpoints_return_index_and_interview_pack(tmp_path: Path) -> None:
    main_module.state = portfolio_state(tmp_path)
    client = TestClient(app)

    index = client.get("/portfolio/evidence-index", headers=HEADERS)
    export = client.post("/portfolio/interview-pack", headers=HEADERS)

    assert index.status_code == 200
    assert index.json()["proof_matrix"]
    assert index.json()["summary"]["local_only"] is True
    assert export.status_code == 200
    assert export.json()["pack_id"] == "interview_pack_latest"
    assert Path(export.json()["json_path"]).exists()
    assert Path(export.json()["markdown_path"]).exists()
