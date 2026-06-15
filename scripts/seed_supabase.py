import os
import sys
import random
from datetime import date, timedelta, time

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

CONDITION_TO_SPECIALTY = {
    "Diabetes": "Endocrinologist",
    "Hypertension": "Cardiologist",
    "Heart Disease": "Cardiologist",
    "Asthma": "Pulmonologist",
    "Arthritis": "Rheumatologist",
    "Osteoporosis": "Rheumatologist",
    "Cancer": "Oncologist",
    "Obesity": "General Practitioner",
}

SLOT_HOURS = [9, 10, 11, 12, 13, 14, 15, 16]  # 9am–4pm (8 slots/day)


def load_csv() -> pd.DataFrame:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "healthcare_dataset.csv")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


MAX_DOCTORS = 50


def seed_doctors(df: pd.DataFrame) -> dict[str, str]:
    """Insert unique doctors (capped at MAX_DOCTORS), return name->id map."""
    unique = df[["doctor", "medical_condition"]].drop_duplicates("doctor").head(MAX_DOCTORS)
    doctors = []
    for _, row in unique.iterrows():
        specialty = CONDITION_TO_SPECIALTY.get(row["medical_condition"], "General Practitioner")
        doctors.append({"name": row["doctor"], "specialty": specialty})

    result = client.table("doctors").insert(doctors).execute()
    return {r["name"]: r["id"] for r in result.data}


def seed_patients(df: pd.DataFrame) -> dict[str, str]:
    """Insert all patients, return name->id map."""
    patients = []
    for _, row in df.iterrows():
        patients.append({
            "name": row["name"],
            "age": int(row["age"]),
            "gender": row["gender"],
            "blood_type": row["blood_type"],
            "medical_condition": row["medical_condition"],
            "medication": row.get("medication", ""),
            "test_results": row.get("test_results", ""),
            "admission_type": row.get("admission_type", ""),
        })

    # Insert in batches of 500 to stay within Supabase limits
    name_to_id = {}
    for i in range(0, len(patients), 500):
        batch = patients[i:i + 500]
        result = client.table("patients").insert(batch).execute()
        for r in result.data:
            name_to_id[r["name"]] = r["id"]

    return name_to_id


def seed_availability(doctor_ids: dict[str, str]) -> list[dict]:
    """Generate 14-day availability grid, return all inserted rows."""
    today = date.today()
    slots = []
    for doctor_name, doctor_id in doctor_ids.items():
        for day_offset in range(14):
            slot_date = today + timedelta(days=day_offset)
            if slot_date.weekday() >= 5:  # skip weekends
                continue
            for hour in SLOT_HOURS:
                slots.append({
                    "doctor_id": doctor_id,
                    "available_date": slot_date.isoformat(),
                    "available_time": time(hour, 0).strftime("%H:%M:%S"),
                    "is_booked": False,
                })

    inserted = []
    for i in range(0, len(slots), 500):
        result = client.table("doctor_availability").insert(slots[i:i + 500]).execute()
        inserted.extend(result.data)

    return inserted


def seed_appointments(availability: list[dict], patient_ids: dict[str, str]) -> None:
    """Pre-book ~20% of slots as baseline appointments."""
    patient_id_list = list(patient_ids.values())
    to_book = random.sample(availability, k=int(len(availability) * 0.20))

    appointments = []
    for slot in to_book:
        appointments.append({
            "patient_id": random.choice(patient_id_list),
            "doctor_id": slot["doctor_id"],
            "appointment_date": slot["available_date"],
            "appointment_time": slot["available_time"],
            "reason": "Routine follow-up",
            "status": "scheduled",
        })
        client.table("doctor_availability").update({"is_booked": True}).eq("id", slot["id"]).execute()

    for i in range(0, len(appointments), 500):
        client.table("appointments").insert(appointments[i:i + 500]).execute()


def main():
    print("Loading CSV...")
    df = load_csv()
    print(f"  {len(df)} rows loaded")

    print("Seeding doctors...")
    doctor_ids = seed_doctors(df)
    print(f"  {len(doctor_ids)} doctors inserted")

    print("Seeding patients...")
    patient_ids = seed_patients(df)
    print(f"  {len(patient_ids)} patients inserted")

    print("Seeding availability...")
    availability = seed_availability(doctor_ids)
    print(f"  {len(availability)} slots created")

    print("Pre-booking ~20% of slots...")
    seed_appointments(availability, patient_ids)
    print("  Done")

    print("\nSeed complete.")


if __name__ == "__main__":
    main()
