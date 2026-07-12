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

> **Note:** Streamlit Community Cloud apps sleep after 12 hours of inactivity. If you see a sleep screen, click "Yes, get this app back up!" — it takes about 60 seconds to restart.

## Final Stack

| Layer | Tool |
|---|---|
| Agent orchestration | LangGraph + SqliteSaver (persistent memory) |
| LLM (agent + planning) | Groq `openai/gpt-oss-120b` |
| LLM (eval judge) | Groq `qwen/qwen3.6-27b` |
| Database | Supabase (PostgreSQL) |
| Vector store | FAISS (committed to repo) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Web / medical search | Serper + NLM E-utilities (Medline, free) |
| Tracing | LangSmith |
| Eval metric tracking | MLflow (local SQLite, logged via `eval/run_eval.py`, surfaced in Staff Dashboard) |
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
- Search for available doctor appointments by specialty and date, and book confirmed slots
- Retrieve and summarize medical history from Supabase
- Retrieve contextually relevant patient history via RAG (FAISS vector store + HuggingFace `all-MiniLM-L6-v2` embeddings)
- Search for medical information via Serper + PubMed (with physician disclaimer appended)

Each message is routed through a LangGraph planner that decomposes the request into tool steps before execution. Conversation memory is persisted per patient via SqliteSaver (thread_id = patient_id). Planning breakdowns and tool call traces are visible in the Staff Dashboard (Tab 4 — Agent Insights).

## App 2 — Staff Dashboard (`app_dashboard.py`)

A staff-facing interface for monitoring and managing the system across 5 tabs:

**Tab 1 — Appointments:** View all appointments with filtering by doctor, date, and status. Staff can mark appointments complete or cancel them directly from the table.

**Tab 2 — Patient Records:** Search for a patient by name to view their full profile and medical records history. Includes an Add Record form for staff to write diagnosis and treatment notes without going through the chat agent.

**Tab 3 — Medical Help:** Direct access to the medical search tool. Staff can query conditions or treatments and get the same Serper + PubMed results the agent uses, without starting a patient conversation.

**Tab 4 — Agent Insights:** Live agent log of the last 50 LangSmith traces with latency and status. Agent Reasoning detail view lets you select any trace to inspect the planner's task breakdown and the full tool call sequence with inputs and outputs. Agent Quality Scores (MLflow) display the latest eval run metrics — updated automatically 3x/day via GitHub Actions.

**Tab 5 — Metrics:** Live appointment booking performance (upcoming, today, tomorrow) pulled directly from Supabase. Tool Usage Summary shows aggregated call counts, success rates, and latency per tool across the last 50 traces.

## AI Governance

Input and output guardrails are applied to every patient chat message via `agent/guardrails.py`.

**Input guardrails** (run before the agent):
- PII detection — Presidio Analyzer (`en_core_web_sm`) with regex supplemental for SSN, phone, email, and credit card
- Injection detection — regex patterns blocking prompt injection and instruction-override attempts

**Output guardrails** (run before the response is displayed):
- Leakage detection — regex patterns catching system prompt or instruction disclosure

Blocked inputs return a user-facing warning and abort execution. Blocked outputs are replaced with a safe fallback message.

## Evaluation

Agent quality evaluation runs automatically 3 times per day via GitHub Actions (`.github/workflows/eval_schedule.yml`) and can be triggered manually from the **Actions tab** in the GitHub repository. Each run pulls the last 20 real patient conversations from LangSmith, scores them with DeepEval G-Eval (correctness, relevance, safety, task completion), and logs results to both MLflow and Supabase (`eval_runs` table). The eval only runs if new conversations have occurred since the last run.

To run manually from the terminal:

```bash
python eval/run_eval.py          # agent quality — requires real chat sessions in LangSmith
python eval/run_governance_eval.py  # guardrail accuracy — fully deterministic, no LLM calls
```

Agent quality scores surface in the Staff Dashboard under Tab 4 — Agent Insights. The eval judge uses `qwen/qwen3.6-27b` via Groq, keeping it on a separate token budget from the main agent.

> **Note on database schema:** All Supabase tables were created manually via the SQL editor. Row Level Security (RLS) is disabled on all tables — acceptable for a server-side capstone with no public auth, but not production-standard. A production system would enable RLS with appropriate policies and use a migration framework (Alembic, Flyway, etc.) for schema versioning.