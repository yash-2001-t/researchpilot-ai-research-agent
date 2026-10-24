
import streamlit as st

from auth import restore_authenticated_client, sign_out_current_user
from auth_ui import render_auth_screen
from report_store import save_report, list_reports, get_report, delete_report

st.set_page_config(page_title="ResearchPilot Storage Test", page_icon="🧪")

st.title("ResearchPilot — Storage Test")

# Require the user to sign in first.
if not render_auth_screen():
    st.stop()

client = restore_authenticated_client()
user = st.session_state.get("supabase_user", {})

if client is None or not user.get("id"):
    st.error("Your session could not be restored. Please sign out and sign in again.")
    st.stop()

st.success(f"Signed in as {user.get('email', 'Unknown user')}")

if st.button("Log out"):
    sign_out_current_user()
    st.rerun()

st.divider()
st.subheader("1. Save a test report")

title = st.text_input("Report title", value="ResearchPilot storage test")
query = st.text_input(
    "Research question",
    value="How is generative AI being adopted by enterprises?"
)

if st.button("Save test report"):
    try:
        saved = save_report(
            client=client,
            user_id=user["id"],
            title=title,
            research_query=query,
            report_content="This is a test report created by ResearchPilot.",
            sources=[],
            input_mode="question",
            source_types="both",
            output_mode="full_report",
        )
        st.session_state["storage_test_report_id"] = saved["id"]
        st.success(f"Report saved successfully. ID: {saved['id']}")
    except Exception as exc:
        st.error(f"Could not save report: {exc}")

st.divider()
st.subheader("2. View saved reports")

if st.button("Load my reports"):
    try:
        reports = list_reports(client)
        st.session_state["storage_test_reports"] = reports
    except Exception as exc:
        st.error(f"Could not load reports: {exc}")

for report in st.session_state.get("storage_test_reports", []):
    with st.expander(f"{report['title']} — {report['created_at']}"):
        st.write("Research question:", report["research_query"])
        st.write("Report ID:", report["id"])

        if st.button("Open report", key=f"open_{report['id']}"):
            try:
                full_report = get_report(client, report["id"])
                if full_report:
                    st.session_state["opened_test_report"] = full_report
                else:
                    st.warning("Report not found.")
            except Exception as exc:
                st.error(f"Could not open report: {exc}")

        if st.button("Delete report", key=f"delete_{report['id']}"):
            try:
                delete_report(client, report["id"])
                st.session_state["storage_test_reports"] = [
                    item
                    for item in st.session_state["storage_test_reports"]
                    if item["id"] != report["id"]
                ]
                st.success("Report deleted.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not delete report: {exc}")

opened = st.session_state.get("opened_test_report")
if opened:
    st.divider()
    st.subheader("Opened report")
    st.write(opened["title"])
    st.text_area(
        "Report content",
        value=opened["report_content"],
        height=200,
        disabled=True,
    )
