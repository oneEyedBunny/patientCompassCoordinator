import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

load_dotenv()

from db.client import get_all_patients, get_medical_records

VECTOR_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "vector_store")


def build_documents(patients: list[dict]) -> list[Document]:
    docs = []
    for p in patients:
        meta = {"patient_id": p["id"], "patient_name": p["name"]}

        # Profile document — core demographic + clinical snapshot
        profile_text = (
            f"{p['name']}, age {p['age']}, {p['gender']}, blood type {p['blood_type']}. "
            f"Condition: {p['medical_condition']}. "
            f"Medication: {p['medication']}. "
            f"Test results: {p['test_results']}."
        )
        docs.append(Document(page_content=profile_text, metadata={**meta, "doc_type": "profile"}))

        # One document per medical record — enables semantic search over history
        records = get_medical_records(p["id"])
        for r in records:
            record_text = (
                f"{p['name']} medical record [{r['record_date']}]: "
                f"Diagnosis: {r['diagnosis']}. "
                f"Treatment: {r['treatment']}."
                + (f" Notes: {r['notes']}." if r.get("notes") else "")
            )
            docs.append(Document(page_content=record_text, metadata={**meta, "doc_type": "record"}))

    return docs


def main():
    print("Fetching patients from Supabase...")
    patients = get_all_patients()
    print(f"  {len(patients)} patients fetched")

    print("Building documents...")
    docs = build_documents(patients)

    print("Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print("Building FAISS index...")
    vectorstore = FAISS.from_documents(docs, embeddings)

    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
    vectorstore.save_local(VECTOR_STORE_PATH)
    print(f"  Index saved to {VECTOR_STORE_PATH}")
    print("\nVector store build complete.")


if __name__ == "__main__":
    main()
