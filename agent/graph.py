import sqlite3
from datetime import date, timedelta
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.state import AgentState
from agent.prompts import SYSTEM_PROMPT, PLANNER_PROMPT
from agent.llm import llm, fast_llm
from agent.tools.appointment_tools import search_doctor_availability, book_appointment, get_patient_appointments
from agent.tools.patient_tools import get_patient_history, update_patient_record
from agent.tools.search_tools import search_medical_info
from agent.tools.rag_tools import retrieve_patient_context

load_dotenv()

tools = [
    search_doctor_availability,
    book_appointment,
    get_patient_appointments,
    get_patient_history,
    update_patient_record,
    search_medical_info,
    retrieve_patient_context,
]

_llm = llm.bind_tools(tools)
_tool_node = ToolNode(tools)


_CONVERSATIONAL_REPLIES = {"yes", "no", "ok", "okay", "sure", "confirm", "book it", "book", "cancel", "thanks", "thank you"}


def planner_node(state: AgentState) -> AgentState:
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if not last_human:
        return {}

    text = last_human.content.strip()
    if len(text) < 30 or text.lower() in _CONVERSATIONAL_REPLIES:
        return {"plan": None}

    prompt = PLANNER_PROMPT.format(user_input=text)
    plan = fast_llm.invoke([HumanMessage(content=prompt)])
    return {"plan": plan.content}


def agent_node(state: AgentState) -> AgentState:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    system_content = SYSTEM_PROMPT + f"\n\nToday's date is {today.isoformat()}. Tomorrow is {tomorrow.isoformat()}."
    if state.get("patient_name"):
        system_content += f"\n\nThe current user is patient: {state['patient_name']}."
    if state.get("patient_context"):
        system_content += f"\n\nPatient context already retrieved:\n{state['patient_context']}\n\nUse this context to answer questions without calling get_patient_history unless the user needs updated records."
    if state.get("plan"):
        system_content += f"\n\nTask plan to execute:\n{state['plan']}"
    messages = [SystemMessage(content=system_content)] + state["messages"]
    response = _llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


_conn = sqlite3.connect("memory.sqlite", check_same_thread=False)


def build_graph() -> CompiledStateGraph:
    checkpointer = SqliteSaver(_conn)
    g = StateGraph(AgentState)
    g.add_node("planner", planner_node)
    g.add_node("agent", agent_node)
    g.add_node("tools", _tool_node)
    g.set_entry_point("planner")
    g.add_edge("planner", "agent")
    g.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=checkpointer)


graph = build_graph()
