# patientCompassCoordinator

## Project Overview

An Agentic Healthcare Assistant that functions as a virtual medical assistant. Patients can book appointments, retrieve medical histories, and search for disease information via a conversational chat interface. Staff can monitor appointments, patient records, and agent performance via a separate dashboard.

## Final Stack

| Layer | Tool |
|---|---|
| Agent orchestration | LangGraph |
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