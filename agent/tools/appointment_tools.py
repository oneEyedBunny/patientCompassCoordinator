from langchain_core.tools import tool
from db.client import get_patient_by_name, get_doctor_by_name, get_available_slots, is_slot_available, book_slot


@tool
def search_doctor_availability(specialty: str, preferred_date: str) -> str:
    """Search for available doctor slots by specialty and date (YYYY-MM-DD)."""
    slots = get_available_slots(specialty, preferred_date)
    if not slots:
        return f"No available slots found for {specialty} on {preferred_date}."

    lines = [f"Available slots for {specialty} on {preferred_date}:"]
    for s in slots:
        lines.append(f"  - Dr. {s['doctors']['name']} at {s['available_time']}")
    return "\n".join(lines)


@tool
def book_appointment(patient_name: str, doctor_name: str, date: str, time: str, reason: str) -> str:
    """Book an appointment for a patient with a specific doctor on a given date and time (YYYY-MM-DD, HH:MM:SS)."""
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
