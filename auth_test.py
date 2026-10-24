
import streamlit as st

from auth import sign_out_current_user
from auth_ui import render_auth_screen

st.set_page_config(page_title="ResearchPilot Auth Test", page_icon="🔐")

is_authenticated = render_auth_screen()

if is_authenticated:
    user = st.session_state.get("supabase_user", {})

    st.success("You are signed in successfully.")
    st.write("Email:", user.get("email", "Not available"))

    if st.button("Log out"):
        sign_out_current_user()
        st.rerun()
