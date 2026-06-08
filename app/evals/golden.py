from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import GoldenEvalCase, GoldenEvalCaseResult, GoldenEvalSuiteResult, JsonDict
from app.services import AppState
from app.utils import new_id, utc_now

DEFAULT_GOLDEN_CASES = Path("sample_data") / "evals" / "golden_cases.json"


def read_path(payload: JsonDict, path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit():
            value = value[int(part)]
        else:
            return None
    return value


def load_cases(path: Path | None = None) -> list[GoldenEvalCase]:
    case_path = path or DEFAULT_GOLDEN_CASES
    payload = json.loads(case_path.read_text(encoding="utf-8"))
    return [GoldenEvalCase.model_validate(case) for case in payload["cases"]]


def check_expectation(output: JsonDict, path: str, operator: str, expected: Any) -> tuple[bool, str]:
    actual = read_path(output, path)
    if operator == "exists":
        passed = actual is not None
    elif operator == "equals":
        passed = actual == expected
    elif operator == "contains":
        if isinstance(actual, list):
            passed = expected in actual or any(expected in str(item) for item in actual)
        else:
            passed = expected in str(actual)
    elif operator == "min_length":
        passed = hasattr(actual, "__len__") and len(actual) >= int(expected)
    else:
        passed = False
    detail = f"{path} {operator} {expected!r}; actual={actual!r}"
    return passed, detail


class GoldenEvalRunner:
    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state

    async def run(self, cases: list[GoldenEvalCase] | None = None) -> GoldenEvalSuiteResult:
        eval_cases = cases or load_cases()
        results: list[GoldenEvalCaseResult] = []
        for case in eval_cases:
            invocation = await self.app_state.invocation_service.invoke(case.skill_id, case.input, "golden-eval")
            failed_expectations: list[str] = []
            output = invocation.output or {}
            if invocation.status == "failed":
                failed_expectations.append(invocation.error or "Invocation failed.")
            else:
                for expectation in case.expectations:
                    passed, detail = check_expectation(
                        output,
                        expectation.path,
                        expectation.operator,
                        expectation.value,
                    )
                    if not passed:
                        failed_expectations.append(detail)
            status = "pass" if not failed_expectations else "fail"
            expected_count = max(len(case.expectations), 1)
            score = round((expected_count - len(failed_expectations)) / expected_count, 3)
            results.append(
                GoldenEvalCaseResult(
                    case_id=case.id,
                    skill_id=case.skill_id,
                    status=status,
                    score=max(score, 0.0),
                    trace_id=invocation.trace_id,
                    latency_ms=invocation.latency_ms,
                    failed_expectations=failed_expectations,
                )
            )
        total = len(results)
        passed = sum(result.status == "pass" for result in results)
        latency = sum(result.latency_ms for result in results)
        return GoldenEvalSuiteResult(
            run_id=new_id("eval"),
            generated_at=utc_now(),
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            score=round(sum(result.score for result in results) / total, 3) if total else 0.0,
            average_latency_ms=round(latency / total, 2) if total else 0.0,
            results=results,
        )
