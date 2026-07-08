"""
Extends doctor availability from today through a target end date.
Only inserts slots that don't already exist (safe to re-run).

Usage:
    python scripts/extend_availability.py
    python scripts/extend_availability.py --end 2026-12-31
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta, time
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

from db.client import get_all_doctors

_supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

SLOT_HOURS = [9, 11, 13, 15]
DEFAULT_END_DATE = date(2026, 9, 30)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", default=DEFAULT_END_DATE.isoformat(), help="End date YYYY-MM-DD")
    args = parser.parse_args()

    end_date = date.fromisoformat(args.end)
    today = date.today()
    print(f"Extending availability: {today} to {end_date}")

    doctors = get_all_doctors()
    print(f"Found {len(doctors)} doctors.")

    # Load existing slots to avoid duplicates — page through since there may be many
    existing_set = set()
    page_size = 1000
    offset = 0
    while True:
        result = _supabase.table("doctor_availability") \
            .select("doctor_id, available_date, available_time") \
            .range(offset, offset + page_size - 1) \
            .execute()
        for r in result.data:
            existing_set.add((r["doctor_id"], r["available_date"], r["available_time"]))
        if len(result.data) < page_size:
            break
        offset += page_size
    print(f"Found {len(existing_set)} existing slots (will skip duplicates).")

    slots = []
    current = today
    while current <= end_date:
        if current.weekday() < 5:  # weekdays only
            for doctor in doctors:
                for hour in SLOT_HOURS:
                    slot_time = time(hour, 0).strftime("%H:%M:%S")
                    key = (doctor["id"], current.isoformat(), slot_time)
                    if key not in existing_set:
                        slots.append({
                            "doctor_id": doctor["id"],
                            "available_date": current.isoformat(),
                            "available_time": slot_time,
                            "is_booked": False,
                        })
        current += timedelta(days=1)

    if not slots:
        print("No new slots to insert — already up to date.")
        return

    print(f"Inserting {len(slots)} new slots...")
    inserted = 0
    for i in range(0, len(slots), 500):
        _supabase.table("doctor_availability").insert(slots[i:i + 500]).execute()
        inserted += min(500, len(slots) - i)
        print(f"  {inserted}/{len(slots)}...", end="\r")

    print(f"\nDone. {inserted} slots inserted.")


if __name__ == "__main__":
    main()
