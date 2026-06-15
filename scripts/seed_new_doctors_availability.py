import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timedelta, time
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

from db.client import get_doctors_by_specialties

_supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

SLOT_HOURS = [9, 10, 11, 12, 13, 14, 15, 16]
NEW_SPECIALTIES = [
    "Nephrologist", "Urologist", "Ophthalmologist",
    "ENT", "Pediatrician", "Hematologist", "Infectious Disease",
]


def main():
    doctors = get_doctors_by_specialties(NEW_SPECIALTIES)
    print(f"Found {len(doctors)} new doctors to generate availability for.")

    today = date.today()
    slots = []
    for doctor in doctors:
        for day_offset in range(35):
            slot_date = today + timedelta(days=day_offset)
            if slot_date.weekday() >= 5:
                continue
            for hour in SLOT_HOURS:
                slots.append({
                    "doctor_id": doctor["id"],
                    "available_date": slot_date.isoformat(),
                    "available_time": time(hour, 0).strftime("%H:%M:%S"),
                    "is_booked": False,
                })

    print(f"Inserting {len(slots)} availability slots...")
    for i in range(0, len(slots), 500):
        _supabase.table("doctor_availability").insert(slots[i:i + 500]).execute()

    print("Done.")


if __name__ == "__main__":
    main()
