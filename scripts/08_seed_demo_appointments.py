"""
Seed demo appointments for the 20 demo patients.

Past (60 calendar days):
  - ~3 appointments per weekday, 70% completed / 30% cancelled
  - Inserted directly — no doctor_availability records exist for past dates

Future (4 weeks, utilization curve):
  - Week 1: 30% of available slots booked
  - Week 2: 34%,  Week 3: 38%,  Week 4: 42%
  - Each booking inserts an appointment AND marks doctor_availability as booked

Run AFTER scripts/03_extend_availability.py so future slots exist.
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

TIMES = ["09:00:00", "11:00:00", "13:00:00", "15:00:00"]

BASE_RATE = 0.30
WEEKLY_INCREMENT = 0.04
PAST_APPTS_PER_DAY = 3
PAST_CANCEL_RATE = 0.30
FUTURE_END_DATE = date(2026, 9, 30)


def main():
    random.seed(42)
    today = date.today()

    result = _client.table("patients").select("id, name").in_("name", PATIENT_NAMES).execute()
    patients = result.data
    print(f"Found {len(patients)} demo patients")

    result = _client.table("doctors").select("id, name, specialty").execute()
    doctors = result.data
    print(f"Found {len(doctors)} doctors")

    if not patients or not doctors:
        print("Missing data — aborting.")
        return

    # ── Past appointments ─────────────────────────────────────────────────────
    past_appointments = []
    for days_ago in range(1, 61):
        d = today - timedelta(days=days_ago)
        if d.weekday() >= 5:
            continue
        for _ in range(PAST_APPTS_PER_DAY):
            status = "cancelled" if random.random() < PAST_CANCEL_RATE else "completed"
            past_appointments.append({
                "patient_id": random.choice(patients)["id"],
                "doctor_id": random.choice(doctors)["id"],
                "appointment_date": d.isoformat(),
                "appointment_time": random.choice(TIMES),
                "reason": random.choice(REASONS),
                "status": status,
            })

    print(f"\nInserting {len(past_appointments)} past appointments (~70% completed, ~30% cancelled)...")
    for i in range(0, len(past_appointments), 500):
        _client.table("appointments").insert(past_appointments[i:i + 500]).execute()
    print("Done.")

    # ── Future appointments (utilization curve) ───────────────────────────────
    num_weeks = ((FUTURE_END_DATE - today).days // 7) + 1
    end_rate = min(BASE_RATE + (num_weeks - 1) * WEEKLY_INCREMENT, 1.0)
    print(f"\nSeeding future appointments (utilization curve: {BASE_RATE:.0%} → {end_rate:.0%}, {num_weeks} weeks)...")
    total_future = 0

    for week in range(num_weeks):
        rate = min(BASE_RATE + week * WEEKLY_INCREMENT, 1.0)
        week_start = today + timedelta(days=week * 7)
        week_end = min(week_start + timedelta(days=6), FUTURE_END_DATE)

        slots_result = (
            _client.table("doctor_availability")
            .select("id, doctor_id, available_date, available_time")
            .eq("is_booked", False)
            .gte("available_date", week_start.isoformat())
            .lte("available_date", week_end.isoformat())
            .execute()
        )
        slots = slots_result.data

        target = int(len(slots) * rate)
        selected = random.sample(slots, min(target, len(slots)))

        future_appointments = [
            {
                "patient_id": random.choice(patients)["id"],
                "doctor_id": slot["doctor_id"],
                "appointment_date": slot["available_date"],
                "appointment_time": slot["available_time"],
                "reason": random.choice(REASONS),
                "status": "scheduled",
            }
            for slot in selected
        ]

        for i in range(0, len(future_appointments), 500):
            _client.table("appointments").insert(future_appointments[i:i + 500]).execute()

        slot_ids = [s["id"] for s in selected]
        for i in range(0, len(slot_ids), 500):
            _client.table("doctor_availability").update({"is_booked": True}).in_("id", slot_ids[i:i + 500]).execute()

        print(f"  Week {week + 1} ({week_start} – {week_end}): {len(selected)}/{len(slots)} slots booked ({rate:.0%})")
        total_future += len(selected)

    print(f"\nTotal future appointments: {total_future}")
    print("Done. Run 03_extend_availability.py first if slots are missing.")


if __name__ == "__main__":
    main()
