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
    get_slot_utilization,
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
    "Agent Insights",
    "Metrics",
])

# ── Tab 1: Appointments ───────────────────────────────────────────────────────

with tab1:
    st.subheader("Appointment Tracking")
    st.caption("Queries Supabase database directly.")

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

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            patient_filter = st.text_input("Patient Name", placeholder="Search by name...", key="appt_patient_filter")
        with col2:
            status_filter = st.selectbox("Status", ["All", "scheduled", "completed", "cancelled"])
        with col3:
            doctor_options = ["All"] + sorted(df["Doctor"].dropna().unique().tolist())
            doctor_filter = st.selectbox("Doctor", doctor_options)
        with col4:
            date_filter = st.date_input("Date", value=None, key="appt_date_filter")

        filtered = df.copy()
        if patient_filter.strip():
            filtered = filtered[filtered["Patient"].str.contains(patient_filter.strip(), case=False, na=False)]
        if status_filter != "All":
            filtered = filtered[filtered["Status"] == status_filter]
        if doctor_filter != "All":
            filtered = filtered[filtered["Doctor"] == doctor_filter]
        if date_filter:
            filtered = filtered[filtered["Date"] == str(date_filter)]

        st.dataframe(filtered.drop(columns=["ID"]), width="stretch")
        st.caption(f"{len(filtered)} appointment(s) shown")

        st.divider()
        st.subheader("Update Status")

        if st.session_state.pop("_status_updated", False):
            st.success(st.session_state.pop("_status_updated_msg", "Status updated."))

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
                if st.button("Update", type="primary", width="stretch"):
                    update_appointment_status(appt_options[selected_label], new_status)
                    st.session_state["_status_updated"] = True
                    st.session_state["_status_updated_msg"] = f"Status updated to '{new_status}'."
                    st.rerun()

# ── Tab 2: Patient Records ────────────────────────────────────────────────────

with tab2:
    st.subheader("Patient Records")
    st.caption("Queries Supabase database directly.")

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

                if st.session_state.pop("_record_added", False):
                    st.success("Record added successfully.")

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
                        st.session_state["_record_added"] = True
                        st.rerun()

# ── Tab 3: Medical Help ─────────────────────────────────────────────────────

with tab3:
    st.subheader("Medical Help")
    st.caption("Queries Serper + PubMed directly.")

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

# ── Tab 5: Metrics ────────────────────────────────────────────────────────────

with tab5:
    st.subheader("Eval Metrics")

    # ── Live booking metrics (from Supabase) ──────────────────────────────────
    @st.fragment(run_every=60)
    def _render_booking_performance():
        from datetime import datetime, timedelta, date
        today = date.today()

        st.markdown("### Appointment Booking Performance")
        st.caption(f"Real appointment data from the database — auto-refreshes every 60s · Last updated: {datetime.now().strftime('%H:%M:%S')}")

        all_appts = get_appointments()
        if not all_appts:
            st.info("No appointment data found.")
            return

        tomorrow = today + timedelta(days=1)
        total = len(all_appts)
        upcoming = sum(1 for a in all_appts if a.get("status") == "scheduled")
        cancelled = sum(1 for a in all_appts if a.get("status") == "cancelled")
        today_count = sum(1 for a in all_appts if a.get("appointment_date") == today.isoformat() and a.get("status") == "scheduled")
        tomorrow_count = sum(1 for a in all_appts if a.get("appointment_date") == tomorrow.isoformat() and a.get("status") == "scheduled")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Bookings", total)
        c2.metric("Today", today_count)
        c3.metric("Tomorrow", tomorrow_count)

        st.divider()
        st.markdown("**Slot Utilization**")

        periods = [("Next 7 Days", 7), ("Next 14 Days", 14), ("Next 30 Days", 30)]
        cols = st.columns(len(periods))
        for col, (label, days) in zip(cols, periods):
            end = today + timedelta(days=days)
            stats = get_slot_utilization(today.isoformat(), end.isoformat())
            rate = stats["booked"] / stats["total"] if stats["total"] else 0.0
            col.metric(label, f"{rate:.0%}", help=f"{stats['booked']} booked of {stats['total']} total slots")

    _render_booking_performance()

    # ── Eval quality metrics (from MLflow) ───────────────────────────────────
    st.divider()
    st.markdown("### Agent Quality Scores")
    st.caption("Scored against the last 20 real patient conversations pulled from LangSmith. Run `python eval/run_eval.py` to refresh.")

    try:
        import mlflow
        mlflow.set_tracking_uri("sqlite:///mlflow.db")

        runs_df = mlflow.search_runs(
            experiment_names=["patient-compass-eval"],
            order_by=["start_time DESC"],
        )

        if runs_df.empty:
            st.info("No eval runs found. Run `eval/run_eval.py` to generate metrics.")
        else:
            all_metric_cols = [c for c in runs_df.columns if c.startswith("metrics.")]
            _exclude = {"metrics.tool_count_", "metrics.traces_evaluated", "metrics.cases_run",
                        "metrics.avg_latency_s", "metrics.booking_success_rate"}
            quality_cols = [
                c for c in all_metric_cols
                if not any(c.startswith(ex) or c == ex for ex in _exclude)
            ]
            latest = runs_df.iloc[0]

            _metric_descriptions = {
                "avg_correctness": "Did the agent accurately address the patient's request and take the right action?",
                "avg_relevance": "Did the response stay on-topic and directly answer what the patient asked?",
                "avg_safety": "Did the response include appropriate disclaimers, avoid prescribing, and recommend a physician when warranted?",
                "avg_task_completion": "Did the agent complete the requested action — booking, history retrieval, or answering the patient's question?",
            }

            if quality_cols:
                table_rows = []
                for col_name in quality_cols:
                    key = col_name.replace("metrics.", "")
                    label = key.replace("_", " ").title().replace("Avg ", "Average ")
                    value = latest.get(col_name)
                    description = _metric_descriptions.get(key, "")
                    if value is not None and not pd.isna(value):
                        table_rows.append({
                            "Metric": label,
                            "Score": f"{value:.0%}",
                            "Description": description,
                        })
                if table_rows:
                    st.dataframe(
                        pd.DataFrame(table_rows),
                        width="stretch",
                        hide_index=True,
                        column_config={
                            "Metric": st.column_config.TextColumn(width=150),
                            "Score": st.column_config.TextColumn(width=100),
                            "Description": st.column_config.TextColumn(width=750),
                        },
                    )


    except Exception as e:
        st.info(f"MLflow not available or no experiment found. Run `eval/run_eval.py` first.\n\n`{e}`")

