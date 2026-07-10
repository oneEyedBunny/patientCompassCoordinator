import streamlit as st
import pandas as pd
from db.client import get_appointments, update_appointment_status


def render_appointments_tab():
    st.subheader("Appointment Tracking")
    st.caption("Queries Supabase database directly.")

    appts = get_appointments()

    if not appts:
        st.info("No appointments found.")
    else:
        rows = []
        for a in appts:
            rows.append({
                "ID": a["id"],
                "Patient": a["patients"]["name"] if a.get("patients") else "—",
                "Doctor": a["doctors"]["name"] if a.get("doctors") else "—",
                "Specialty": a["doctors"]["specialty"] if a.get("doctors") else "—",
                "Date": a["appointment_date"],
                "Time": str(a["appointment_time"])[:5],
                "Reason": a.get("reason", ""),
                "Status": a.get("status", "scheduled"),
            })

        df = pd.DataFrame(rows)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            patient_filter = st.text_input("Patient Name", placeholder="Search by name...", key="appt_patient_filter")
        with col2:
            status_filter = st.selectbox("Status", ["All", "scheduled", "completed", "cancelled"])
        with col3:
            doctor_options = ["All"] + sorted(df["Doctor"].dropna().unique().tolist())
            doctor_filter = st.selectbox("Doctor", doctor_options)
        with col4:
            date_filter = st.date_input("Date", value=None, key="appt_date_filter")

        filtered = df.copy()
        if patient_filter.strip():
            filtered = filtered[filtered["Patient"].str.contains(patient_filter.strip(), case=False, na=False)]
        if status_filter != "All":
            filtered = filtered[filtered["Status"] == status_filter]
        if doctor_filter != "All":
            filtered = filtered[filtered["Doctor"] == doctor_filter]
        if date_filter:
            filtered = filtered[filtered["Date"] == str(date_filter)]

        st.dataframe(filtered.drop(columns=["ID"]), width="stretch")
        st.caption(f"{len(filtered)} appointment(s) shown")

        st.divider()
        st.subheader("Update Status")

        if st.session_state.pop("_status_updated", False):
            st.success(st.session_state.pop("_status_updated_msg", "Status updated."))

        if filtered.empty:
            st.info("No appointments match the current filters.")
        else:
            appt_options = {
                f"{r['Patient']} — Dr. {r['Doctor']} on {r['Date']} at {r['Time']}": r["ID"]
                for _, r in filtered.iterrows()
            }
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                selected_label = st.selectbox("Select Appointment", list(appt_options.keys()))
            with col2:
                new_status = st.selectbox("New Status", ["completed", "cancelled", "scheduled"])
            with col3:
                st.write("")
                st.write("")
                if st.button("Update", type="primary", width="stretch"):
                    update_appointment_status(appt_options[selected_label], new_status)
                    st.session_state["_status_updated"] = True
                    st.session_state["_status_updated_msg"] = f"Status updated to '{new_status}'."
                    st.rerun()
