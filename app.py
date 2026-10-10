"""
Virtual SPM. Run with:  streamlit run app.py

Pages
  * CBFEM Virtual Test — beam-end connector stiffness (stiffness_page.py, cbfem.py)
  * Stub Column Test   — EN 15512 A.2.1 compression test (stub_page.py, stub.py)
"""

import streamlit as st

st.set_page_config(page_title="Virtual SPM", page_icon="🏗️", layout="wide")

st.navigation([
    st.Page("stiffness_page.py", title="CBFEM Virtual Test", icon="📐", default=True),
    st.Page("stub_page.py", title="Stub Column Test", icon="🧱"),
], position="top").run()
