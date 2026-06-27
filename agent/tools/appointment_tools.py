from datetime import date, timedelta
from langchain_core.tools import tool
import dateparser
from db.client import get_patient_by_name, get_doctor_by_name, get_available_slots, is_slot_available, book_slot, get_appointments

_WEEKDAYS = {0, 1, 2, 3, 4}  # Mon–Fri


def _resolve_date(date_str: str) -> str:
    """Normalize any human date string to YYYY-MM-DD (ISO format)."""
    try:
        return date.fromisoformat(date_str).isoformat()
    except ValueError:
        pass
    parsed = dateparser.parse(
        date_str,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": date.today(),
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    if parsed:
        return parsed.date().isoformat()
    raise ValueError(f"Could not parse date: '{date_str}'. Please use a format like 'tomorrow', 'next Monday', or '2026-07-03'.")


def _next_weekdays(start: str, n: int = 7) -> list[str]:
    """Return the next n weekday dates starting from start (inclusive)."""
    current = date.fromisoformat(_resolve_date(start))
    days = []
    while len(days) < n:
        if current.weekday() in _WEEKDAYS:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


@tool
def search_doctor_availability(specialty: str, preferred_date: str) -> str:
    """Search for available doctor slots by specialty and date (YYYY-MM-DD).
    If no slots exist on the preferred date, automatically checks the next 7 weekdays."""
    dates_to_check = _next_weekdays(preferred_date)
    found = {}

    for d in dates_to_check:
        slots = get_available_slots(specialty, d)
        if slots:
            found[d] = slots

    if not found:
        return (
            f"No available slots found for {specialty} in the next 7 weekdays "
            f"starting {preferred_date}. The following specialties are available: "
            "Cardiologist, Dermatologist, Endocrinologist, Gastroenterologist, "
            "General Practitioner, Neurologist, OB/GYN, Oncologist, Orthopedist, "
            "Psychiatrist, Pulmonologist, Rheumatologist."
        )

    lines = [f"Available slots for {specialty}:"]
    for d, slots in found.items():
        lines.append(f"\n  {d}:")
        for s in slots[:5]:  # cap at 5 per day to avoid massive responses
            lines.append(f"    - Dr. {s['doctors']['name']} at {s['available_time']}")
        if len(slots) > 5:
            lines.append(f"    ... and {len(slots) - 5} more slots")
    return "\n".join(lines)


@tool
def get_patient_appointments(patient_name: str) -> str:
    """Get all scheduled, completed, and cancelled appointments for a patient by name."""
    patient = get_patient_by_name(patient_name)
    if not patient:
        return f"Patient '{patient_name}' not found. Please verify the name."

    appointments = get_appointments({"patient_id": patient["id"]})
    if not appointments:
        return f"No appointments found for {patient_name}."

    lines = [f"Appointments for {patient_name}:"]
    for a in sorted(appointments, key=lambda x: (x["appointment_date"], x["appointment_time"]), reverse=True):
        doctor_name = a["doctors"]["name"] if a.get("doctors") else "Unknown"
        specialty = a["doctors"]["specialty"] if a.get("doctors") else ""
        time_str = str(a["appointment_time"])[:5]
        lines.append(
            f"  - {a['appointment_date']} at {time_str} with Dr. {doctor_name}"
            f" ({specialty}) — {a.get('status', 'scheduled')} — {a.get('reason', 'No reason given')}"
        )
    return "\n".join(lines)


@tool
def book_appointment(patient_name: str, doctor_name: str, date: str, time: str, reason: str) -> str:
    """Book an appointment for a patient with a specific doctor on a given date and time (YYYY-MM-DD, HH:MM:SS)."""
    try:
        date = _resolve_date(date)
    except ValueError as e:
        return str(e)

    patient = get_patient_by_name(patient_name)
    if not patient:
        return f"Patient '{patient_name}' not found. Please verify the name."

    doctor = get_doctor_by_name(doctor_name)
    if not doctor:
        return f"Doctor '{doctor_name}' not found."

    doctor_id = doctor["id"]

    if not is_slot_available(doctor_id, date, time):
        return "That slot is no longer available. Please search for another time."

    appointment = book_slot(patient["id"], doctor_id, date, time, reason)
    return (
        f"Appointment confirmed!\n"
        f"  Patient: {patient_name}\n"
        f"  Doctor: Dr. {doctor_name}\n"
        f"  Date: {date} at {time}\n"
        f"  Reason: {reason}\n"
        f"  Appointment ID: {appointment['id']}"
    )
