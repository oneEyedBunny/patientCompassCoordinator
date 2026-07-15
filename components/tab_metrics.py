import os
import streamlit as st
import pandas as pd
from db.client import get_appointments
from services.telemetry import fetch_runs
from theme import PRIMARY, HEADER_BG, TEXT, LATENCY_GOOD_S, LATENCY_WARN_S, LATENCY_COLOR_GOOD, LATENCY_COLOR_WARN, LATENCY_COLOR_BAD


def _render_tool_usage():
    from datetime import datetime
    from langsmith import Client as LangSmithClient

    project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    _, runs_clean = fetch_runs(project_name)

    st.markdown("### Tool Usage Summary")
    st.caption(f"Aggregated tool calls across the last 50 conversation traces — auto-refreshes every 60s · Last updated: {datetime.now().strftime('%H:%M:%S')}")

    if not runs_clean:
        st.caption("No traces found yet. Use the chat app to generate traces.")
        return

    # Orchestration-level health — derived from clean runs (rate limit errors excluded)
    total = len(runs_clean)
    failed = sum(1 for r in runs_clean if r.status == "error" or r.error)
    succeeded = total - failed
    rate = f"{(succeeded / total * 100):.0f}%" if total else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Runs", total)
    c2.metric("Succeeded", succeeded)
    c3.metric("Failed", failed)
    c4.metric("Success Rate", rate)
    st.divider()

    # Invalidate cached tool usage whenever the clean trace set changes
    _current_ids = frozenset(str(r.id) for r in runs_clean)
    if st.session_state.get("_ls_tool_usage_ids") != _current_ids:
        st.session_state.pop("_ls_tool_usage", None)
        st.session_state["_ls_tool_usage_ids"] = _current_ids

    if "_ls_tool_usage" not in st.session_state:
        with st.spinner("Loading"):
            try:
                ls = LangSmithClient()
                clean_trace_ids = {str(r.id) for r in runs_clean}
                tool_runs = list(ls.list_runs(
                    project_name=project_name,
                    run_type="tool",
                    limit=100,
                ))
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
        summary_df["Avg Latency"] = (
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
                tooltip=["Tool Called:N", "Calls:Q", "Errors:Q", "Avg Latency:Q"],
            )
            .properties(height=260)
        )
        table_html = (
            display_df.style
            .format({"Success Rate": "{:.0%}", "Avg Latency": "{:.2f}s"})
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
        col1, col2 = st.columns([2, 1], vertical_alignment="bottom")
        with col1:
            st.altair_chart(chart, width="stretch")
        with col2:
            st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.caption("No tool runs found in LangSmith for these traces.")


@st.fragment
def _render_governance_eval():
    import mlflow

    st.markdown("### Guardrail Quality Scores")
    st.caption("Deterministic test suite — runs predefined input and output cases through the guardrail functions and publishes results to MLflow. No LLM calls. Re-run any time guardrail logic changes.")

    with st.spinner("Loading"):
        try:
            mlflow.set_tracking_uri("sqlite:///mlflow.db")
            runs_df = mlflow.search_runs(
                experiment_names=["patient_compass_governance"],
                order_by=["start_time DESC"],
            )
            load_error = None
        except Exception as e:
            runs_df = None
            load_error = e

    col_btn, col_ts, _ = st.columns([1, 3, 6], vertical_alignment="center")
    with col_btn:
        def _start_gov_run():
            st.session_state["_gov_running"] = True

        st.button(
            "Run Now",
            key="run_governance_eval",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("_gov_running", False),
            on_click=_start_gov_run,
        )

    if st.session_state.get("_gov_running"):
        with st.spinner("Loading"):
            try:
                from eval.run_governance_eval import main as _run_gov
                _run_gov()
            except Exception as e:
                st.error(f"Eval failed: {e}")
        st.session_state["_gov_running"] = False
        st.rerun()
    with col_ts:
        if runs_df is not None and not runs_df.empty:
            last_run = runs_df.iloc[0]["start_time"]
            ts = last_run.strftime("%Y-%m-%d %H:%M UTC") if hasattr(last_run, "strftime") else str(last_run)[:16]
            st.caption(f"Last run: {ts}")
        else:
            st.caption("No runs found yet.")

    if load_error is not None:
        st.info(f"MLflow data unavailable.\n\n`{load_error}`")
        return
    if runs_df is None or runs_df.empty:
        return

    _descriptions = {
        "injection_accuracy":  ("Injection Detection",  "Percentage of prompt injection attempts correctly detected and blocked. Higher is better."),
        "pii_accuracy":        ("PII Detection",        "Percentage of messages containing PII (SSN, phone, email, credit card) correctly detected and blocked. Higher is better."),
        "leakage_accuracy":    ("Leakage Detection",    "Percentage of responses attempting to expose system prompt content correctly blocked. Higher is better."),
        "false_positive_rate": ("False Positive Rate",  "Percentage of legitimate patient messages incorrectly blocked by guardrails. Lower is better."),
    }

    latest = runs_df.iloc[0]
    table_rows = []
    for key, (label, description) in _descriptions.items():
        value = latest.get(f"metrics.{key}")
        if value is not None and not pd.isna(value):
            table_rows.append({"Metric": label, "Score": f"{value:.0%}", "Description": description})

    if table_rows:
        st.dataframe(
            pd.DataFrame(table_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "Metric":      st.column_config.TextColumn(width=180),
                "Score":       st.column_config.TextColumn(width=100),
                "Description": st.column_config.TextColumn(width=720),
            },
        )


def _build_performance_spans(ls, project_name: str, root_run) -> list[dict]:
    """Fetch LLM and tool child spans and return them as a chronological waterfall."""

    def _lat(r):
        return round((r.end_time - r.start_time).total_seconds(), 2) if r.start_time and r.end_time else None

    children = list(ls.list_runs(project_name=project_name, parent_run_id=root_run.id))
    rows = []

    # Planner LLM (one call, sets the task plan before agent cycles)
    for child in children:
        if child.name == "planner":
            for gc in ls.list_runs(project_name=project_name, parent_run_id=child.id):
                if gc.run_type == "llm":
                    rows.append({
                        "start": gc.start_time,
                        "component": "Planner LLM",
                        "latency": _lat(gc),
                        "prompt": getattr(gc, "prompt_tokens", None),
                        "completion": getattr(gc, "completion_tokens", None),
                        "is_llm": True,
                    })

    # Agent LLM runs — one per agent cycle (decides which tool to call next)
    agent_llm_runs = []
    for child in children:
        if child.name == "agent":
            for gc in ls.list_runs(project_name=project_name, parent_run_id=child.id):
                if gc.run_type == "llm":
                    agent_llm_runs.append(gc)
    agent_llm_runs.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0)

    # Tool runs
    tool_runs = []
    for child in children:
        if child.name == "tools":
            for gc in ls.list_runs(project_name=project_name, parent_run_id=child.id):
                if gc.run_type == "tool":
                    tool_runs.append(gc)
    tool_runs.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0)

    # Interleave: agent_llm[i] + tool[i]; last agent_llm has no paired tool (final response)
    for i, llm in enumerate(agent_llm_runs):
        label = (
            f"Agent LLM → {tool_runs[i].name}" if i < len(tool_runs)
            else "Agent LLM (final response)"
        )
        rows.append({
            "start": llm.start_time,
            "component": label,
            "latency": _lat(llm),
            "prompt": getattr(llm, "prompt_tokens", None),
            "completion": getattr(llm, "completion_tokens", None),
            "is_llm": True,
        })
        if i < len(tool_runs):
            tr = tool_runs[i]
            rows.append({
                "start": tr.start_time,
                "component": f"Tool: {tr.name}",
                "latency": _lat(tr),
                "prompt": None,
                "completion": None,
                "is_llm": False,
            })

    rows.sort(key=lambda r: r["start"].timestamp() if r.get("start") else 0)
    return rows


