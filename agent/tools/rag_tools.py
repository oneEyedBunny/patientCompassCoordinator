import os
from langchain_core.tools import tool
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
def retrieve_patient_context(patient_name: str, query: str) -> str:
    """Search a patient's indexed medical history for records semantically relevant to the query.
    Use when the user asks about past diagnoses, treatments, ongoing conditions, medications, or health patterns.
    Always pass the active patient's full name as patient_name."""
    try:
        vs = _load_vectorstore()
        # fetch_k is large to ensure all of this patient's docs are candidates before filtering
        docs = vs.similarity_search(
            query,
            k=4,
            filter={"patient_name": patient_name},
            fetch_k=1000,
        )
        if not docs:
            return f"No relevant medical history found for {patient_name} matching this query."
        return "\n\n".join(doc.page_content for doc in docs)
    except Exception as e:
        print(f"[rag_tools] Vector store error: {e}")
        return "Vector store not available. Run scripts/build_vector_store.py first."
