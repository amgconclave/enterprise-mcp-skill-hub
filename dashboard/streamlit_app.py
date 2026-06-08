from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st
import yaml

from app.bootstrap import create_state
from app.models import SkillManifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "sample_data" / "manifests"


@st.cache_resource
def get_state():
    return create_state()


def run_async(coro):
    return asyncio.run(coro)


state = get_state()

st.set_page_config(page_title="Enterprise MCP Skill Hub", layout="wide")
st.title("Enterprise MCP Skill Hub")

view = st.sidebar.radio(
    "View",
    [
        "Skill Catalog",
        "Register / Validate Skill",
        "Invoke Skill",
        "Demo Agent",
        "MCP Inspector",
        "Metrics",
        "Audit Events",
    ],
)


if view == "Skill Catalog":
    st.subheader("Skill Catalog")
    rows = [
        {
            "id": skill.id,
            "name": skill.name,
            "version": skill.version,
            "enabled": skill.enabled,
            "provider": skill.provider,
            "tags": ", ".join(skill.tags),
            "description": skill.description,
        }
        for skill in state.registry.list()
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    selected = st.selectbox("Skill status", [skill.id for skill in state.registry.list()])
    col_enable, col_disable = st.columns(2)
    if col_enable.button("Enable", use_container_width=True):
        state.registry.set_status(selected, True, "streamlit-admin")
        st.rerun()
    if col_disable.button("Disable", use_container_width=True):
        state.registry.set_status(selected, False, "streamlit-admin")
        st.rerun()

elif view == "Register / Validate Skill":
    st.subheader("Register / Validate Skill")
    manifest_files = sorted(MANIFEST_DIR.glob("*.yaml"))
    chosen = st.selectbox("Sample manifest", [path.name for path in manifest_files])
    manifest_text = st.text_area(
        "Manifest YAML",
        value=(MANIFEST_DIR / chosen).read_text(encoding="utf-8"),
        height=420,
    )
    payload = yaml.safe_load(manifest_text)
    col_validate, col_register = st.columns(2)
    if col_validate.button("Validate", use_container_width=True):
        st.json(state.validator.validate_manifest(payload).model_dump(mode="json"))
    if col_register.button("Register", use_container_width=True):
        result = state.validator.validate_manifest(payload)
        if not result.valid:
            st.error(result.errors)
        else:
            manifest = SkillManifest.model_validate(payload)
            st.json(state.registry.register(manifest, "streamlit-admin").model_dump(mode="json"))

elif view == "Invoke Skill":
    st.subheader("Invoke Skill")
    enabled = state.registry.enabled()
    skill = state.registry.get(st.selectbox("Enabled skill", [item.id for item in enabled]))
    st.caption(skill.description)
    example = {
        "summarize_document": {"text": (ROOT / "sample_data" / "meeting_notes.txt").read_text(encoding="utf-8")},
        "extract_entities": {"text": (ROOT / "sample_data" / "support_ticket.txt").read_text(encoding="utf-8")},
        "translate_text": {"text": "Hello enterprise agent.", "target_language": "French"},
        "classify_request": {"request": (ROOT / "sample_data" / "rfp_question.txt").read_text(encoding="utf-8")},
        "generate_action_items": {"text": (ROOT / "sample_data" / "meeting_notes.txt").read_text(encoding="utf-8")},
        "search_knowledge_base": {"query": "AI governance policy audit disabled skills", "limit": 3},
    }.get(skill.id, {})
    payload_text = st.text_area("Input JSON", value=json.dumps(example, indent=2), height=260)
    if st.button("Invoke", use_container_width=True):
        invocation = run_async(state.invocation_service.invoke(skill.id, json.loads(payload_text), "streamlit-admin"))
        st.json(invocation.model_dump(mode="json"))

elif view == "Demo Agent":
    st.subheader("Demo Agent")
    default_prompt = (
        "Summarize the Atlas Labs support meeting, classify the RFP request, search approved policy "
        "context, and create action items for Priya Shah by 2026-06-15."
    )
    prompt = st.text_area("Compound task", value=default_prompt, height=160)
    if st.button("Run Agent", use_container_width=True):
        run = run_async(state.agent.run(prompt, "streamlit-admin"))
        st.json(run.model_dump(mode="json"))

elif view == "MCP Inspector":
    st.subheader("MCP Inspector")
    tab_tools, tab_resources, tab_prompts = st.tabs(["Tools", "Resources", "Prompts"])
    with tab_tools:
        st.json([tool.model_dump(mode="json") for tool in state.mcp.list_tools()])
    with tab_resources:
        resources = state.mcp.list_resources()
        st.json([resource.model_dump(mode="json") for resource in resources])
        uri = st.selectbox("Read resource", [resource.uri for resource in resources])
        st.json(state.mcp.read_resource(uri).model_dump(mode="json"))
    with tab_prompts:
        st.json([prompt.model_dump(mode="json") for prompt in state.mcp.list_prompts()])

elif view == "Metrics":
    st.subheader("Metrics")
    st.json(state.metrics.summary().model_dump(mode="json"))
    st.dataframe([metric.model_dump(mode="json") for metric in state.metrics.metrics], use_container_width=True)

elif view == "Audit Events":
    st.subheader("Audit Events")
    st.dataframe([event.model_dump(mode="json") for event in state.audit.events], use_container_width=True)
