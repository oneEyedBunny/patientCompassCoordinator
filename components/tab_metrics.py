import os
import streamlit as st
import pandas as pd
from db.client import get_appointments
from services.telemetry import fetch_runs
from theme import PRIMARY, HEADER_BG, TEXT


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
        with st.spinner("Loading tool usage data..."):
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
        col1, col2 = st.columns([2, 1])
        with col1:
            st.altair_chart(chart, width="stretch")
        with col2:
            st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.caption("No tool runs found in LangSmith for these traces.")


def render_metrics_tab():
    st.subheader("Eval Metrics")

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
        total = sum(1 for a in all_appts if a.get("status") == "scheduled")
        today_count = sum(1 for a in all_appts if a.get("appointment_date") == today.isoformat() and a.get("status") == "scheduled")
        tomorrow_count = sum(1 for a in all_appts if a.get("appointment_date") == tomorrow.isoformat() and a.get("status") == "scheduled")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Upcoming Appointments", total)
        c2.metric("Appointments Today", today_count)
        c3.metric("Appointments Tomorrow", tomorrow_count)

    _render_booking_performance()

    st.divider()

    @st.fragment(run_every=60)
    def _render_tool_usage_fragment():
        _render_tool_usage()

    _render_tool_usage_fragment()
