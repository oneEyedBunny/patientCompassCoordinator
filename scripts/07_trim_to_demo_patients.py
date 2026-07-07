"""
Trim Supabase to only the 20 demo patients.

Deletes all other patients and their related medical_records and appointments.
Run this once, then rebuild the vector store:
    python scripts/05_build_vector_store.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from db.client import _client

KEEP_NAMES = [
    "Robert Bauer", "Brooke Brady", "Natalie Gamble", "Haley Perkins",
    "Jamie Campbell", "Luke Burgess", "Daniel Schmidt", "Timothy Burns",
    "Christopher Bright", "Kathryn Stewart", "Eileen Thompson", "Paul Henderson",
    "Peter Fitzgerald", "Cathy Small", "Kenneth Moore", "Mary Hunter",
    "Joshua Oliver", "Thomas Martinez", "James Patterson", "William Cooper",
]


def main():
    print("Fetching all patients...")
    result = _client.table("patients").select("id, name").execute()
    all_patients = result.data
    print(f"  {len(all_patients)} total patients in DB")

    # Match keepers case-insensitively
    keep_ids = set()
    matched_names = []
    for name in KEEP_NAMES:
        match = next((p for p in all_patients if p["name"].lower() == name.lower()), None)
        if match:
            keep_ids.add(match["id"])
            matched_names.append(match["name"])
        else:
            print(f"  ⚠️  '{name}' not found in DB — skipping")

    delete_ids = [p["id"] for p in all_patients if p["id"] not in keep_ids]
    delete_names = [p["name"] for p in all_patients if p["id"] not in keep_ids]

    print(f"\nKeeping {len(keep_ids)} patients:")
    for n in matched_names:
        print(f"  ✓ {n}")

    print(f"\nWill delete {len(delete_ids)} patients and their records/appointments.")

    if not delete_ids:
        print("Nothing to delete.")
        return

    confirm = input("\nProceed? This is irreversible. (y/N): ")
    if confirm.strip().lower() != "y":
        print("Aborted.")
        return

    batch_size = 50
    def delete_in_batches(table: str, id_field: str, ids: list):
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            _client.table(table).delete().in_(id_field, batch).execute()

    print("\nDeleting medical records...")
    delete_in_batches("medical_records", "patient_id", delete_ids)

    print("Deleting appointments...")
    delete_in_batches("appointments", "patient_id", delete_ids)

    print("Deleting patients...")
    delete_in_batches("patients", "id", delete_ids)

    print(f"\nDone. Removed {len(delete_ids)} patients and all related records.")
    print("\n⚠️  Rebuild the vector store:")
    print("    python scripts/05_build_vector_store.py")


if __name__ == "__main__":
    main()
