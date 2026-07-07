"""
Strip honorific prefixes (Mr., Mrs., Ms., Dr., Prof.) from patient names in Supabase.

After running this script, rebuild the FAISS vector store:
    python scripts/build_vector_store.py
"""
import re
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from db.client import _client

_PREFIX_RE = re.compile(r'^(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+', re.IGNORECASE)
_SUFFIX_RE = re.compile(r'\s+(Jr\.?|Sr\.?|II|III|IV|M\.?D\.?|Ph\.?D\.?|D\.?D\.?S\.?)$', re.IGNORECASE)


def _clean(name: str) -> str:
    name = _PREFIX_RE.sub("", name).strip()
    name = _SUFFIX_RE.sub("", name).strip()
    return name


def main():
    result = _client.table("patients").select("id, name").execute()
    patients = result.data

    to_update = [(p["id"], p["name"], _clean(p["name"])) for p in patients if _clean(p["name"]) != p["name"]]

    if not to_update:
        print("No prefixed names found — nothing to update.")
        return

    print(f"Found {len(to_update)} patient(s) with prefixes:\n")
    for _, old, new in to_update:
        print(f"  '{old}'  →  '{new}'")

    confirm = input("\nProceed with update? (y/N): ")
    if confirm.strip().lower() != "y":
        print("Aborted.")
        return

    for pid, _, new_name in to_update:
        _client.table("patients").update({"name": new_name}).eq("id", pid).execute()

    print(f"\nUpdated {len(to_update)} record(s).")
    print("\n⚠️  Rebuild the FAISS vector store before using RAG features:")
    print("    python scripts/build_vector_store.py")


if __name__ == "__main__":
    main()
