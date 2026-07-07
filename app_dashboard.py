import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from theme import PRIMARY, TEXT, HEADER_BG, DASH_SELECT_BG

load_dotenv()

from db.client import (
    get_appointments,
    get_patient_by_name,
    search_patients_by_name,
    get_medical_records,
    add_medical_record,
    update_appointment_status,
)
from agent.tools.search_tools import search_medical_info

st.set_page_config(
    page_title="Patient Compass — Staff Dashboard",
    page_icon="🏥",
    layout="wide",
)

st.markdown(f'<h1 style="color: {PRIMARY};">Patient Compass — Staff Dashboard</h1>', unsafe_allow_html=True)
st.caption("Internal staff view")

# Hide Streamlit's auto-generated section anchor icons (not useful in a dashboard)
st.markdown("""
<style>
[data-testid="stMarkdownAnchorLink"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Global input + dropdown styling
st.markdown(f"""
<style>
div[data-baseweb="select"] > div:first-child {{
    border: 2px solid {PRIMARY} !important;
    border-radius: 6px !important;
    background-color: {DASH_SELECT_BG} !important;
}}
div[data-testid="stTextInput"] input {{
    background-color: #F8FAFC !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 6px !important;
}}
div[data-testid="stTextInput"] input:focus {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.15) !important;
}}
button[data-baseweb="tab"] {{
    padding-left: 24px !important;
    padding-right: 24px !important;
}}
</style>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Appointments",
    "Patient Records",
    "Medical Help",
    "Metrics",
    "Agent Logs",
])

# ── Tab 1: Appointments ───────────────────────────────────────────────────────

with tab1:
    st.subheader("All Appointments")
    st.caption("Queries Supabase database directly — same data the agent uses.")

    appts = get_appointments()

    if not appts:
        st.info("No appointments found.")
    else:
        rows = []
        for a in appts:
            rows.append({
                "ID": a["id"],
                "Patient": a["patients"]["name"] if a.get("patients") else "—",
                "Doctor": a["doctors"]["name"] if a.get("doctors") else "—",
                "Specialty": a["doctors"]["specialty"] if a.get("doctors") else "—",
                "Date": a["appointment_date"],
                "Time": str(a["appointment_time"])[:5],
                "Reason": a.get("reason", ""),
                "Status": a.get("status", "scheduled"),
            })

        df = pd.DataFrame(rows)

        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Status", ["All", "scheduled", "completed", "cancelled"])
        with col2:
            doctor_options = ["All"] + sorted(df["Doctor"].dropna().unique().tolist())
            doctor_filter = st.selectbox("Doctor", doctor_options)
        with col3:
            date_filter = st.date_input("Date", value=None, key="appt_date_filter")

        filtered = df.copy()
        if status_filter != "All":
            filtered = filtered[filtered["Status"] == status_filter]
        if doctor_filter != "All":
            filtered = filtered[filtered["Doctor"] == doctor_filter]
        if date_filter:
            filtered = filtered[filtered["Date"] == str(date_filter)]

        st.dataframe(filtered.drop(columns=["ID"]), use_container_width=True)
        st.caption(f"{len(filtered)} appointment(s) shown")

        st.divider()
        st.subheader("Update Status")

        if filtered.empty:
            st.info("No appointments match the current filters.")
        else:
            appt_options = {
                f"{r['Patient']} — Dr. {r['Doctor']} on {r['Date']} at {r['Time']}": r["ID"]
                for _, r in filtered.iterrows()
            }
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                selected_label = st.selectbox("Select Appointment", list(appt_options.keys()))
            with col2:
                new_status = st.selectbox("New Status", ["completed", "cancelled", "scheduled"])
            with col3:
                st.write("")
                st.write("")
                if st.button("Update", type="primary", use_container_width=True):
                    update_appointment_status(appt_options[selected_label], new_status)
                    st.success(f"Status updated to '{new_status}'.")
                    st.rerun()

# ── Tab 2: Patient Records ────────────────────────────────────────────────────