def _render_performance_table(spans: list[dict]):
    LLM_FLAG_S = 8  # LLM spans > 8s likely absorbed a Groq rate limit retry wait

    def _color(lat, is_llm=False):
        if lat is None:
            return ""
        if lat <= LATENCY_GOOD_S:
            return LATENCY_COLOR_GOOD
        if lat <= LATENCY_WARN_S:
            return LATENCY_COLOR_WARN
        return LATENCY_COLOR_BAD

    def _lat_str(lat, is_llm=False):
        if lat is None:
            return "—"
        flag = " ⚠️" if is_llm and lat > LLM_FLAG_S else ""
        return f"{lat:.2f}s{flag}"

    def _tok(val):
        return f"{val:,}" if val is not None else "—"

    total_lat = sum(s["latency"] for s in spans if s["latency"] is not None)
    total_color = (
        LATENCY_COLOR_GOOD if total_lat <= LATENCY_GOOD_S
        else LATENCY_COLOR_WARN if total_lat <= LATENCY_WARN_S
        else LATENCY_COLOR_BAD
    )
    total_prompt = sum(s["prompt"] for s in spans if s["prompt"] is not None) or None
    total_completion = sum(s["completion"] for s in spans if s["completion"] is not None) or None

    rows_html = ""
    for i, span in enumerate(spans, 1):
        lat = span["latency"]
        color = _color(lat, span["is_llm"])
        lat_style = f"color:{color};font-weight:bold;" if color else ""
        rows_html += (
            f"<tr>"
            f"<td style='padding:5px 10px;border-bottom:1px solid #e0e0e0;'>{i}</td>"
            f"<td style='padding:5px 10px;border-bottom:1px solid #e0e0e0;'>{span['component']}</td>"
            f"<td style='padding:5px 10px;border-bottom:1px solid #e0e0e0;{lat_style}'>{_lat_str(lat, span['is_llm'])}</td>"
            f"<td style='padding:5px 10px;border-bottom:1px solid #e0e0e0;text-align:right;'>{_tok(span['prompt'])}</td>"
            f"<td style='padding:5px 10px;border-bottom:1px solid #e0e0e0;text-align:right;'>{_tok(span['completion'])}</td>"
            f"</tr>"
        )

    rows_html += (
        f"<tr style='font-weight:bold;background-color:{HEADER_BG};'>"
        f"<td style='padding:6px 10px;'></td>"
        f"<td style='padding:6px 10px;'>Total</td>"
        f"<td style='padding:6px 10px;color:{total_color};'>{total_lat:.2f}s</td>"
        f"<td style='padding:6px 10px;text-align:right;'>{_tok(total_prompt)}</td>"
        f"<td style='padding:6px 10px;text-align:right;'>{_tok(total_completion)}</td>"
        f"</tr>"
    )

    st.markdown(
        f"<div style='overflow-x:auto;'>"
        f"<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
        f"<thead><tr style='background-color:{HEADER_BG};color:{TEXT};'>"
        f"<th style='padding:8px 10px;text-align:left;font-weight:600;'>Step</th>"
        f"<th style='padding:8px 10px;text-align:left;font-weight:600;'>Component</th>"
        f"<th style='padding:8px 10px;text-align:left;font-weight:600;'>Duration</th>"
        f"<th style='padding:8px 10px;text-align:right;font-weight:600;'>Prompt Tokens</th>"
        f"<th style='padding:8px 10px;text-align:right;font-weight:600;'>Completion Tokens</th>"
        f"</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>",
        unsafe_allow_html=True,
    )


