import re
from datetime import date, timedelta
from langchain_core.tools import tool
import dateparser


def _resolve_time(time_str: str) -> str:
    """Normalize any human time string to HH:MM:SS for DB lookup."""
    s = time_str.strip().upper()
    # Already HH:MM:SS
    if re.match(r'^\d{1,2}:\d{2}:\d{2}$', s):
        h, m, sec = s.split(":")
        return f"{int(h):02d}:{m}:{sec}"
    # HH:MM
    if re.match(r'^\d{1,2}:\d{2}$', s):
        h, m = s.split(":")
        return f"{int(h):02d}:{m}:00"
    # 11AM / 9PM
    match = re.match(r'^(\d{1,2})\s*(AM|PM)$', s)
    if match:
        h, period = int(match.group(1)), match.group(2)
        if period == "PM" and h != 12:
            h += 12
        elif period == "AM" and h == 12:
            h = 0
        return f"{h:02d}:00:00"
    # 11:00 AM / 9:30 PM
    match = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)$', s)
    if match:
        h, mins, period = int(match.group(1)), match.group(2), match.group(3)
        if period == "PM" and h != 12:
            h += 12
        elif period == "AM" and h == 12:
            h = 0
        return f"{h:02d}:{mins}:00"
    raise ValueError(f"Could not parse time: '{time_str}'. Use a format like '11:00 AM', '14:00', or '09:00:00'.")


def _fmt_time(t) -> str:
    """Convert HH:MM:SS or HH:MM string to 12-hour AM/PM format."""
    parts = str(t).split(":")
    h, m = int(parts[0]), int(parts[1])
    period = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:{m:02d} {period}"
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
            "General Practitioner, Nephrologist, Neurologist, OB/GYN, Oncologist, "
            "Orthopedist, Psychiatrist, Pulmonologist, Rheumatologist."
        )

    lines = [f"Available slots for {specialty}:"]
    for d, slots in found.items():
        lines.append(f"\n  {d}:")
        for s in slots[:5]:  # cap at 5 per day to avoid massive responses
            lines.append(f"    - Dr. {s['doctors']['name']} at {_fmt_time(s['available_time'])}")
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
            f"  - {a['appointment_date']} at {_fmt_time(time_str)} with Dr. {doctor_name}"
            f" ({specialty}) — {a.get('status', 'scheduled')} — {a.get('reason', 'No reason given')}"
        )
    return "\n".join(lines)


@tool
def book_appointment(patient_name: str, doctor_name: str, date: str, time: str, reason: str) -> str:
    """Book an appointment for a patient with a specific doctor on a given date and time. Date: YYYY-MM-DD or natural language. Time: any format (HH:MM:SS, HH:MM, 11:00 AM, 11AM)."""
    try:
        date = _resolve_date(date)
        time = _resolve_time(time)
    except ValueError as e:
        return str(e)

    patient = get_patient_by_name(patient_name)
    if not patient:
        return f"Patient '{patient_name}' not found. Please verify the name."

    doctor = get_doctor_by_name(re.sub(r"(?i)^dr\.?\s+", "", doctor_name.strip()))
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
        f"  Date: {date} at {_fmt_time(time)}\n"
        f"  Reason: {reason}\n"
        f"  Appointment ID: {appointment['id']}"
    )
