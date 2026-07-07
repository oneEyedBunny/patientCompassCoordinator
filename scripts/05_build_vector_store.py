import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

load_dotenv()

from db.client import get_all_patients, get_all_medical_records

VECTOR_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "vector_store")


def build_documents(patients: list[dict], records_by_patient: dict) -> list[Document]:
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

        # One document per medical record — enables per-patient semantic history search
        for r in records_by_patient.get(p["id"], []):
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

    print("Fetching all medical records (bulk)...")
    all_records = get_all_medical_records()
    print(f"  {len(all_records)} medical records fetched")

    # Group records by patient_id in memory — avoids per-patient API calls
    records_by_patient: dict = {}
    for r in all_records:
        records_by_patient.setdefault(r["patient_id"], []).append(r)

    print("Building documents...")
    docs = build_documents(patients, records_by_patient)

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
