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
def retrieve_patient_context(query: str) -> str:
    """Retrieve the most relevant patient summaries from the vector store to provide context for a query."""
    try:
        vs = _load_vectorstore()
        docs = vs.similarity_search(query, k=3)
        if not docs:
            return "No relevant patient context found."
        return "\n\n".join(doc.page_content for doc in docs)
    except Exception as e:
        print(f"[rag_tools] Vector store error: {e}")
        return "Vector store not available. Run scripts/build_vector_store.py first."
