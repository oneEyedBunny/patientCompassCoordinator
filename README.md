# patientCompassCoordinator

## Project Overview

An Agentic Healthcare Assistant that functions as a virtual medical assistant. Patients can book appointments, retrieve medical histories, and search for disease information via a conversational chat interface. Staff can monitor appointments, patient records, and agent performance via a separate dashboard.

## Final Stack

| Layer | Tool |
|---|---|
| Agent orchestration | LangGraph + SqliteSaver (persistent memory) |
| LLM (agent / planning) | Groq `llama-3.3-70b-versatile` |
| LLM (fast subtasks) | Groq `llama-3.1-8b-instant` |
| Database | Supabase (PostgreSQL) |
| Vector store | FAISS (committed to repo) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Web / medical search | Serper + NLM E-utilities (Medline, free) |
| Tracing | LangSmith |
| Eval metrics | MLflow |
| UI | Streamlit (2 separate apps) |
| Deployment | Streamlit Community Cloud |
| Patient data | Kaggle `prasad22/healthcare-dataset` |

## Running the Apps

Both apps can run simultaneously on different ports:

```bash
# Patient chat (default port 8501)
streamlit run app_chat.py

# Staff dashboard (port 8502 — avoids collision with chat app)
streamlit run app_dashboard.py --server.port 8502
```

## App 1 — Patient Chat Interface (`app_chat.py`)

A conversational chat interface for patients. Load a patient by name to begin a session. The agent can:
- Retrieve and summarize medical history
- Search for available doctor appointments by specialty and date
- Book appointments and confirm with the patient before executing
- Search for medical information via Serper + PubMed (with physician disclaimer)
- Retrieve relevant patient context from the FAISS knowledge base

Persistent memory is maintained per patient via LangGraph SqliteSaver (thread_id = patient_id). An Agent Reasoning expander shows the task plan and all tool calls made during each response.

## App 2 — Staff Dashboard (`app_dashboard.py`)

A staff-facing interface for monitoring and managing the system across 5 tabs:

**Tab 1 — Appointments:** View all appointments with filtering by doctor, date, and status. Staff can mark appointments complete or cancel them directly from the table.

**Tab 2 — Patient Records:** Search for a patient by name to view their full profile and medical records history. Includes an Add Record form for staff to write diagnosis and treatment notes without going through the chat agent.

**Tab 3 — Medical Search:** Direct access to the medical search tool. Staff can query conditions or treatments and get the same Serper + PubMed results the agent uses, without starting a patient conversation.

**Tab 4 — Metrics:** Displays MLflow eval run data including booking success rate, average response latency, and tool call distribution as charts and metric cards.

**Tab 5 — Agent Logs:** Shows the last 20 LangSmith traces with timestamp, user intent, tools fired, latency, and pass/fail status for auditing agent behavior across sessions.