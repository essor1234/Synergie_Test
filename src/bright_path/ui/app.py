from __future__ import annotations

import streamlit as st

from bright_path.settings import API_URL, DEMO_NOW

st.set_page_config(
    page_title="Bright Path Scheduling",
    page_icon="📅",
    layout="wide",
)

st.title("Bright Path Scheduling")
st.caption("Shared scheduling for owners, receptionists, and tutors")

st.info(
    "The project foundation is ready. Lesson schedules and safe rescheduling "
    "will be added in the next gated phases."
)

st.subheader("Local services")
st.write(f"API: `{API_URL}`")
st.write(f"Pinned demonstration time: `{DEMO_NOW}`")