@st.fragment
def _render_performance():
    from langsmith import Client as LangSmithClient

    st.markdown("### Performance")
    st.caption("Per-measured span latency and token breakdown for a single conversation turn. LangGraph overhead — state transitions, node routing, serialization between steps — is not included here.")

    project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    _, runs_clean = fetch_runs(project_name)

    if not runs_clean:
        st.caption("No traces found yet. Use the chat app to generate traces.")
        return

    run_map: dict[str, object] = {}
    for run in runs_clean:
        user_input = ""
        if run.inputs:
            messages = run.inputs.get("messages", [])
            if messages:
                last = messages[-1]
                user_input = (
                    last.get("content", "") if isinstance(last, dict)
                    else str(getattr(last, "content", ""))
                )[:80]
        time_str = run.start_time.strftime("%Y-%m-%d %H:%M") if run.start_time else "—"
        run_map[f"{time_str}  |  {user_input or '(no input)'}"] = run

    selected_label = st.selectbox("Conversation turn", options=list(run_map.keys()), key="perf_trace_selector")

    if st.session_state.get("_perf_label") != selected_label:
        st.session_state.pop("_perf_spans", None)

    def _start_analyze():
        st.session_state["_perf_analyzing"] = True

    col_btn, col_hint = st.columns([1, 9], vertical_alignment="center")
    with col_btn:
        st.button(
            "Analyze",
            key="perf_analyze",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get("_perf_analyzing", False),
            on_click=_start_analyze,
        )

    if st.session_state.get("_perf_analyzing"):
        with st.spinner("Loading"):
            try:
                ls = LangSmithClient()
                spans = _build_performance_spans(ls, project_name, run_map[selected_label])
                st.session_state["_perf_spans"] = spans
                st.session_state["_perf_label"] = selected_label
            except Exception as e:
                st.error(f"Could not load span data: {e}")
        st.session_state["_perf_analyzing"] = False
        st.rerun(scope="fragment")

    spans = st.session_state.get("_perf_spans")
    if spans is not None and st.session_state.get("_perf_label") == selected_label:
        if spans:
            _render_performance_table(spans)
            st.caption("⚠️ LLM spans marked ⚠️ likely include Groq rate limit retry waits — actual inference is typically under 2s.")
        else:
            st.caption("No span data found for this trace.")
    else:
        with col_hint:
            st.caption("Select a conversation turn and click Analyze to load the breakdown.")


