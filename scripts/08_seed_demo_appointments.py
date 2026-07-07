"""
Seed demo appointments for the 20 demo patients:
  - 20 completed past appointments (1 per patient, 1-6 months ago)
  -  5 cancelled appointments (random patients, 1-4 months ago)
  -  5 upcoming appointments  (different random patients, 1-4 weeks out)

Inserts directly into appointments — bypasses doctor_availability so no
slot availability checks are needed for historical/future dates.
"""
import os
import sys
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from db.client import _client

PATIENT_NAMES = [
    "Robert Bauer", "Brooke Brady", "Natalie Gamble", "Haley Perkins",
    "Jamie Campbell", "Luke Burgess", "Daniel Schmidt", "Timothy Burns",
    "Christopher Bright", "Kathryn Stewart", "Eileen Thompson", "Paul Henderson",
    "Peter Fitzgerald", "Cathy Small", "Kenneth Moore", "Mary Hunter",
    "Joshua Oliver", "Thomas Martinez", "James Patterson", "William Cooper",
]

REASONS = [
    "Annual physical exam",
    "Follow-up on medication",
    "Routine check-up",
    "Chronic condition monitoring",
    "Blood pressure review",
    "Lab results review",
    "Specialist consultation",
    "Preventive care visit",
    "Symptom evaluation",
    "Post-treatment follow-up",
]

TIMES = ["09:00:00", "10:00:00", "11:00:00", "13:00:00", "14:00:00", "15:00:00", "16:00:00"]


def _past_date(months_ago: int) -> str:
    jitter = random.randint(-10, 10)
    return (date.today() - timedelta(days=months_ago * 30 + jitter)).isoformat()


def _future_date(weeks_ahead: int) -> str:
    d = date.today() + timedelta(weeks=weeks_ahead, days=random.randint(0, 4))
    while d.weekday() >= 5:  # skip weekends
        d += timedelta(days=1)
    return d.isoformat()


def main():
    random.seed(42)

    result = _client.table("patients").select("id, name").in_("name", PATIENT_NAMES).execute()
    patients = [(p["name"], p["id"]) for p in result.data]
    print(f"Found {len(patients)} demo patients")

    result = _client.table("doctors").select("id, name, specialty").execute()
    doctors = result.data
    print(f"Found {len(doctors)} doctors")

    if not patients or not doctors:
        print("Missing data — aborting.")
        return

    appointments = []

    # 20 completed — one per patient
    for name, pid in patients:
        appointments.append({
            "patient_id": pid,
            "doctor_id": random.choice(doctors)["id"],
            "appointment_date": _past_date(random.randint(1, 6)),
            "appointment_time": random.choice(TIMES),
            "reason": random.choice(REASONS),
            "status": "completed",
        })

    # 5 cancelled — random patients
    for name, pid in random.sample(patients, 5):
        appointments.append({
            "patient_id": pid,
            "doctor_id": random.choice(doctors)["id"],
            "appointment_date": _past_date(random.randint(1, 4)),
            "appointment_time": random.choice(TIMES),
            "reason": random.choice(REASONS),
            "status": "cancelled",
        })

    # 5 upcoming — different random patients
    for name, pid in random.sample(patients, 5):
        appointments.append({
            "patient_id": pid,
            "doctor_id": random.choice(doctors)["id"],
            "appointment_date": _future_date(random.randint(1, 4)),
            "appointment_time": random.choice(TIMES),
            "reason": random.choice(REASONS),
            "status": "scheduled",
        })

    print(f"\nInserting {len(appointments)} appointments...")
    _client.table("appointments").insert(appointments).execute()
    print(f"Done. 20 completed | 5 cancelled | 5 upcoming")


if __name__ == "__main__":
    main()