# ── Tab 4: Agent Insights ─────────────────────────────────────────────────────

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
    st.caption("Aggregated tool calls across the last 50 conversation traces.")

    _project = st.session_state.get("_ls_project", "")
    _runs = st.session_state.get("_ls_runs_clean", [])

    if not _runs:
        st.caption("No traces found yet. Use the chat app to generate traces.")
        return

    # Orchestration-level health — derived from clean runs (rate limit errors excluded)
    total = len(_runs)
    failed = sum(1 for r in _runs if r.status == "error" or r.error)
    succeeded = total - failed
    rate = f"{(succeeded / total * 100):.0f}%" if total else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Runs", total)
    c2.metric("Succeeded", succeeded)
    c3.metric("Failed", failed)
    c4.metric("Success Rate", rate)
    st.divider()

    # Invalidate cached tool usage whenever the clean trace set changes
    _current_ids = frozenset(str(r.id) for r in _runs)
    if st.session_state.get("_ls_tool_usage_ids") != _current_ids:
        st.session_state.pop("_ls_tool_usage", None)
        st.session_state["_ls_tool_usage_ids"] = _current_ids

    if "_ls_tool_usage" not in st.session_state:
        with st.spinner("Loading tool usage data..."):
            try:
                from langsmith import Client as LangSmithClient
                ls = LangSmithClient()
                # Single API call — fetch all recent tool runs for the project
                # instead of traversing each root run's children (which is 40-80 calls)
                clean_trace_ids = {str(r.id) for r in _runs}
                tool_runs = list(ls.list_runs(
                    project_name=_project,
                    run_type="tool",
                    limit=100,
                ))
                # Only count tool runs from clean traces (no rate limit errors)
                tool_runs = [t for t in tool_runs if str(t.trace_id) in clean_trace_ids]
                tool_summary: dict[str, dict] = {}
                for t in tool_runs:
                    name = t.name or "unknown"
                    tool_summary.setdefault(name, {"Calls": 0, "Errors": 0, "_latency_total": 0.0, "_latency_count": 0})
                    tool_summary[name]["Calls"] += 1
                    if t.status == "error":
                        tool_summary[name]["Errors"] += 1
                    if t.start_time and t.end_time:
                        latency = (t.end_time - t.start_time).total_seconds()
                        tool_summary[name]["_latency_total"] += latency
                        tool_summary[name]["_latency_count"] += 1
                st.session_state._ls_tool_usage = tool_summary
            except Exception as e:
                st.error(f"Could not load tool usage: {e}")
                return

    tool_summary = st.session_state.get("_ls_tool_usage")

    if tool_summary is not None and len(tool_summary) > 0:
        summary_df = pd.DataFrame.from_dict(tool_summary, orient="index")
        summary_df.index.name = "Tool Called"
        summary_df["Success Rate"] = (
            (summary_df["Calls"] - summary_df["Errors"]) / summary_df["Calls"]
        ).round(2)
        summary_df["Avg Latency (s)"] = (
            summary_df["_latency_total"] / summary_df["_latency_count"].replace(0, float("nan"))
        ).round(2)
        summary_df = summary_df.drop(columns=["_latency_total", "_latency_count"])
        summary_df = summary_df.sort_values("Calls", ascending=False)
        display_df = summary_df.reset_index()
        import altair as alt
        chart = (
            alt.Chart(display_df)
            .mark_bar(color=PRIMARY)
            .encode(
                x=alt.X("Tool Called:N", sort="-y", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Calls:Q", axis=alt.Axis(tickMinStep=1, tickCount=6), scale=alt.Scale(domainMin=0, nice=True)),
                tooltip=["Tool Called:N", "Calls:Q", "Errors:Q", "Avg Latency (s):Q"],
            )
            .properties(height=260)
        )
        table_html = (
            display_df.style
            .format({"Success Rate": "{:.0%}", "Avg Latency (s)": "{:.2f}s"})
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
            st.altair_chart(chart, width="stretch")
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

    # Tool calls and plan are embedded in the run's output state — no extra API calls needed.
    outputs = selected_run.outputs or {}
    messages = outputs.get("messages", [])

    # Plan is part of LangGraph state and comes back in outputs directly
    plan_text = outputs.get("plan") or None

    # Collect tool results keyed by tool_call_id
    tool_results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, dict) and msg.get("type") == "tool":
            tc_id = msg.get("tool_call_id", "")
            if tc_id:
                tool_results[tc_id] = str(msg.get("content", ""))[:400]

    # Collect tool calls from AI messages and pair with results
    tool_calls = []
    for msg in messages:
        if isinstance(msg, dict) and msg.get("type") == "ai":
            for tc in msg.get("tool_calls", []):
                tc_id = tc.get("id", "")
                tool_calls.append({
                    "tool": tc.get("name", "unknown"),
                    "input": tc.get("args", {}),
                    "output": tool_results.get(tc_id, ""),
                    "latency": None,
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

        def _has_user_msg(run) -> bool:
            for msg in (run.inputs or {}).get("messages", []):
                t = msg.get("type") if isinstance(msg, dict) else getattr(msg, "type", None)
                if t == "human":
                    return True
            return False

        def _is_clean(run) -> bool:
            if run.error and "rate_limit" in run.error.lower():
                return False
            if run.run_type and run.run_type != "chain":
                return False
            return _has_user_msg(run)

        # Stream root runs lazily. Collect everything for Agent Logs (up to 50),
        # and keep pulling until we have 20 clean records for Tool Usage + Agent Reasoning.
        # Agent Logs sees all runs including errors; clean sections only see valid patient turns.
        _runs: list = []
        _runs_clean: list = []
        _checked = 0
        for _run in _client.list_runs(project_name=project_name, filter="eq(is_root, true)"):
            _checked += 1
            if _checked > 500:
                break
            if len(_runs) < 50:
                _runs.append(_run)
            if len(_runs_clean) < 20 and _is_clean(_run):
                _runs_clean.append(_run)
            if len(_runs_clean) >= 20 and len(_runs) >= 50:
                break

        _runs.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0, reverse=True)
        _runs_clean.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0, reverse=True)
        st.session_state._ls_runs = _runs
        st.session_state._ls_runs_clean = _runs_clean
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
            def _extract_run_meta(run):
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
                return latency, user_input

            # Agent Logs table — all runs including rate limit errors (useful for troubleshooting)
            rows = []
            for run in _runs:
                latency, user_input = _extract_run_meta(run)
                rows.append({
                    "Time": run.start_time.strftime("%Y-%m-%d %H:%M:%S") if run.start_time else "—",
                    "Input": user_input or "—",
                    "Latency (s)": latency,
                    "Run ID": str(run.id)[:8],
                    "Status": run.status or "—",
                    "Error": run.error[:200] if run.error else "—",
                })
            st.dataframe(pd.DataFrame(rows), width="stretch")

            # run_map for Agent Reasoning — clean runs only (no rate limit errors)
            run_map: dict[str, object] = {}
            for run in _runs_clean:
                _, user_input = _extract_run_meta(run)
                time_str = run.start_time.strftime("%Y-%m-%d %H:%M") if run.start_time else "—"
                label = f"{time_str}  |  {user_input[:60] or '(no input)'}"
                run_map[label] = run
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


with tab4:
    _project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    _render_agent_logs_live(_project_name)
