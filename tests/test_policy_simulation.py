from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.main import app


def test_policy_simulation_denies_viewer_confidential_invocation() -> None:
    main_module.state = create_state()
    client = TestClient(app)

    response = client.post(
        "/policy/simulate",
        headers={"X-API-Key": "dev-local-token"},
        json={
            "skill_id": "classify_request",
            "role": "viewer",
            "environment": "local",
            "data_sensitivity": "confidential",
            "requested_action": "invoke",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "deny"
    assert "viewer-public-only" in payload["matched_rules"]


def test_enforced_policy_blocks_invocation() -> None:
    main_module.state = create_state()
    client = TestClient(app)

    response = client.post(
        "/skills/classify_request/invoke",
        headers={"X-API-Key": "dev-local-token"},
        json={
            "input": {"request": "Classify this internal support request."},
            "policy_context": {
                "role": "viewer",
                "environment": "local",
                "data_sensitivity": "confidential",
                "requested_action": "invoke",
                "enforce": True,
            },
        },
    )

    assert response.status_code == 403
    assert "Policy denied" in response.json()["detail"]
