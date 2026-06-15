from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(dict):
    messages: Annotated[list[BaseMessage], add_messages]
    patient_id: str | None
    patient_name: str | None
    patient_context: str | None
    plan: str | None
