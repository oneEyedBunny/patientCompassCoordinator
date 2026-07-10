import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from dotenv import load_dotenv
from theme import PRIMARY, DASH_SELECT_BG

load_dotenv()

from components.tab_appointments import render_appointments_tab
from components.tab_records import render_records_tab
from components.tab_medical_help import render_medical_help_tab
from components.tab_insights import render_insights_tab
from components.tab_metrics import render_metrics_tab

st.set_page_config(
    page_title="Patient Compass — Staff Dashboard",
    page_icon="🏥",
    layout="wide",
)

st.markdown(f'<h1 style="color: {PRIMARY};">Patient Compass — Staff Dashboard</h1>', unsafe_allow_html=True)
st.caption("Internal staff view")

# Hide Streamlit's auto-generated section anchor icons (not useful in a dashboard)
st.markdown("""
<style>
[data-testid="stMarkdownAnchorLink"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# Global input + dropdown styling
st.markdown(f"""
<style>
div[data-baseweb="select"] > div:first-child {{
    border: 2px solid {PRIMARY} !important;
    border-radius: 6px !important;
    background-color: {DASH_SELECT_BG} !important;
}}
div[data-testid="stTextInput"] input {{
    background-color: #F8FAFC !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 6px !important;
}}
div[data-testid="stTextInput"] input:focus {{
    border-color: {PRIMARY} !important;
    box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.15) !important;
}}
button[data-baseweb="tab"] {{
    padding-left: 24px !important;
    padding-right: 24px !important;
}}
</style>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Appointments",
    "Patient Records",
    "Medical Help",
    "Agent Insights",
    "Metrics",
])

with tab1:
    render_appointments_tab()

with tab2:
    render_records_tab()

with tab3:
    render_medical_help_tab()

with tab4:
    render_insights_tab()

with tab5:
    render_metrics_tab()
