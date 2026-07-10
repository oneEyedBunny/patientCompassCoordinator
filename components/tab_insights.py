import os
import streamlit as st
import pandas as pd
from theme import PRIMARY, HEADER_BG, TEXT
from services.telemetry import fetch_runs


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


def _render_agent_reasoning():
    st.subheader("Agent Reasoning")
    st.caption("Select a conversation turn to inspect its planning and tool call sequence.")

    _run_map = st.session_state.get("_ls_run_map", {})
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
    all_messages = outputs.get("messages", [])
    # Scope to this turn only: find the last human message and take everything after it.
    # run.inputs only contains the new human message (not full prior state), so we can't
    # use len(inputs["messages"]) as a prior-state offset.
    last_human_idx = next(
        (i for i in range(len(all_messages) - 1, -1, -1)
         if isinstance(all_messages[i], dict) and all_messages[i].get("type") == "human"),
        None,
    )
    messages = all_messages[last_human_idx + 1:] if last_human_idx is not None else all_messages

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
    from datetime import datetime

    try:
        all_runs, clean_runs = fetch_runs(project_name)

        col_r, col_ts, _ = st.columns([1, 3, 3])
        with col_r:
            if st.button("🔄 Refresh All", key="refresh_agent_logs"):
                # Clear the shared cache so both tabs get fresh data on next render
                fetch_runs.clear()
                st.session_state.pop("_ls_tool_usage", None)
        with col_ts:
            st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} · auto-refreshes every 30s")

        st.subheader("Agent Logs")
        st.caption("LangGraph traces from the patient chat app.")

        if not all_runs:
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

            rows = []
            for run in all_runs:
                latency, user_input = _extract_run_meta(run)
                rows.append({
                    "Time": run.start_time.strftime("%Y-%m-%d %H:%M:%S") if run.start_time else "—",
                    "Input": user_input or "—",
                    "Latency (s)": latency,
                    "Run ID": str(run.id)[:8],
                    "Status": run.status or "—",
                    "Error Message": run.error[:200] if run.error else "—",
                })

            def _style_status(val):
                if val == "success":
                    return "color: #2e7d32; font-weight: bold"
                if val == "error":
                    return "color: #c62828; font-weight: bold"
                return ""

            def _style_latency(val):
                try:
                    v = float(val)
                    if v < 10:
                        return "color: #2e7d32; font-weight: bold"
                    if v < 30:
                        return "color: #e65100; font-weight: bold"
                    return "color: #c62828; font-weight: bold"
                except (TypeError, ValueError):
                    return ""

            styled_logs = (
                pd.DataFrame(rows)
                .style
                .format({"Latency (s)": lambda x: f"{x:.2f}" if x is not None else "—"})
                .map(_style_status, subset=["Status"])
                .map(_style_latency, subset=["Latency (s)"])
            )
            st.dataframe(styled_logs, width="stretch")

            # Build run_map for Agent Reasoning dropdown — UI state, scoped to this tab
            run_map: dict[str, object] = {}
            for run in clean_runs:
                _, user_input = _extract_run_meta(run)
                time_str = run.start_time.strftime("%Y-%m-%d %H:%M") if run.start_time else "—"
                label = f"{time_str}  |  {user_input[:120] or '(no input)'}"
                run_map[label] = run
            st.session_state._ls_run_map = run_map

        st.divider()
        _render_agent_reasoning()

        st.divider()
        st.markdown("### Agent Quality Scores")
        st.caption("Scored against the last 20 real patient conversations pulled from LangSmith.")
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

    except Exception as e:
        import traceback
        st.error(f"LangSmith error: `{e}`")
        with st.expander("Full traceback"):
            st.code(traceback.format_exc())


def render_insights_tab():
    _project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    _render_agent_logs_live(_project_name)
