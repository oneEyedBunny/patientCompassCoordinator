import os
import streamlit as st
import pandas as pd
from theme import PRIMARY, HEADER_BG, TEXT, LATENCY_GOOD_S, LATENCY_WARN_S, LATENCY_COLOR_GOOD, LATENCY_COLOR_WARN, LATENCY_COLOR_BAD
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


def _extract_agent_llm_runs(client, project_name: str, root_run) -> list:
    """
    Fetch the ChatGroq/LLM spans from agent nodes, sorted by execution order.
    Each agent cycle has one LLM call that decides which tool (if any) to invoke next.
    Matching agent_llm[i] → tool_call[i] gives the token cost of the decision to use that tool.
    """
    children = list(client.list_runs(project_name=project_name, parent_run_id=root_run.id))
    llm_runs = []
    for child in [c for c in children if c.name == "agent"]:
        grandchildren = list(client.list_runs(project_name=project_name, parent_run_id=child.id))
        llm_runs.extend(gc for gc in grandchildren if gc.run_type == "llm")
    return sorted(llm_runs, key=lambda r: r.start_time.timestamp() if r.start_time else 0)


def _render_agent_reasoning():
    st.subheader("Agent Reasoning")
    st.caption("Select a conversation turn to inspect its planning and tool call sequence. Expand a tool call to view agent prompt and completion token counts for that cycle.")

    _run_map = st.session_state.get("_ls_run_map", {})
    if not _run_map:
        st.caption("No traces available.")
        return

    st.markdown(f"""
<style>
[data-testid="stSelectbox"] > div > div {{
    border: 2px solid {PRIMARY} !important;
    border-radius: 6px;
}}
</style>
""", unsafe_allow_html=True)
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

    # Fetch per-tool latencies and per-agent-cycle token counts from LangSmith child spans
    try:
        from langsmith import Client as LangSmithClient
        _ls = LangSmithClient()
        _project = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
        child_tool_runs = _extract_tool_runs(_ls, _project, selected_run)
        agent_llm_runs = _extract_agent_llm_runs(_ls, _project, selected_run)

        latency_map: dict[str, list] = {}
        for tr in child_tool_runs:
            lat = round((tr.end_time - tr.start_time).total_seconds(), 2) if tr.start_time and tr.end_time else None
            latency_map.setdefault(tr.name, []).append(lat)

        for i, tc in enumerate(tool_calls):
            if tc["tool"] in latency_map and latency_map[tc["tool"]]:
                tc["latency"] = latency_map[tc["tool"]].pop(0)
            if i < len(agent_llm_runs):
                llm = agent_llm_runs[i]
                tc["tokens"] = {
                    "prompt": getattr(llm, "prompt_tokens", None),
                    "completion": getattr(llm, "completion_tokens", None),
                    "total": getattr(llm, "total_tokens", None),
                }
    except Exception:
        pass

    cols = st.columns([2, 2])

    with cols[0]:
        st.markdown("**Task Plan**")
        if plan_text:
            st.markdown(plan_text)
        else:
            st.caption("No plan generated (short or conversational message).")
    with cols[1]:
        st.markdown(f"**Tool Calls ({len(tool_calls)})**")
        if not tool_calls:
            st.caption("No tools fired for this conversation turn.")
        else:
            for i, tc in enumerate(tool_calls, 1):
                with st.expander(f"{i}. `{tc['tool']}`"):
                    tok = tc.get("tokens", {})
                    if tok.get("total") is not None:
                        st.caption(f"Agent tokens — prompt: {tok['prompt']:,} · completion: {tok['completion']:,} · total: {tok['total']:,}")
                    st.markdown("**Input:**")
                    st.json(tc["input"])
                    st.markdown("**Output:**")
                    st.text(tc["output"])


@st.fragment(run_every=60)
def _render_agent_logs_live(project_name: str):
    from datetime import datetime

    try:
        all_runs, clean_runs = fetch_runs(project_name)

        col_r, col_ts, _ = st.columns([1, 2, 4], vertical_alignment="center")
        with col_r:
            if st.button("🔄 Refresh All", key="refresh_agent_logs", type="primary"):
                # Clear the shared cache so both tabs get fresh data on next render
                fetch_runs.clear()
                st.session_state.pop("_ls_tool_usage", None)
        with col_ts:
            st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} · auto-refreshes every 60s")

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
                    if v <= LATENCY_GOOD_S:
                        return f"color: {LATENCY_COLOR_GOOD}; font-weight: bold"
                    if v <= LATENCY_WARN_S:
                        return f"color: {LATENCY_COLOR_WARN}; font-weight: bold"
                    return f"color: {LATENCY_COLOR_BAD}; font-weight: bold"
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

    except Exception as e:
        import traceback
        st.error(f"LangSmith error: `{e}`")
        with st.expander("Full traceback"):
            st.code(traceback.format_exc())


@st.fragment
def _render_agent_quality_scores():
    from datetime import datetime, timezone, timedelta
    from db.client import get_latest_eval_run

    st.divider()
    st.markdown("### Agent Quality Scores")
    st.caption("Scored against the last 10 real patient conversations pulled from LangSmith. Updates automatically 3x/day — trigger a manual run anytime from the GitHub Actions tab.")

    with st.spinner("Loading"):
        try:
            latest = get_latest_eval_run()
        except Exception as e:
            st.info(f"Could not load eval scores.\n\n`{e}`")
            return

    if latest is None:
        st.info("No eval runs found yet. Scores will appear here after the first automated run, or trigger one manually from the GitHub Actions tab.")
        return

    run_at = latest.get("run_at")
    if run_at:
        ts = run_at[:16].replace("T", " ") + " UTC"
        now = datetime.now(timezone.utc)
        next_run = next(
            (now.replace(hour=h, minute=0, second=0, microsecond=0)
             for h in [6, 13, 21] if now.replace(hour=h, minute=0, second=0, microsecond=0) > now),
            (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0),
        )
        st.caption(f"Last run: {ts} · Next run: {next_run.strftime('%Y-%m-%d %H:%M UTC')}")

    _metric_descriptions = {
        "avg_correctness":     "Did the agent accurately address the patient's request and take the right action?",
        "avg_relevance":       "Did the response stay on-topic and directly answer what the patient asked?",
        "avg_safety":          "Did the response include appropriate disclaimers, avoid prescribing, and recommend a physician when warranted?",
        "avg_task_completion": "Did the agent complete the requested action — booking, history retrieval, or answering the patient's question?",
    }

    table_rows = []
    for key, description in _metric_descriptions.items():
        value = latest.get(key)
        if value is not None:
            table_rows.append({
                "Metric": key.replace("_", " ").title().replace("Avg ", "Average "),
                "Score": f"{value:.0%}",
                "Description": description,
            })

    if table_rows:
        st.dataframe(
            pd.DataFrame(table_rows),
            width="stretch",
            hide_index=True,
            column_config={
                "Metric":      st.column_config.TextColumn(width=150),
                "Score":       st.column_config.TextColumn(width=100),
                "Description": st.column_config.TextColumn(width=750),
            },
        )


def render_insights_tab():
    _project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    _render_agent_logs_live(_project_name)
    _render_agent_quality_scores()
