import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

from agent.graph import graph
from db.client import get_patient_by_name, get_medical_records

st.set_page_config(page_title="Patient Compass Coordinator", page_icon="🏥", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏥 Patient Compass")
    st.divider()

    if "patient_name" not in st.session_state:
        st.info("👇 **Step 1:** Enter the patient name below to get started.")

    patient_name_input = st.text_input("Patient Name", placeholder="e.g. Danielle Forbes")

    if st.button("Submit", use_container_width=True, type="primary"):
        name = patient_name_input.strip()
        if not name:
            st.warning("Please enter a patient name.")
        else:
            patient = get_patient_by_name(name)
            if not patient:
                st.error(f"Patient '{name}' not found.")
            else:
                records = get_medical_records(patient["id"])
                context_lines = [
                    f"Patient on file: {patient['name']}, Age {patient['age']}, {patient['gender']}, Blood type {patient['blood_type']}.",
                    f"Primary condition: {patient['medical_condition']}. Medication: {patient['medication']}. Test results: {patient['test_results']}.",
                ]
                if records:
                    context_lines.append("Medical records:")
                    for r in records:
                        context_lines.append(f"  [{r['record_date']}] {r['diagnosis']} — {r['treatment']}")
                else:
                    context_lines.append("No additional medical records on file.")

                st.session_state.patient_name = patient["name"]
                st.session_state.patient_id = patient["id"]
                st.session_state.patient_context = "\n".join(context_lines)
                st.session_state.messages = []
                st.session_state.tool_calls_log = []
                st.session_state.last_plan = None
                st.success(f"✓ Loaded: {patient['name']}")

    if "patient_name" in st.session_state:
        st.divider()
        st.markdown(f"**Active Patient**")
        st.markdown(f"### {st.session_state.patient_name}")
        if st.button("Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.tool_calls_log = []
            st.session_state.last_plan = None
            st.rerun()

# ── Session state defaults ────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "tool_calls_log" not in st.session_state:
    st.session_state.tool_calls_log = []
if "last_plan" not in st.session_state:
    st.session_state.last_plan = None

# ── Main area ─────────────────────────────────────────────────────────────────

st.markdown("## Patient Compass Coordinator")
st.caption("Virtual medical assistant — for informational use only.")

if "patient_name" not in st.session_state:
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Welcome")
        st.markdown(
            "To get started, enter a patient name in the **sidebar on the left** and click **Submit**. "
            "Once loaded, you can ask about medical history, search for doctors, book appointments, and more."
        )
        st.markdown("**What I can help with:**")
        st.markdown("- 📋 Retrieve and summarize medical history")
        st.markdown("- 📅 Search for available appointments")
        st.markdown("- 🗓️ Book appointments with specialists")
        st.markdown("- 🔍 Search for medical information")
    st.stop()

# ── Chat history ──────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("You", avatar="👤"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage) and msg.content:
        with st.chat_message("PCC", avatar="🏥"):
            st.markdown(msg.content)

if st.session_state.last_plan or st.session_state.tool_calls_log:
    with st.expander("Agent Reasoning", expanded=False):
        if st.session_state.last_plan:
            st.markdown("**Task Plan:**")
            st.markdown(st.session_state.last_plan)
            st.divider()
        for entry in st.session_state.tool_calls_log:
            st.markdown(f"**Tool:** `{entry['tool']}`")
            st.markdown(f"**Input:** {entry['input']}")
            st.markdown(f"**Output:** {entry['output']}")
            st.divider()

# ── Chat input ────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask me about your history, appointments, or health questions..."):
    user_message = HumanMessage(content=prompt)
    st.session_state.messages.append(user_message)
    # Track length after appending so we can slice out only the agent's new replies
    pre_invoke_count = len(st.session_state.messages)

    with st.chat_message("You", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("PCC", avatar="🏥"):
        with st.spinner("Thinking..."):
            try:
                result = graph.invoke(
                    {
                        "messages": [user_message],
                        "patient_name": st.session_state.get("patient_name"),
                        "patient_context": st.session_state.get("patient_context"),
                    },
                    config={
                        "recursion_limit": 40,
                        "configurable": {"thread_id": st.session_state.get("patient_id", "default")},
                    },
                )
            except Exception:
                st.error("I ran into an issue processing your request. Please try rephrasing or breaking it into smaller steps.")
                st.session_state.messages.pop()
                st.stop()

        st.session_state.last_plan = result.get("plan")
        all_messages = result["messages"]
        # Sync session state from checkpoint so pre_invoke_count stays accurate next turn
        st.session_state.messages = all_messages
        new_messages = all_messages[pre_invoke_count:]

        tool_entries = []
        final_response = ""

        for msg in new_messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_entries.append({
                        "tool": tc["name"],
                        "input": tc["args"],
                        "output": "",
                    })
            elif hasattr(msg, "name") and msg.name:
                if tool_entries:
                    tool_entries[-1]["output"] = msg.content
            elif msg.content:
                final_response = msg.content

        st.session_state.tool_calls_log.extend(tool_entries)

        st.markdown(final_response)
