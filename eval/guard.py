"""
Guards the automated eval run. Call should_run_eval() before running the
eval harness to avoid scoring stale traces when the app hasn't been used.
"""

import os
from datetime import datetime
from langsmith import Client as LangSmithClient
from db.client import get_last_eval_timestamp


def get_last_eval_run() -> datetime | None:
    """Return the UTC datetime of the most recent eval run, or None."""
    return get_last_eval_timestamp()


def get_last_agent_activity() -> datetime | None:
    """Return the UTC datetime of the most recent patient conversation trace, or None."""
    project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    client = LangSmithClient()
    runs = list(client.list_runs(
        project_name=project_name,
        filter="eq(is_root, true)",
        limit=1,
    ))
    if not runs:
        return None
    return runs[0].start_time


def should_run_eval() -> bool:
    """Return True if there are new agent conversations since the last eval run."""
    last_eval = get_last_eval_run()
    last_activity = get_last_agent_activity()

    if last_eval is None:
        return True
    if last_activity is None:
        return False
    return last_activity > last_eval