def render_metrics_tab():
    @st.fragment(run_every=60)
    def _render_booking_performance():
        from datetime import datetime, timedelta, date
        today = date.today()
        st.markdown("### Appointment Bookings")
        st.caption(f"Real appointment data from the database — auto-refreshes every 60s · Last updated: {datetime.now().strftime('%H:%M:%S')}")
        with st.spinner("Loading"):
            all_appts = get_appointments()
        if not all_appts:
            st.info("No appointment data found.")
            return
        tomorrow = today + timedelta(days=1)
        total = sum(1 for a in all_appts if a.get("status") == "scheduled")
        today_count = sum(1 for a in all_appts if a.get("appointment_date") == today.isoformat() and a.get("status") == "scheduled")
        tomorrow_count = sum(1 for a in all_appts if a.get("appointment_date") == tomorrow.isoformat() and a.get("status") == "scheduled")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Upcoming Appointments", total)
        c2.metric("Appointments Today", today_count)
        c3.metric("Appointments Tomorrow", tomorrow_count)

    _render_booking_performance()

    st.divider()

    @st.fragment
    def _render_tool_usage_fragment():
        if not st.session_state.get("_tool_usage_loaded"):
            st.markdown("### Tool Usage Summary")
            def _start_load():
                st.session_state["_tool_usage_loaded"] = True
            st.button("Load", type="primary", key="load_tool_usage_btn", on_click=_start_load)
        else:
            _render_tool_usage()

    _render_tool_usage_fragment()

    st.divider()
    _render_performance()

    st.divider()
    _render_governance_eval()
