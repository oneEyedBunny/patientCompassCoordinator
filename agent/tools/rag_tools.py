import os
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
_index_path = os.path.join(os.path.dirname(__file__), "..", "..", "vector_store")
_vectorstore: FAISS | None = None


def _load_vectorstore() -> FAISS:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = FAISS.load_local(_index_path, _embeddings, allow_dangerous_deserialization=True)
    return _vectorstore


@tool
def retrieve_patient_context(query: str, config: RunnableConfig, patient_name: str = "") -> str:
    """Search a patient's indexed medical history for records semantically relevant to the query.
    Use when the user asks about past diagnoses, treatments, medications, or health patterns —
    OR when the user describes a symptom or health concern where their personal history may be
    relevant (e.g., existing conditions, current medications, prior treatments).
    Never use for appointment booking. Always pass the active patient's full name as patient_name."""
    if not patient_name or not patient_name.strip():
        patient_name = config.get("configurable", {}).get("patient_name", "")
    if not patient_name or not patient_name.strip():
        return "Cannot search medical history: patient name is not available."
    if not query or not query.strip():
        return "Cannot search medical history: query is required."
    try:
        vs = _load_vectorstore()
        # Prepend patient name so the embedding biases toward this patient's docs
        # before the post-hoc metadata filter is applied across fetch_k candidates
        full_query = f"{patient_name}: {query}"
        docs = vs.similarity_search(
            full_query,
            k=5,
            filter={"patient_name": patient_name, "doc_type": "record"},
            fetch_k=1000,
        )
        if not docs:
            return f"No relevant medical history found for {patient_name} matching this query."
        return "\n\n".join(doc.page_content for doc in docs)
    except Exception as e:
        print(f"[rag_tools] Vector store error: {e}")
        return "Vector store not available. Run scripts/build_vector_store.py first."
