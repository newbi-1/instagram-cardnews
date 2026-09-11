"""Admin page (sidebar) — username/password login.

English filename so Streamlit Cloud reliably shows the multipage entry.
Korean label via page_title / console UI.
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.admin_console import render_admin_console

load_dotenv()

st.set_page_config(page_title="관리자", page_icon="🔐", layout="centered")
st.markdown("### 관리자")
render_admin_console()
