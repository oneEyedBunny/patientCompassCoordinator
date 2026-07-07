"""
Seed the medical_records table with 2-3 synthetic visit records per patient.
Records are generated from each patient's existing condition/medication/test_results fields.
Idempotent — skips patients who already have records.
"""
import os
import sys
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from db.client import get_all_patients, get_all_medical_records

_supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

BATCH_SIZE = 500

# (diagnosis_template, treatment_template, notes_template) — 3 records per condition
# {condition}, {medication}, {test_results} are filled from patient data
CONDITION_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "Diabetes": [
        ("Type 2 Diabetes — initial diagnosis confirmed", "Started {medication}. Nutritional counseling initiated.", "Patient educated on blood glucose self-monitoring and carbohydrate counting."),
        ("Diabetes — 6-month follow-up", "{medication} continued, dosage stable.", "HbA1c reviewed. Dietary compliance noted. No hypoglycemic episodes reported."),
        ("Diabetes — routine monitoring", "Ongoing {medication}. Lifestyle modifications reinforced.", "{test_results}"),
    ],
    "Hypertension": [
        ("Hypertension — initial assessment", "Started {medication}. Low-sodium diet and exercise regimen advised.", "Blood pressure elevated at presentation. Patient education on lifestyle modifications provided."),
        ("Hypertension — medication review", "{medication} continued. BP trending toward target range.", "Patient reports good adherence. No side effects noted."),
        ("Hypertension — routine check", "Ongoing {medication}. Stress reduction strategies discussed.", "{test_results}"),
    ],
    "Heart Disease": [
        ("Cardiovascular evaluation — initial", "Started {medication}. Cardiac monitoring initiated.", "EKG performed. Patient referred to cardiology for further evaluation."),
        ("Heart disease — 6-month cardiology follow-up", "{medication} continued. Activity restrictions reviewed.", "Functional status stable. No new chest pain or dyspnea reported."),
        ("Heart disease — routine monitoring", "Ongoing {medication}. Dietary and activity plan reviewed.", "{test_results}"),
    ],
    "Asthma": [
        ("Asthma — initial diagnosis", "Started {medication}. Inhaler technique reviewed and confirmed.", "Peak flow measured. Environmental and allergen triggers identified and discussed."),
        ("Asthma — follow-up visit", "{medication} continued. Inhaler use and frequency assessed.", "Symptom frequency reduced since last visit. Action plan updated."),
        ("Asthma — routine review", "Ongoing {medication}. Rescue inhaler use tracked.", "{test_results}"),
    ],
    "Cancer": [
        ("Oncology consultation — initial assessment", "{medication} initiated per oncology protocol.", "Staging complete. Treatment plan established in coordination with oncology team."),
        ("Cancer — treatment progress review", "Ongoing {medication}. Treatment tolerance assessed.", "Side effects managed with supportive care. Patient coping well."),
        ("Cancer — monitoring visit", "Continued {medication}. Follow-up imaging ordered.", "{test_results}"),
    ],
    "Arthritis": [
        ("Arthritis — initial assessment", "Started {medication}. Physical therapy referral placed.", "Joint mobility evaluated. Range of motion exercises and ergonomic modifications prescribed."),
        ("Arthritis — follow-up", "{medication} continued. Pain levels and daily function reassessed.", "Patient reports moderate improvement in morning stiffness."),
        ("Arthritis — routine monitoring", "Ongoing {medication}. Activity pacing and joint protection techniques reviewed.", "{test_results}"),
    ],
    "Obesity": [
        ("Obesity — initial assessment", "Started {medication}. Structured dietary and behavioral counseling initiated.", "BMI and metabolic panel documented. Weight management program established."),
        ("Obesity — 6-month progress review", "Ongoing {medication}. Weight trend and dietary adherence reviewed.", "Patient demonstrates improved meal planning adherence."),
        ("Obesity — routine check", "Continued {medication}. Physical activity goals updated.", "{test_results}"),
    ],
    "Osteoporosis": [
        ("Osteoporosis — initial diagnosis", "Started {medication}. Calcium and vitamin D supplementation added.", "DEXA scan results reviewed. Fall prevention strategies and home safety assessment discussed."),
        ("Osteoporosis — 6-month follow-up", "{medication} continued. Supplement adherence and tolerability confirmed.", "No fracture events since last visit. Weight-bearing exercise program reinforced."),
        ("Osteoporosis — routine monitoring", "Ongoing {medication}. Bone health and fall risk reassessed.", "{test_results}"),
    ],
}

DEFAULT_TEMPLATES: list[tuple[str, str, str]] = [
    ("{condition} — initial assessment", "Started {medication}. Patient education and baseline care plan provided.", "Baseline health metrics documented. Follow-up scheduled."),
    ("{condition} — follow-up visit", "{medication} continued. Response to treatment assessed.", "Condition stable. No acute concerns noted."),
    ("{condition} — routine monitoring", "Ongoing management with {medication}. Care plan reviewed.", "{test_results}"),
]

# Approximate months-ago for each of the 3 records
_RECORD_OFFSETS = [12, 6, 3]


def _date_offset(months_ago: int) -> str:
    jitter = random.randint(-10, 10)
    return (date.today() - timedelta(days=months_ago * 30 + jitter)).isoformat()


def _fill(template: str, patient: dict) -> str:
    return (
        template
        .replace("{condition}", patient.get("medical_condition") or "condition")
        .replace("{medication}", patient.get("medication") or "prescribed medication")
        .replace("{test_results}", patient.get("test_results") or "results reviewed")
    )


def build_records(patient: dict) -> list[dict]:
    condition = (patient.get("medical_condition") or "").strip()
    templates = CONDITION_TEMPLATES.get(condition, DEFAULT_TEMPLATES)
    records = []
    for i, (diag, treat, notes) in enumerate(templates):
        records.append({
            "patient_id": patient["id"],
            "record_date": _date_offset(_RECORD_OFFSETS[i]),
            "diagnosis": _fill(diag, patient),
            "treatment": _fill(treat, patient),
            "notes": _fill(notes, patient),
        })
    return records


def batch_insert(records: list[dict]) -> None:
    total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i: i + BATCH_SIZE]
        _supabase.table("medical_records").insert(batch).execute()
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches} — {len(batch)} records inserted")


def main():
    random.seed(42)

    print("Fetching all patients...")
    patients = get_all_patients()
    print(f"  {len(patients)} patients loaded")

    print("Checking for existing records (bulk fetch)...")
    existing_records = get_all_medical_records()
    already_seeded = {r["patient_id"] for r in existing_records}
    print(f"  {len(already_seeded)} patients already have records — skipping")

    to_seed = [p for p in patients if p["id"] not in already_seeded]
    print(f"  {len(to_seed)} patients to seed")

    if not to_seed:
        print("Nothing to do — all patients already have records.")
        return

    print("Building records...")
    all_records = []
    for p in to_seed:
        all_records.extend(build_records(p))
    print(f"  {len(all_records)} records built ({len(all_records) / max(len(to_seed), 1):.1f} per patient)")

    print(f"Inserting into Supabase in batches of {BATCH_SIZE}...")
    batch_insert(all_records)

    print(f"\nDone. {len(all_records)} medical records seeded across {len(to_seed)} patients.")
    print("Next step: run python scripts/build_vector_store.py to rebuild the FAISS index.")


if __name__ == "__main__":
    main()
