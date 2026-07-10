import streamlit as st
from langsmith import Client as LangSmithClient


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


@st.cache_data(ttl=60)
def fetch_runs(project_name: str) -> tuple[list, list]:
    """Fetch root runs from LangSmith. Returns (all_runs, clean_runs).

    all_runs: up to 50 most recent root runs, including errors (used for the Agent Logs table)
    clean_runs: up to 20 valid patient conversation runs — no rate limit errors, chain type,
                has a human message (used for Agent Reasoning and Tool Usage)

    Cached for 60 seconds so both tabs can call this independently without hammering the API.
    """
    client = LangSmithClient()
    all_runs: list = []
    clean_runs: list = []
    checked = 0

    for run in client.list_runs(project_name=project_name, filter="eq(is_root, true)"):
        checked += 1
        if checked > 500:
            break
        if len(all_runs) < 50:
            all_runs.append(run)
        if len(clean_runs) < 20 and _is_clean(run):
            clean_runs.append(run)
        if len(clean_runs) >= 20 and len(all_runs) >= 50:
            break

    all_runs.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0, reverse=True)
    clean_runs.sort(key=lambda r: r.start_time.timestamp() if r.start_time else 0, reverse=True)

    return all_runs, clean_runs
