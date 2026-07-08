# Patient Compass Coordinator

> **Capstone project** — built for the University of Michigan Applied Generative AI Specialization. Some conventions typical of production codebases (comprehensive test coverage, CI/CD pipelines, secrets management beyond `.env`, full error monitoring, etc.) are intentionally out of scope.

## Project Overview

An Agentic Healthcare Assistant that functions as a virtual medical assistant. Patients can book appointments, retrieve medical histories, and search for disease information via a conversational chat interface. Staff can monitor appointments, patient records, and agent performance via a separate dashboard.

The system is designed for two distinct user roles. **Patients** interact through a clean, conversational UI with no exposure to underlying agent mechanics. **Operators (staff)** have a dedicated dashboard that provides full visibility into system behavior — including appointment management, live tool usage telemetry, agent planning breakdowns, and eval metrics — giving operators the observability needed to monitor and audit the agent without touching the patient-facing interface.

## Live Apps

| App | URL |
|---|---|
| Patient Chat | [patient-compass-coordinator.streamlit.app](https://patient-compass-coordinator.streamlit.app) |
| Staff Dashboard | [patient-compass-dashboard.streamlit.app](https://patient-compass-dashboard.streamlit.app) |

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

## Running the Apps locally

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

Persistent memory is maintained per patient via LangGraph SqliteSaver (thread_id = patient_id). Planning breakdowns and tool call traces are available in the Staff Dashboard (Tab 4 — Agent Insights).

## App 2 — Staff Dashboard (`app_dashboard.py`)

A staff-facing interface for monitoring and managing the system across 5 tabs:

**Tab 1 — Appointments:** View all appointments with filtering by doctor, date, and status. Staff can mark appointments complete or cancel them directly from the table.

**Tab 2 — Patient Records:** Search for a patient by name to view their full profile and medical records history. Includes an Add Record form for staff to write diagnosis and treatment notes without going through the chat agent.

**Tab 3 — Medical Help:** Direct access to the medical search tool. Staff can query conditions or treatments and get the same Serper + PubMed results the agent uses, without starting a patient conversation.

**Tab 4 — Agent Insights:** Shows live tool usage (call count and success rate per tool from LangSmith), the last 20 session traces, and an Agent Reasoning detail view — select any trace to inspect the planner's task breakdown and the full tool call sequence with inputs and outputs.

**Tab 5 — Metrics:** Displays live booking performance (total, upcoming, completed, cancelled, completion rate) pulled directly from the database, plus MLflow eval quality scores (correctness, relevance, tool accuracy) and run history. Populated by running `python eval/run_eval.py`.

## AI Governance (Phase 6)

Input and output guardrails are applied to every patient chat message via `agent/guardrails.py`.

**Input guardrails** (run before the agent):
- PII detection — Presidio Analyzer (`en_core_web_sm`) with regex supplemental for SSN, phone, email, and credit card
- Injection detection — regex patterns blocking prompt injection and instruction-override attempts

**Output guardrails** (run before the response is displayed):
- Leakage detection — regex patterns catching system prompt or instruction disclosure

Blocked inputs return a user-facing warning and abort execution. Blocked outputs are replaced with a safe fallback message.

**One-time setup:**
```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_sm
```

## Evaluation

Run the agent quality eval harness to populate dashboard Tab 5 — Metrics:

```bash
python eval/run_eval.py
```

Pulls the last 20 real patient conversations from LangSmith and scores each with DeepEval G-Eval (correctness, relevance, safety) using a Groq-backed judge — no static test cases, no OpenAI key required. Aggregate metrics are logged to MLflow. Requires at least one real chat session to have occurred first.

Run the governance eval harness independently (no LLM calls — fully deterministic):

```bash
python eval/run_governance_eval.py
```

Runs 17 test cases (injection, PII, leakage, and legitimate inputs) through the guardrail functions and logs accuracy, per-category accuracy, and false positive rate to MLflow under the `patient_compass_governance` experiment.