with tab2:
    st.subheader("Patient Records")
    st.caption("Queries Supabase database directly — same data the agent uses.")

    col_s, _ = st.columns([2, 3])
    with col_s:
        search_name = st.text_input("Retrieve Patient records", placeholder="e.g. Theresa or Danielle Forbes")
        if st.button("Search", type="primary", key="patient_search_btn"):
            if not search_name.strip():
                st.warning("Enter a patient name to search.")
            else:
                st.session_state._patient_search_query = search_name.strip()
                st.session_state._patient_search_results = search_patients_by_name(search_name.strip())

    matches = st.session_state.get("_patient_search_results")

    if matches is not None:
        if not matches:
            st.error(f"No patient found matching '{st.session_state.get('_patient_search_query', '')}'.")
        else:
            if len(matches) == 1:
                patient = matches[0]
            else:
                st.caption(f"{len(matches)} patients found — select one to view their record.")
                selected_name = st.selectbox(
                    "Select patient",
                    options=[p["name"] for p in matches],
                )
                patient = next(p for p in matches if p["name"] == selected_name)

            if patient:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"### {patient['name']}")
                    st.markdown(f"**Age:** {patient['age']} &nbsp;|&nbsp; **Gender:** {patient['gender']} &nbsp;|&nbsp; **Blood Type:** {patient['blood_type']}")
                    st.markdown(f"**Condition:** {patient['medical_condition']}")
                    st.markdown(f"**Medication:** {patient['medication']}")
                with col2:
                    st.markdown(f"**Test Results:** {patient['test_results']}")
                    st.markdown(f"**Admission Type:** {patient['admission_type']}")

                st.divider()
                st.subheader("Medical Records")

                records = get_medical_records(patient["id"])

                if not records:
                    st.info("No medical records on file.")
                else:
                    for r in records:
                        with st.expander(f"{r['record_date']} — {r['diagnosis']}"):
                            st.markdown(f"**Treatment:** {r['treatment']}")
                            if r.get("notes"):
                                st.markdown(f"**Notes:** {r['notes']}")

                st.divider()
                st.subheader("Add Medical Record")

                with st.form("add_record_form"):
                    diagnosis = st.text_input("Diagnosis")
                    treatment = st.text_area("Treatment", height=80)
                    notes = st.text_area("Notes (optional)", height=60)
                    submitted = st.form_submit_button("Add Record", type="primary")

                if submitted:
                    if not diagnosis or not treatment:
                        st.warning("Diagnosis and treatment are required.")
                    else:
                        add_medical_record(patient["id"], diagnosis, treatment, notes)
                    st.success("Record added.")
                    st.rerun()

# ── Tab 3: Medical Help ─────────────────────────────────────────────────────

with tab3:
    st.subheader("Medical Help")
    st.caption("Queries Serper + PubMed directly — same sources the agent uses.")

    col_q, _ = st.columns([2, 3])
    with col_q:
        query = st.text_input("Ask a medical question", placeholder="e.g. chronic kidney disease treatment options", key="med_search_input")

    # Clear stored result as soon as the query text changes from what was last searched
    if query != st.session_state.get("med_last_query", ""):
        st.session_state.med_search_result = None

    if st.button("Search", type="primary", key="med_search_btn"):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            with st.spinner("Searching..."):
                result = search_medical_info.invoke({"query": query.strip()})
            st.session_state.med_search_result = result
            st.session_state.med_last_query = query

    if st.session_state.get("med_search_result"):
        st.markdown(st.session_state.med_search_result)

# ── Tab 4: Metrics ────────────────────────────────────────────────────────────

with tab4:
    st.subheader("Eval Metrics")
    st.caption("Populated after running `python eval/run_eval.py`.")

    try:
        import mlflow

        runs_df = mlflow.search_runs(
            experiment_names=["patient-compass-eval"],
            order_by=["start_time DESC"],
        )

        if runs_df.empty:
            st.info("No eval runs found. Run `eval/run_eval.py` to generate metrics.")
        else:
            all_metric_cols = [c for c in runs_df.columns if c.startswith("metrics.")]
            quality_cols = [c for c in all_metric_cols if not c.startswith("metrics.tool_count_")]
            tool_cols = [c for c in all_metric_cols if c.startswith("metrics.tool_count_")]
            latest = runs_df.iloc[0]

            # ── Quality metrics ───────────────────────────────────────────────
            st.markdown("### Latest Run — Quality Metrics")
            if quality_cols:
                display_cols = st.columns(len(quality_cols))
                for i, col_name in enumerate(quality_cols):
                    label = col_name.replace("metrics.", "").replace("_", " ").title()
                    value = latest.get(col_name)
                    if value is not None:
                        display_cols[i].metric(label, f"{value:.2f}")

            # ── Tool call distribution ────────────────────────────────────────
            if tool_cols:
                st.divider()
                st.markdown("### Tool Call Distribution (Latest Run)")
                tool_data = {
                    col.replace("metrics.tool_count_", "").replace("_", " "): latest.get(col, 0)
                    for col in tool_cols
                }
                tool_df = pd.DataFrame.from_dict(tool_data, orient="index", columns=["Calls"])
                tool_df = tool_df.sort_values("Calls", ascending=False)
                st.bar_chart(tool_df)

            # ── All runs history ──────────────────────────────────────────────
            st.divider()
            st.markdown("### All Runs")
            display_df = runs_df[["run_id", "start_time"] + quality_cols].copy()
            display_df.columns = [c.replace("metrics.", "") for c in display_df.columns]
            st.dataframe(display_df, use_container_width=True)

            if quality_cols:
                st.bar_chart(runs_df.set_index("start_time")[quality_cols])

    except Exception as e:
        st.info(f"MLflow not available or no experiment found. Run `eval/run_eval.py` first.\n\n`{e}`")

