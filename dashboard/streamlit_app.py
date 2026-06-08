from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st
import yaml

from app.bootstrap import create_state
from app.evals.golden import GoldenEvalRunner, load_cases
from app.models import PolicyInvocationContext, PolicySimulationRequest, SkillManifest

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
        "Promote Skill",
        "Invoke Skill",
        "Policy Simulator",
        "Demo Agent",
        "Evaluation Lab",
        "MCP Inspector",
        "Governance Report",
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
            "status": skill.status,
            "enabled": skill.enabled,
            "mcp_exposed": state.registry.is_mcp_exposed(skill),
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
            if "status" not in payload and manifest.status == "draft":
                manifest = manifest.model_copy(update={"status": "validated"})
            st.json(state.registry.register(manifest, "streamlit-admin").model_dump(mode="json"))

elif view == "Promote Skill":
    st.subheader("Promote Skill")
    rows = [
        {
            "id": skill.id,
            "version": skill.version,
            "status": skill.status,
            "enabled": skill.enabled,
            "schema_valid": state.validator.validate_manifest(skill.model_dump(mode="json")).valid,
            "mcp_exposed": state.registry.is_mcp_exposed(skill),
        }
        for skill in state.registry.list()
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    selected = st.selectbox("Promotion candidate", [skill.id for skill in state.registry.list()])
    candidate = state.registry.get(selected)
    validation = state.validator.validate_manifest(candidate.model_dump(mode="json"))
    st.json(validation.model_dump(mode="json"))
    if st.button("Promote for MCP Exposure", use_container_width=True):
        if not validation.valid:
            st.error(validation.errors)
        else:
            st.json(state.registry.promote(selected, "streamlit-admin").model_dump(mode="json"))
            st.rerun()

elif view == "Invoke Skill":
    st.subheader("Invoke Skill")
    exposed = state.registry.mcp_exposed()
    skill = state.registry.get(st.selectbox("Promoted MCP skill", [item.id for item in exposed]))
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
    with st.expander("Policy enforcement"):
        enforce_policy = st.checkbox("Enforce policy for this invocation")
        col_role, col_environment, col_sensitivity = st.columns(3)
        policy_role = col_role.selectbox("Role", ["admin", "reviewer", "agent", "viewer"], index=2)
        policy_environment = col_environment.text_input("Environment", value="local", key="invoke_policy_env")
        policy_sensitivity = col_sensitivity.selectbox(
            "Data sensitivity",
            ["public", "internal", "confidential"],
            index=1,
            key="invoke_policy_sensitivity",
        )
    if st.button("Invoke", use_container_width=True):
        invocation = run_async(
            state.invocation_service.invoke(
                skill.id,
                json.loads(payload_text),
                "streamlit-admin",
                PolicyInvocationContext(
                    role=policy_role,
                    environment=policy_environment,
                    data_sensitivity=policy_sensitivity,
                    requested_action="invoke",
                    enforce=enforce_policy,
                ),
            )
        )
        st.json(invocation.model_dump(mode="json"))

elif view == "Policy Simulator":
    st.subheader("Policy Simulator")
    selected = st.selectbox("Skill", [skill.id for skill in state.registry.list()])
    col_role, col_sensitivity = st.columns(2)
    role = col_role.selectbox("Role", ["admin", "reviewer", "agent", "viewer"], index=2)
    sensitivity = col_sensitivity.selectbox("Data sensitivity", ["public", "internal", "confidential"], index=1)
    col_env, col_action = st.columns(2)
    environment = col_env.selectbox("Environment", ["local", "staging", "production"])
    action = col_action.selectbox("Requested action", ["invoke", "register", "promote"])
    request = PolicySimulationRequest(
        skill_id=selected,
        role=role,
        environment=environment,
        data_sensitivity=sensitivity,
        requested_action=action,
    )
    result = state.policy.simulate(state.registry.get(selected), request)
    st.metric("Decision", result.decision.upper())
    st.json(result.model_dump(mode="json"))
    st.dataframe(
        [
            {"role": role_name, "allowed_data_sensitivity": ", ".join(values)}
            for role_name, values in state.policy.access_summary(state.registry.get(selected), environment).items()
        ],
        use_container_width=True,
        hide_index=True,
    )

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

elif view == "Evaluation Lab":
    st.subheader("Evaluation Lab")
    cases = load_cases()
    st.dataframe(
        [
            {
                "id": case.id,
                "skill_id": case.skill_id,
                "expectations": len(case.expectations),
                "tags": ", ".join(case.tags),
                "description": case.description,
            }
            for case in cases
        ],
        use_container_width=True,
        hide_index=True,
    )
    if st.button("Run Golden Eval Suite", use_container_width=True):
        result = run_async(GoldenEvalRunner(state).run(cases))
        col_score, col_passed, col_failed = st.columns(3)
        col_score.metric("Score", f"{result.score:.3f}")
        col_passed.metric("Passed", result.passed_cases)
        col_failed.metric("Failed", result.failed_cases)
        st.dataframe(
            [case_result.model_dump(mode="json") for case_result in result.results],
            use_container_width=True,
            hide_index=True,
        )
        st.json(result.model_dump(mode="json"))

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

elif view == "Governance Report":
    st.subheader("Governance Report")
    report = state.governance.generate()
    col_status, col_skills, col_tools, col_cost = st.columns(4)
    col_status.metric("Status", report.status.upper())
    col_skills.metric("Registered skills", report.skills_registered)
    col_tools.metric("Enabled MCP tools", report.enabled_tools)
    col_cost.metric("Estimated cost", f"${report.estimated_cost:.4f}")
    st.dataframe(
        [skill.model_dump(mode="json") for skill in report.skills],
        use_container_width=True,
        hide_index=True,
    )
    st.dataframe(
        [check.model_dump(mode="json") for check in report.checks],
        use_container_width=True,
        hide_index=True,
    )
    st.json(report.model_dump(mode="json"))
    col_save, col_load = st.columns(2)
    if col_save.button("Save Local Snapshot", use_container_width=True):
        st.json(state.persistence.save(state).model_dump(mode="json"))
    if col_load.button("Read Local Snapshot", use_container_width=True):
        st.json(state.persistence.load())

elif view == "Metrics":
    st.subheader("Metrics")
    st.json(state.metrics.summary().model_dump(mode="json"))
    st.dataframe([metric.model_dump(mode="json") for metric in state.metrics.metrics], use_container_width=True)

elif view == "Audit Events":
    st.subheader("Audit Events")
    st.dataframe([event.model_dump(mode="json") for event in state.audit.events], use_container_width=True)
