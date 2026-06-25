"""
15 evaluation test cases covering all agent intent types.
Each case runs against a real patient loaded into the agent session.
TEST_PATIENT should be a name that exists in your Supabase patients table.
"""

TEST_PATIENT = "Amanda Lopez"

TEST_CASES = [
    # ── Multi-intent ──────────────────────────────────────────────────────────
    {
        "id": "multi_01",
        "description": "Capstone spec scenario: book nephrologist + summarize treatment options",
        "input": "I have chronic kidney disease. Can you find me a nephrologist appointment and also explain what treatment options are available?",
        "expected_tools": ["search_doctor_availability", "book_appointment", "search_medical_info"],
        "reference": "Appointment booked with a nephrologist. Treatment options for CKD include dialysis, dietary management, blood pressure control, and in advanced cases kidney transplant.",
    },
    {
        "id": "multi_02",
        "description": "Book appointment and retrieve patient history in one message",
        "input": "Can you pull up my medical history and also find me a cardiologist appointment this week?",
        "expected_tools": ["get_patient_history", "search_doctor_availability"],
        "reference": "Medical history summarized. Available cardiologist slots returned for the requested timeframe.",
    },
    {
        "id": "multi_03",
        "description": "Medical search and add record in one message",
        "input": "I was just diagnosed with hypertension. Can you add that to my record and tell me more about managing it?",
        "expected_tools": ["update_patient_record", "search_medical_info"],
        "reference": "Record updated with hypertension diagnosis. Information provided on lifestyle changes, medication options, and monitoring.",
    },

    # ── Single-intent: booking ────────────────────────────────────────────────
    {
        "id": "book_01",
        "description": "Simple appointment booking by specialty",
        "input": "I need to see a cardiologist. What's available tomorrow?",
        "expected_tools": ["search_doctor_availability"],
        "reference": "Available cardiologist slots returned for the requested date.",
    },
    {
        "id": "book_02",
        "description": "Book a specific slot after seeing availability",
        "input": "Book me with the first available cardiologist tomorrow at 9am.",
        "expected_tools": ["search_doctor_availability", "book_appointment"],
        "reference": "Appointment confirmed with doctor, date, and time.",
    },

    # ── Single-intent: history ────────────────────────────────────────────────
    {
        "id": "history_01",
        "description": "Retrieve and summarize patient medical history",
        "input": "Can you give me a summary of my medical history?",
        "expected_tools": ["get_patient_history"],
        "reference": "Summary includes patient condition, medication, test results, and any records on file.",
    },

    # ── Single-intent: record update ──────────────────────────────────────────
    {
        "id": "record_01",
        "description": "Add a new medical record entry",
        "input": "Please add to my record that I was seen for a routine checkup today. Diagnosis: healthy. Treatment: none required.",
        "expected_tools": ["update_patient_record"],
        "reference": "Medical record added confirming diagnosis and treatment.",
    },

    # ── Single-intent: medical search ─────────────────────────────────────────
    {
        "id": "search_01",
        "description": "Search for information on a medical condition",
        "input": "What are the symptoms and treatment options for Type 2 diabetes?",
        "expected_tools": ["search_medical_info"],
        "reference": "Response covers symptoms, lifestyle interventions, medications, and includes physician disclaimer.",
    },
    {
        "id": "search_02",
        "description": "Search for medication information",
        "input": "What is metformin used for and what are the common side effects?",
        "expected_tools": ["search_medical_info"],
        "reference": "Explains metformin as a diabetes medication, lists common side effects, includes disclaimer.",
    },

    # ── RAG ───────────────────────────────────────────────────────────────────
    {
        "id": "rag_01",
        "description": "Query that should leverage FAISS patient context",
        "input": "Based on my profile, what should I be aware of regarding my condition?",
        "expected_tools": ["retrieve_patient_context"],
        "reference": "Response references patient-specific context including condition, medication, and relevant notes.",
    },

    # ── Edge cases ────────────────────────────────────────────────────────────
    {
        "id": "edge_01",
        "description": "Request outside medical scope",
        "input": "Can you help me book a flight to Miami?",
        "expected_tools": [],
        "reference": "Agent politely declines and explains it can only assist with medical-related tasks.",
    },
    {
        "id": "edge_02",
        "description": "Request for prescription (should decline with disclaimer)",
        "input": "Can you prescribe me something for my back pain?",
        "expected_tools": [],
        "reference": "Agent explains it cannot prescribe medication and recommends consulting a physician.",
    },
    {
        "id": "edge_03",
        "description": "Ambiguous request — no specialty or date specified",
        "input": "I need a doctor.",
        "expected_tools": [],
        "reference": "Agent asks clarifying questions about specialty preference and preferred date.",
    },
    {
        "id": "edge_04",
        "description": "No slots available for requested specialty on a weekend",
        "input": "Can you find me a cardiologist on Saturday?",
        "expected_tools": ["search_doctor_availability"],
        "reference": "Agent reports no availability on Saturday (no weekend slots) and suggests a weekday.",
    },

    # ── Regression ────────────────────────────────────────────────────────────
    {
        "id": "regression_01",
        "description": "Full end-to-end: chronic kidney disease scenario from capstone spec",
        "input": "My father has chronic kidney disease. Book a nephrologist appointment and summarize treatment options.",
        "expected_tools": ["search_doctor_availability", "book_appointment", "search_medical_info"],
        "reference": "Nephrologist appointment booked. Treatment options include dialysis, dietary changes, ACE inhibitors, and transplant evaluation for late-stage CKD.",
    },
]
