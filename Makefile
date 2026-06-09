.PHONY: install test dev mcp dashboard demo validate-skills eval conformance lint

install:
	python -m pip install -r requirements-dev.txt

test:
	python -m pytest

lint:
	python -m ruff check app tests dashboard

dev:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

mcp:
	python -m app.mcp_server tools

dashboard:
	python -m streamlit run dashboard/streamlit_app.py

demo:
	python -m app.demo

validate-skills:
	python -m app.evals.run_eval --validate-only

eval:
	python -m app.evals.run_eval

conformance:
	python -m app.evals.run_conformance
