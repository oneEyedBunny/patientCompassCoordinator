import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

from agent.graph import graph, _conn
from agent.tools.rag_tools import _load_vectorstore
from db.client import get_patient_by_name, get_medical_records

# Pre-warm the FAISS index and embedding model so the first patient
# message doesn't silently stall while PyTorch initializes.
_load_vectorstore()

st.set_page_config(page_title="Patient Compass Coordinator", page_icon="🏥", layout="wide")

st.markdown("""
<style>
/* Submit / primary buttons → indigo */
div.stButton > button[kind="primary"] {
    background-color: #4f46e5 !important;
    border-color: #4f46e5 !important;
    color: white !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #4338ca !important;
    border-color: #4338ca !important;
}
/* Chat history container border → teal */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 2px solid #0d9488 !important;
    border-radius: 10px !important;
}
/* Chat input bar → teal */
div[data-testid="stChatInput"] > div {
    border: 2px solid #0d9488 !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

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

                first_name = patient["name"].split()[0]
                st.session_state.patient_name = patient["name"]
                st.session_state.patient_id = patient["id"]
                st.session_state.patient_context = "\n".join(context_lines)
                st.session_state.greeting = f"Hello {first_name}, how can I help you today?"
                st.session_state.messages = []
                st.success(f"✓ Loaded: {patient['name']}")

    if "patient_name" in st.session_state:
        st.divider()
        st.markdown(f"**Active Patient**")
        st.markdown(f"### {st.session_state.patient_name}")
        if st.button("Clear Conversation", use_container_width=True):
            thread_id = st.session_state.get("patient_id", "default")
            try:
                _conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
                _conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
                _conn.commit()
            except Exception:
                pass
            st.session_state.messages = []
            st.rerun()

# ── Session state defaults ────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "greeting" not in st.session_state:
    st.session_state.greeting = None

# ── Main area ─────────────────────────────────────────────────────────────────

st.markdown('<h2 style="color: #0d9488;">Patient Compass Coordinator</h2>', unsafe_allow_html=True)
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

with st.container(border=True):
    if st.session_state.get("greeting"):
        with st.chat_message("PCC", avatar="🏥"):
            st.markdown(st.session_state.greeting)

    for msg in st.session_state.messages:
        if isinstance(msg, HumanMessage):
            with st.chat_message("You", avatar="👤"):
                st.markdown(msg.content)
        elif isinstance(msg, AIMessage) and msg.content:
            with st.chat_message("PCC", avatar="🏥"):
                st.markdown(msg.content)

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
            except Exception as e:
                import traceback
                traceback.print_exc()
                err_str = str(e)
                if "rate_limit_exceeded" in err_str or "429" in err_str:
                    import re
                    wait = re.search(r"try again in ([\d\w.]+)", err_str)
                    wait_msg = f" Please try again in {wait.group(1)}." if wait else " Please try again in a few minutes."
                    st.warning(f"The AI service is temporarily rate limited.{wait_msg}")
                else:
                    st.error("I ran into an issue processing your request. Please try rephrasing or breaking it into smaller steps.")
                print(f"[app_chat] graph.invoke error: {e}")
                st.session_state.messages.pop()
                st.stop()

        all_messages = result["messages"]
        # Sync session state from checkpoint so pre_invoke_count stays accurate next turn
        st.session_state.messages = all_messages
        new_messages = all_messages[pre_invoke_count:]

        final_response = next(
            (msg.content for msg in reversed(new_messages) if isinstance(msg, AIMessage) and msg.content),
            ""
        )
        st.markdown(final_response)
