from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from agent.state import AgentState
from agent.prompts import SYSTEM_PROMPT
from agent.llm import llm
from agent.tools.appointment_tools import search_doctor_availability, book_appointment
from agent.tools.patient_tools import get_patient_history, update_patient_record
from agent.tools.search_tools import search_medical_info
from agent.tools.rag_tools import retrieve_patient_context

load_dotenv()

tools = [
    search_doctor_availability,
    book_appointment,
    get_patient_history,
    update_patient_record,
    search_medical_info,
    retrieve_patient_context,
]

_llm = llm.bind_tools(tools)
_tool_node = ToolNode(tools)


def agent_node(state: AgentState) -> AgentState:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = _llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", _tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


graph = build_graph()