# ── Tab 5: Agent Logs ─────────────────────────────────────────────────────────

def _extract_tool_runs(client, project_name: str, root_run) -> list:
    """
    In LangGraph, tool runs are grandchildren of the graph run:
      graph_run → tools node (chain) → individual tool runs (tool)
    This fetches direct children, finds all nodes named 'tools', then
    fetches their children to get the actual tool runs.
    """
    children = list(client.list_runs(project_name=project_name, parent_run_id=root_run.id))
    tool_runs = []
    for child in children:
        if child.name == "tools":
            grandchildren = list(client.list_runs(project_name=project_name, parent_run_id=child.id))
            tool_runs.extend(gc for gc in grandchildren if gc.run_type == "tool")
        elif child.run_type == "tool":
            tool_runs.append(child)
    return sorted(tool_runs, key=lambda r: r.start_time.timestamp() if r.start_time else 0)


def _render_tool_usage():
    st.markdown("### Tool Usage Summary")
    st.caption("Aggregated tool calls across the last 20 conversation traces.")

    _project = st.session_state.get("_ls_project", "")
    _runs = st.session_state.get("_ls_runs", [])

    if not _runs:
        st.caption("No traces found yet. Use the chat app to generate traces.")
        return

    # Orchestration-level health — derived from root runs, no extra API calls
    total = len(_runs)
    failed = sum(1 for r in _runs if r.status == "error" or r.error)
    succeeded = total - failed
    rate = f"{(succeeded / total * 100):.0f}%" if total else "—"

    st.caption("**Orchestration Health** — root-level pipeline success across loaded traces")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Runs", total)
    c2.metric("Succeeded", succeeded)
    c3.metric("Failed", failed)
    c4.metric("Success Rate", rate)
    st.divider()

    if "_ls_tool_usage" not in st.session_state:
        with st.spinner("Loading tool usage data..."):
            try:
                from langsmith import Client as LangSmithClient
                _client = LangSmithClient()
                tool_summary: dict[str, dict] = {}
                for run in _runs:
                    for t in _extract_tool_runs(_client, _project, run):
                        name = t.name or "unknown"
                        tool_summary.setdefault(name, {"Calls": 0, "Errors": 0})
                        tool_summary[name]["Calls"] += 1
                        if t.status == "error":
                            tool_summary[name]["Errors"] += 1
                st.session_state._ls_tool_usage = tool_summary
            except Exception as e:
                st.caption(f"Could not load tool usage: {e}")
                return

    tool_summary = st.session_state.get("_ls_tool_usage")

    if tool_summary:
        summary_df = pd.DataFrame.from_dict(tool_summary, orient="index")
        summary_df.index.name = "Tool Called"
        summary_df["Success Rate"] = (
            (summary_df["Calls"] - summary_df["Errors"]) / summary_df["Calls"]
        ).round(2)
        summary_df = summary_df.sort_values("Calls", ascending=False)
        display_df = summary_df.reset_index()
        import altair as alt
        chart = (
            alt.Chart(display_df)
            .mark_bar(color=PRIMARY)
            .encode(
                x=alt.X("Tool Called:N", sort="-y", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Calls:Q", axis=alt.Axis(tickMinStep=1, tickCount=6), scale=alt.Scale(domainMin=0, nice=True)),
                tooltip=["Tool Called:N", "Calls:Q", "Errors:Q"],
            )
            .properties(height=260)
        )
        table_html = (
            display_df.style
            .format({"Success Rate": "{:.0%}"})
            .hide(axis="index")
            .set_table_styles([
                {"selector": "table", "props": [("width", "100%"), ("border-collapse", "collapse")]},
                {"selector": "thead th", "props": [
                    ("background-color", HEADER_BG),
                    ("color", TEXT),
                    ("font-weight", "600"),
                    ("padding", "6px 10px"),
                    ("text-align", "left"),
                ]},
                {"selector": "td", "props": [("padding", "4px 10px")]},
            ])
            .to_html()
        )
        col1, col2 = st.columns([2, 1])
        with col1:
            st.altair_chart(chart, use_container_width=True)
        with col2:
            st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.caption("No tool runs found in LangSmith for these traces.")


def _render_agent_reasoning():
    st.subheader("Agent Reasoning")
    st.caption("Select a conversation turn to inspect its planning and tool call sequence.")

    _run_map = st.session_state.get("_ls_run_map", {})
    _project = st.session_state.get("_ls_project", "")
    if not _run_map:
        st.caption("No traces available.")
        return

    selected_label = st.selectbox(
        "Conversation turn",
        options=list(_run_map.keys()),
        index=0,
        key="trace_selector",
    )
    selected_run = _run_map[selected_label]

    with st.spinner("Loading trace details..."):
        try:
            from langsmith import Client as LangSmithClient
            _client = LangSmithClient()
            # Fetch direct children to find plan text and ToolNode runs
            child_runs = list(_client.list_runs(
                project_name=_project,
                parent_run_id=selected_run.id,
            ))
            child_runs.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0)
            # Use _extract_tool_runs to correctly traverse graph_run → tools node → tool runs
            tool_runs = _extract_tool_runs(_client, _project, selected_run)
        except Exception as e:
            st.caption(f"Could not load trace details: {e}")
            return

    plan_text = None
    for child in child_runs:
        if child.name == "planner" and child.outputs:
            plan_text = (
                child.outputs.get("plan")
                or child.outputs.get("output", {}).get("plan")
            )
            break

    tool_calls = []
    for t in tool_runs:
        tool_output = ""
        if t.outputs:
            tool_output = t.outputs.get("output", str(t.outputs))
        tool_calls.append({
            "tool": t.name,
            "input": t.inputs or {},
            "output": str(tool_output)[:400],
            "latency": round(
                (t.end_time - t.start_time).total_seconds(), 2
            ) if t.end_time and t.start_time else None,
        })

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Task Plan**")
        if plan_text:
            st.markdown(plan_text)
        else:
            st.caption("No plan generated (short or conversational message).")
    with col2:
        st.markdown(f"**Tool Calls ({len(tool_calls)})**")
        if not tool_calls:
            st.caption("No tools fired for this conversation turn.")
        else:
            for i, tc in enumerate(tool_calls, 1):
                latency_str = f" · {tc['latency']}s" if tc["latency"] is not None else ""
                with st.expander(f"{i}. `{tc['tool']}`{latency_str}"):
                    st.markdown("**Input:**")
                    st.json(tc["input"])
                    st.markdown("**Output:**")
                    st.text(tc["output"])


