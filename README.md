# Patient Compass Coordinator

## Project Overview

An Agentic Healthcare Assistant that functions as a virtual medical assistant. Patients can book appointments, retrieve medical histories, and search for disease information via a conversational chat interface. Staff can monitor appointments, patient records, and agent performance via a separate dashboard.

The system is designed for two distinct user roles. **Patients** interact through a clean, conversational UI with no exposure to underlying agent mechanics. **Operators (staff)** have a dedicated dashboard that provides full visibility into system behavior — including appointment management, live tool usage telemetry, agent planning breakdowns, and eval metrics — giving operators the observability needed to monitor and audit the agent without touching the patient-facing interface.

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
| UI | Streamlit (2 separate apps- Patient side & Operator side) |
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

Persistent memory is maintained per patient via LangGraph SqliteSaver (thread_id = patient_id). Planning breakdowns and tool call traces are available in the Staff Dashboard (Tab 5 — Agent Reasoning).

## App 2 — Staff Dashboard (`app_dashboard.py`)

A staff-facing interface for monitoring and managing the system across 5 tabs:

**Tab 1 — Appointments:** View all appointments with filtering by doctor, date, and status. Staff can mark appointments complete or cancel them directly from the table.

**Tab 2 — Patient Records:** Search for a patient by name to view their full profile and medical records history. Includes an Add Record form for staff to write diagnosis and treatment notes without going through the chat agent.

**Tab 3 — Medical Search:** Direct access to the medical search tool. Staff can query conditions or treatments and get the same Serper + PubMed results the agent uses, without starting a patient conversation.

**Tab 4 — Metrics:** Displays MLflow eval run data as quality metric cards (correctness, relevance, tool accuracy, booking success rate, latency) and a tool call distribution bar chart. Populated by running `python eval/run_eval.py`.

**Tab 5 — Agent Logs:** Shows a live tool usage summary (call count and success rate per tool from LangSmith), the last 20 session traces, and an Agent Reasoning detail view — select any trace to inspect the planner's task breakdown and the full tool call sequence with inputs and outputs.

## Evaluation

Run the agent quality eval harness before deployment to populate dashboard Tab 4:

```bash
python eval/run_eval.py
```

Runs 15 test cases through the live agent, scores each with an LLM-as-judge (correctness, relevance, tool accuracy), and logs aggregate metrics to MLflow.