import streamlit as st
from db.client import search_patients_by_name, get_medical_records, add_medical_record


def render_records_tab():
    st.subheader("Patient Records")
    st.caption("Queries Supabase database directly.")

    col_s, _ = st.columns([2, 3])
    with col_s:
        search_name = st.text_input("Retrieve Patient records", placeholder="e.g. Theresa or Danielle Forbes")
        if st.button("Search", type="primary", key="patient_search_btn"):
            if not search_name.strip():
                st.warning("Enter a patient name to search.")
            else:
                st.session_state._patient_search_query = search_name.strip()
                st.session_state._patient_search_results = search_patients_by_name(search_name.strip())

    matches = st.session_state.get("_patient_search_results")

    if matches is not None:
        if not matches:
            st.error(f"No patient found matching '{st.session_state.get('_patient_search_query', '')}'.")
        else:
            if len(matches) == 1:
                patient = matches[0]
            else:
                st.caption(f"{len(matches)} patients found — select one to view their record.")
                selected_name = st.selectbox(
                    "Select patient",
                    options=[p["name"] for p in matches],
                )
                patient = next(p for p in matches if p["name"] == selected_name)

            if patient:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"### {patient['name']}")
                    st.markdown(f"**Age:** {patient['age']} &nbsp;|&nbsp; **Gender:** {patient['gender']} &nbsp;|&nbsp; **Blood Type:** {patient['blood_type']}")
                    st.markdown(f"**Condition:** {patient['medical_condition']}")
                    st.markdown(f"**Medication:** {patient['medication']}")
                with col2:
                    st.markdown(f"**Test Results:** {patient['test_results']}")
                    st.markdown(f"**Admission Type:** {patient['admission_type']}")

                st.divider()
                st.subheader("Medical Records")

                records = get_medical_records(patient["id"])

                if not records:
                    st.info("No medical records on file.")
                else:
                    for r in records:
                        with st.expander(f"{r['record_date']} — {r['diagnosis']}"):
                            st.markdown(f"**Treatment:** {r['treatment']}")
                            if r.get("notes"):
                                st.markdown(f"**Notes:** {r['notes']}")

                st.divider()
                st.subheader("Add Medical Record")

                if st.session_state.pop("_record_added", False):
                    st.success("Record added successfully.")

                with st.form("add_record_form"):
                    diagnosis = st.text_input("Diagnosis")
                    treatment = st.text_area("Treatment", height=80)
                    notes = st.text_area("Notes (optional)", height=60)
                    submitted = st.form_submit_button("Add Record", type="primary")

                if submitted:
                    if not diagnosis or not treatment:
                        st.warning("Diagnosis and treatment are required.")
                    else:
                        add_medical_record(patient["id"], diagnosis, treatment, notes)
                        st.session_state["_record_added"] = True
                        st.rerun()
