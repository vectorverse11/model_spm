"""
Virtual SPM — entry point.  Run with:  streamlit run app.py

Pages:
  1. CBFEM Virtual Test — max deflection, F, K4, initial & secant stiffness,
                           curves and CSV (stiffness_page.py, cbfem.py)
  2. Earlier model      — previous virtual test model (virtual_test_page.py)
"""

import streamlit as st

st.set_page_config(page_title="Virtual SPM", page_icon="🏗️", layout="wide")

st.navigation([
    st.Page("stiffness_page.py", title="CBFEM Virtual Test", icon="📐", default=True),
    st.Page("virtual_test_page.py", title="Earlier model", icon="🧪"),
]).run()