@st.fragment(run_every=60)
def _render_agent_logs_live(project_name: str):
    from langsmith import Client as LangSmithClient
    from datetime import datetime

    try:
        _client = LangSmithClient()

        # Filter root runs server-side — avoids fetching hundreds of child runs
        _runs = list(_client.list_runs(
            project_name=project_name,
            filter="eq(is_root, true)",
            limit=20,
        ))
        _runs.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0, reverse=True)
        st.session_state._ls_runs = _runs
        st.session_state._ls_project = project_name

        col_r, col_ts, _ = st.columns([1, 3, 3])
        with col_r:
            if st.button("🔄 Refresh All", key="refresh_agent_logs"):
                # Runs auto-refresh; this only forces tool usage to re-fetch
                st.session_state.pop("_ls_tool_usage", None)
        with col_ts:
            st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} · auto-refreshes every 30s")

        st.subheader("Agent Logs")
        st.caption("LangGraph traces from the patient chat app.")

        if not _runs:
            st.info(
                f"No traces found in project **{project_name}**. "
                "Interact with the patient chat app to generate traces. "
                "Verify `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` are set in `.env`."
            )
        else:
            rows = []
            run_map: dict[str, object] = {}
            for run in _runs:
                latency = None
                if run.end_time and run.start_time:
                    latency = round((run.end_time - run.start_time).total_seconds(), 2)
                user_input = ""
                if run.inputs:
                    messages = run.inputs.get("messages", [])
                    if messages:
                        last = messages[-1]
                        if isinstance(last, dict):
                            user_input = last.get("content", "")[:120]
                        elif hasattr(last, "content"):
                            user_input = str(last.content)[:120]
                time_str = run.start_time.strftime("%Y-%m-%d %H:%M") if run.start_time else "—"
                label = f"{time_str}  |  {user_input[:60] or '(no input)'}"
                run_map[label] = run
                rows.append({
                    "Time": run.start_time.strftime("%Y-%m-%d %H:%M:%S") if run.start_time else "—",
                    "Input": user_input or "—",
                    "Latency (s)": latency,
                    "Run ID": str(run.id)[:8],
                    "Status": run.status or "—",
                    "Error": run.error[:200] if run.error else "—",
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.session_state._ls_run_map = run_map

        st.divider()
        _render_tool_usage()

        st.divider()
        _render_agent_reasoning()

    except Exception as e:
        import traceback
        st.error(f"LangSmith error: `{e}`")
        with st.expander("Full traceback"):
            st.code(traceback.format_exc())


with tab5:
    _project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    _render_agent_logs_live(_project_name)
