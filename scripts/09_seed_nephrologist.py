"""
Insert two Nephrologist doctors and seed their availability for the next 35 weekdays.

Run once:
    python scripts/09_seed_nephrologist.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta, time
from dotenv import load_dotenv
load_dotenv()

from db.client import _client

DOCTORS = [
    {"name": "Sarah Chen", "specialty": "Nephrologist"},
    {"name": "Marcus Webb", "specialty": "Nephrologist"},
]

SLOT_HOURS = [9, 10, 11, 12, 13, 14, 15, 16]


def main():
    # Insert doctors (skip any that already exist by name)
    existing = _client.table("doctors").select("name").eq("specialty", "Nephrologist").execute()
    existing_names = {d["name"] for d in existing.data}

    inserted_ids = []
    for doc in DOCTORS:
        if doc["name"] in existing_names:
            print(f"  Already exists: {doc['name']} — fetching ID")
            result = _client.table("doctors").select("id").eq("name", doc["name"]).execute()
            inserted_ids.append(result.data[0]["id"])
        else:
            result = _client.table("doctors").insert(doc).execute()
            inserted_ids.append(result.data[0]["id"])
            print(f"  Inserted: {doc['name']}")

    # Seed availability for the next 35 weekdays
    today = date.today()
    slots = []
    for doctor_id in inserted_ids:
        for day_offset in range(35):
            slot_date = today + timedelta(days=day_offset)
            if slot_date.weekday() >= 5:
                continue
            for hour in SLOT_HOURS:
                slots.append({
                    "doctor_id": doctor_id,
                    "available_date": slot_date.isoformat(),
                    "available_time": time(hour, 0).strftime("%H:%M:%S"),
                    "is_booked": False,
                })

    print(f"\nInserting {len(slots)} availability slots...")
    for i in range(0, len(slots), 500):
        _client.table("doctor_availability").insert(slots[i:i + 500]).execute()

    print("Done. Dr. Sarah Chen and Dr. Marcus Webb are available as Nephrologists.")


if __name__ == "__main__":
    main()
