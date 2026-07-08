import os
from datetime import date
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def get_patient_by_name(name: str) -> dict | None:
    result = _client.table("patients").select("*").ilike("name", f"%{name}%").limit(1).execute()
    return result.data[0] if result.data else None


def search_patients_by_name(name: str) -> list[dict]:
    result = _client.table("patients").select("*").ilike("name", f"%{name}%").order("name").limit(50).execute()
    return result.data


def get_patient_by_id(patient_id: str) -> dict | None:
    result = _client.table("patients").select("*").eq("id", patient_id).limit(1).execute()
    return result.data[0] if result.data else None


def _normalize_time(t: str) -> str:
    """Ensure time is HH:MM:SS — the DB stores seconds, the agent often omits them."""
    return t if len(t) == 8 else t + ":00"


def get_available_slots(specialty: str, date: str) -> list[dict]:
    result = (
        _client.table("doctor_availability")
        .select("*, doctors(name, specialty)")
        .eq("is_booked", False)
        .eq("available_date", date)
        .execute()
    )
    return [
        r for r in result.data
        if r.get("doctors") and r["doctors"]["specialty"].lower() == specialty.lower()
    ]


def book_slot(patient_id: str, doctor_id: str, date: str, time: str, reason: str) -> dict:
    time = _normalize_time(time)
    _client.table("doctor_availability").update({"is_booked": True}).eq("doctor_id", doctor_id).eq("available_date", date).eq("available_time", time).execute()

    result = (
        _client.table("appointments")
        .insert({
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "appointment_date": date,
            "appointment_time": time,
            "reason": reason,
            "status": "scheduled",
        })
        .execute()
    )
    return result.data[0]


def get_appointments(filters: dict | None = None) -> list[dict]:
    query = _client.table("appointments").select("*, patients(name), doctors(name, specialty)")
    if filters:
        for key, value in filters.items():
            query = query.eq(key, value)
    return query.execute().data


def add_medical_record(patient_id: str, diagnosis: str, treatment: str, notes: str) -> dict:
    result = (
        _client.table("medical_records")
        .insert({
            "patient_id": patient_id,
            "record_date": str(date.today()),
            "diagnosis": diagnosis,
            "treatment": treatment,
            "notes": notes,
        })
        .execute()
    )
    return result.data[0]


def is_slot_available(doctor_id: str, date: str, time: str) -> bool:
    time = _normalize_time(time)
    result = (
        _client.table("doctor_availability")
        .select("id")
        .eq("doctor_id", doctor_id)
        .eq("available_date", date)
        .eq("available_time", time)
        .eq("is_booked", False)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def get_all_patients() -> list[dict]:
    all_patients = []
    page_size = 1000
    offset = 0
    while True:
        result = _client.table("patients").select("*").range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        all_patients.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_patients


def get_doctor_by_name(name: str) -> dict | None:
    result = _client.table("doctors").select("*").ilike("name", f"%{name}%").limit(1).execute()
    return result.data[0] if result.data else None


def get_medical_records(patient_id: str) -> list[dict]:
    result = (
        _client.table("medical_records")
        .select("*")
        .eq("patient_id", patient_id)
        .order("record_date", desc=True)
        .execute()
    )
    return result.data


def get_all_medical_records() -> list[dict]:
    """Fetch all medical records in paginated bulk queries — avoids per-patient API calls."""
    all_records = []
    page_size = 1000
    offset = 0
    while True:
        result = _client.table("medical_records").select("*").range(offset, offset + page_size - 1).execute()
        if not result.data:
            break
        all_records.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_records



def update_appointment_status(appointment_id: str, status: str) -> None:
    _client.table("appointments").update({"status": status}).eq("id", appointment_id).execute()


def get_all_doctors() -> list[dict]:
    result = _client.table("doctors").select("id, name, specialty").execute()
    return result.data


def get_doctors_by_specialties(specialties: list[str]) -> list[dict]:
    result = _client.table("doctors").select("id, name, specialty").in_("specialty", specialties).execute()
    return result.data
