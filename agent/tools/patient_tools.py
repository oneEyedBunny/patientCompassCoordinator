from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from agent.llm import llm
from agent.prompts import HISTORY_SUMMARY_PROMPT
from db.client import get_patient_by_name, get_medical_records, add_medical_record


@tool
def get_patient_history(patient_name: str) -> str:
    """Retrieve and summarize the full medical history for a patient by name."""
    patient = get_patient_by_name(patient_name)
    if not patient:
        return f"Patient '{patient_name}' not found. Please verify the name."

    records = get_medical_records(patient["id"])

    raw = (
        f"Patient: {patient['name']}, Age: {patient['age']}, Gender: {patient['gender']}\n"
        f"Blood Type: {patient['blood_type']}\n"
        f"Primary Condition: {patient['medical_condition']}\n"
        f"Medication: {patient['medication']}\n"
        f"Test Results: {patient['test_results']}\n"
        f"Admission Type: {patient['admission_type']}\n"
    )

    if records:
        raw += "\nMedical Records:\n"
        for r in records:
            raw += f"  [{r['record_date']}] Diagnosis: {r['diagnosis']} | Treatment: {r['treatment']} | Notes: {r['notes']}\n"

    prompt = HISTORY_SUMMARY_PROMPT.format(raw_history=raw)
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content


@tool
def log_session_summary(patient_name: str, diagnosis: str, treatment: str, notes: str) -> str:
    """Log a clinical summary of the current patient conversation to their medical record.
    Call this after a booking is confirmed or when the conversation is ending to capture
    symptoms, conditions, and any care discussed. Use the appointment reason or primary
    condition as diagnosis, booked or recommended care as treatment, and a brief summary
    of what the patient shared as notes."""
    patient = get_patient_by_name(patient_name)
    if not patient:
        return f"Patient '{patient_name}' not found. Please verify the name."

    add_medical_record(patient["id"], diagnosis, treatment, notes)
    return f"Session summary logged for {patient_name}: {diagnosis} — {treatment}."
