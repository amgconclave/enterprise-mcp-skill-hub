import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.bootstrap import create_state
from app.evals.golden import GoldenEvalRunner, load_cases
from app.main import app


@pytest.mark.asyncio
async def test_golden_eval_runner_scores_expected_behavior() -> None:
    state = create_state()

    result = await GoldenEvalRunner(state).run(load_cases())

    assert result.total_cases >= 4
    assert result.failed_cases == 0
    assert result.score == 1.0
    assert all(case.trace_id for case in result.results)


def test_golden_eval_api_endpoint() -> None:
    main_module.state = create_state()
    client = TestClient(app)

    response = client.post("/evals/golden", headers={"X-API-Key": "dev-local-token"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["score"] == 1.0
    assert payload["failed_cases"] == 0
