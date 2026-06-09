from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app

HEADERS = {"X-API-Key": "dev-local-token"}


def test_artifact_inventory_lists_reviewer_artifact_families() -> None:
    state = create_state()
    inventory = state.artifacts.inventory()

    names = {item.name for item in inventory.items}
    assert inventory.inventory_id == "artifact_inventory_latest"
    assert inventory.artifact_count >= 12
    assert "Artifact Inventory + README Checklist" in names
    assert "Enterprise Portfolio Demo Pack" in names
    assert "Release Candidate Publish Pack" in names
    assert "Local CI Doctor Audit Pack" in names
    assert "UI Verification Pack" in names
    assert "Reviewer Walkthrough Pack" in names
    assert "Local Launch Checklist" in names
    assert "Conformance Report Output" in names
    assert "Governance Report Output" in names
    assert any(item.directory == "data/artifact_indexes" for item in inventory.items)
    assert any("artifacts/readme-checklist" in command for command in inventory.local_commands)
    assert any("reviewer proof checklist" in command for command in inventory.local_commands)
    assert all(item.reviewer_purpose for item in inventory.items)


def test_readme_checklist_writes_markdown_and_json(tmp_path: Path) -> None:
    state = create_state()
    state.artifacts.output_dir = tmp_path / "artifact_indexes"

    export = state.artifacts.readme_checklist()

    assert export.checklist_id == "readme_checklist_latest"
    assert "artifact_indexes" in export.json_path
    assert Path(export.json_path).exists()
    assert Path(export.markdown_path).exists()

    bundle = json.loads(Path(export.json_path).read_text(encoding="utf-8"))
    markdown = Path(export.markdown_path).read_text(encoding="utf-8")
    assert "artifact_inventory" in bundle
    assert "readme_badge_suggestions" in bundle
    assert "reviewer_proof_checklist" in bundle
    assert "cleanup_regeneration_notes" in bundle
    assert "README Checklist" in markdown
    assert "reviewer proof checklist" in markdown


def test_artifact_inventory_endpoints_return_inventory_and_checklist(tmp_path: Path) -> None:
    main_module.state = create_state()
    main_module.state.artifacts.output_dir = tmp_path / "artifact_indexes"
    client = TestClient(app)

    inventory = client.get("/artifacts/inventory", headers=HEADERS)
    export = client.post(
        "/artifacts/readme-checklist",
        json={"actor": "pytest-github-reviewer"},
        headers=HEADERS,
    )

    assert inventory.status_code == 200
    assert inventory.json()["inventory_id"] == "artifact_inventory_latest"
    assert any(
        item["producer_endpoint"] == "POST /artifacts/readme-checklist"
        for item in inventory.json()["items"]
    )
    assert export.status_code == 200
    assert export.json()["checklist_id"] == "readme_checklist_latest"
    assert Path(export.json()["json_path"]).exists()
