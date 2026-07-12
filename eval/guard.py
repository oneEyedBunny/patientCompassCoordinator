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


def get_last_agent_activity(since: datetime | None) -> bool:
    """Return True if any patient conversation traces exist after `since`.
    Passes the timestamp directly to LangSmith to avoid relying on list_runs ordering."""
    project_name = os.environ.get("LANGCHAIN_PROJECT", "patient-compass-coordinator")
    client = LangSmithClient()
    runs = list(client.list_runs(
        project_name=project_name,
        filter="eq(is_root, true)",
        start_time=since,
        limit=1,
    ))
    return len(runs) > 0


def should_run_eval() -> bool:
    """Return True if there are new agent conversations since the last eval run."""
    last_eval = get_last_eval_run()

    if last_eval is None:
        return True

    return get_last_agent_activity(since=last_eval)
