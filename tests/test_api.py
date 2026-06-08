from fastapi.testclient import TestClient

from app.main import app, state

client = TestClient(app)


def test_demo_token_and_health_are_public() -> None:
    token = client.post("/auth/demo-token")
    health = client.get("/health")

    assert token.status_code == 200
    assert token.json()["token"] == "dev-local-token"
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_auth_is_required_for_skill_catalog() -> None:
    response = client.get("/skills")

    assert response.status_code == 401


def test_skill_catalog_and_invocation_api() -> None:
    response = client.get("/skills", headers={"X-API-Key": "dev-local-token"})
    invoke = client.post(
        "/skills/classify_request/invoke",
        headers={"X-API-Key": "dev-local-token"},
        json={"input": {"request": "RFP security review is blocked."}},
    )

    assert response.status_code == 200
    assert len(response.json()) >= 6
    assert invoke.status_code == 200
    assert invoke.json()["output"]["category"] == "sales"


def test_status_change_hides_mcp_tool() -> None:
    client.patch(
        "/skills/translate_text/status",
        headers={"X-API-Key": "dev-local-token"},
        json={"enabled": False, "actor": "pytest"},
    )
    tools = client.get("/mcp/tools", headers={"X-API-Key": "dev-local-token"}).json()
    client.patch(
        "/skills/translate_text/status",
        headers={"X-API-Key": "dev-local-token"},
        json={"enabled": True, "actor": "pytest"},
    )

    assert "translate_text" not in [tool["name"] for tool in tools]


def test_metrics_endpoint_reflects_usage() -> None:
    state.metrics.metrics.clear()
    client.post(
        "/skills/generate_action_items/invoke",
        headers={"X-API-Key": "dev-local-token"},
        json={"input": {"text": "Action: Devan to follow up by 2026-06-15."}},
    )

    response = client.get("/metrics/usage", headers={"X-API-Key": "dev-local-token"})

    assert response.status_code == 200
    assert response.json()["invocation_count"] == 1
