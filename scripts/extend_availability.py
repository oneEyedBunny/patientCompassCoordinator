"""
One-off script to extend doctor availability through July 20.
Only inserts slots that don't already exist (no duplicates).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta, time
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

from db.client import get_all_doctors

_supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

SLOT_HOURS = [9, 10, 11, 12, 13, 14, 15, 16]
END_DATE = date(2026, 7, 20)


def main():
    doctors = get_all_doctors()
    print(f"Found {len(doctors)} doctors.")

    existing = _supabase.table("doctor_availability").select("doctor_id, available_date, available_time").execute().data
    existing_set = {(r["doctor_id"], r["available_date"], r["available_time"]) for r in existing}
    print(f"Found {len(existing_set)} existing slots.")

    today = date.today()
    slots = []
    current = today
    while current <= END_DATE:
        if current.weekday() < 5:
            for doctor in doctors:
                for hour in SLOT_HOURS:
                    key = (doctor["id"], current.isoformat(), time(hour, 0).strftime("%H:%M:%S"))
                    if key not in existing_set:
                        slots.append({
                            "doctor_id": doctor["id"],
                            "available_date": current.isoformat(),
                            "available_time": time(hour, 0).strftime("%H:%M:%S"),
                            "is_booked": False,
                        })
        current += timedelta(days=1)

    print(f"Inserting {len(slots)} new slots...")
    for i in range(0, len(slots), 500):
        _supabase.table("doctor_availability").insert(slots[i:i + 500]).execute()

    print("Done.")


if __name__ == "__main__":
    main()
