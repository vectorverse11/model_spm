"""
Virtual SPM — CBFEM Virtual Test.  Run with:  streamlit run app.py

The virtual machine calculates the max deflection, the load F at which it is
reached, K4 = F / t_p, the initial and secant stiffness, and the curves
(stiffness_page.py, cbfem.py).
"""

import streamlit as st

st.set_page_config(page_title="Virtual SPM — CBFEM Virtual Test", page_icon="🏗️",
                   layout="wide")

st.navigation([
    st.Page("stiffness_page.py", title="CBFEM Virtual Test", icon="📐", default=True),
], position="hidden").run()
