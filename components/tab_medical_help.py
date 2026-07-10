import streamlit as st
from agent.tools.search_tools import search_medical_info


def render_medical_help_tab():
    st.subheader("Medical Help")
    st.caption("Queries Serper + PubMed directly.")

    col_q, _ = st.columns([2, 3])
    with col_q:
        query = st.text_input("Ask a medical question", placeholder="e.g. chronic kidney disease treatment options", key="med_search_input")

    # Clear stored result as soon as the query text changes from what was last searched
    if query != st.session_state.get("med_last_query", ""):
        st.session_state.med_search_result = None

    if st.button("Search", type="primary", key="med_search_btn"):
        if not query.strip():
            st.warning("Enter a search query.")
        else:
            with st.spinner("Searching..."):
                result = search_medical_info.invoke({"query": query.strip()})
            st.session_state.med_search_result = result
            st.session_state.med_last_query = query

    if st.session_state.get("med_search_result"):
        st.markdown(st.session_state.med_search_result)
