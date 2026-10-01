"""
Virtual SPM — entry point.  Run with:  streamlit run app.py

Pages:
  1. Stiffness Calculator — CBFEM initial & secant stiffness (stiffness_page.py)
  2. Virtual Test         — virtual beam-stiffness test machine (virtual_test_page.py)
"""

import streamlit as st

st.set_page_config(page_title="Virtual SPM", page_icon="🏗️", layout="wide")

st.navigation([
    st.Page("stiffness_page.py", title="Stiffness Calculator", icon="📐", default=True),
    st.Page("virtual_test_page.py", title="Virtual Test", icon="🧪"),
]).run()
