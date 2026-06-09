from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app

HEADERS = {"X-API-Key": "dev-local-token"}


def test_conformance_report_endpoint_covers_promoted_skills() -> None:
    main_module.state = create_state()
    client = TestClient(app)

    response = client.get("/conformance/report", headers=HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["promoted_skill_count"] >= 6
    assert payload["failed_skill_count"] == 0
    assert all(skill["schema_valid"] for skill in payload["skills"])
    assert all(skill["sample_invocation_passed"] for skill in payload["skills"])
    assert all(skill["output_schema_valid"] for skill in payload["skills"])
    assert all(skill["policy_checked"] for skill in payload["skills"])
    assert all(skill["mcp_exposed"] for skill in payload["skills"])


def test_replay_endpoint_reports_same_output_for_deterministic_invocation() -> None:
    main_module.state = create_state()
    client = TestClient(app)
    invocation = client.post(
        "/skills/classify_request/invoke",
        headers=HEADERS,
        json={"input": {"request": "Security outage is blocking the RFP."}},
    ).json()

    response = client.post(f"/invocations/{invocation['id']}/replay", headers=HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["same_output"] is True
    assert payload["original_output"] == payload["replay_output"]
    assert payload["original_input"] == {"request": "Security outage is blocking the RFP."}


def test_policy_denied_invocation_replays_as_denied_consistently() -> None:
    main_module.state = create_state()
    client = TestClient(app)
    denied = client.post(
        "/skills/classify_request/invoke",
        headers=HEADERS,
        json={
            "input": {"request": "Classify this confidential support request."},
            "policy_context": {
                "role": "viewer",
                "environment": "local",
                "data_sensitivity": "confidential",
                "requested_action": "invoke",
                "enforce": True,
            },
        },
    )
    invocations = client.get("/invocations", headers=HEADERS).json()

    replay = client.post(f"/invocations/{invocations[-1]['id']}/replay", headers=HEADERS)

    assert denied.status_code == 403
    assert invocations[-1]["status"] == "failed"
    assert invocations[-1]["output"] is None
    assert replay.status_code == 200
    payload = replay.json()
    assert payload["replay_status"] == "failed"
    assert payload["replay_output"] is None
    assert payload["same_output"] is True
    assert "Policy denied" in payload["replay_error"]
