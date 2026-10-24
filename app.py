
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agent import research
from auth import restore_authenticated_client, sign_out_current_user
from auth_ui import render_auth_screen
from report_generator import (
    build_markdown_export,
    build_word_document,
)
from report_store import save_report, list_reports, get_report, delete_report


PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

try:
    for key in ("GROQ_API_KEY", "TAVILY_API_KEY"):
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except Exception:
    pass


st.set_page_config(
    page_title="ResearchPilot",
    page_icon="🔎",
    layout="wide",
)

# -------------------------
# Authentication
# -------------------------
if not render_auth_screen():
    st.stop()

client = restore_authenticated_client()
user = st.session_state.get("supabase_user", {})

if client is None or not user.get("id"):
    st.error(
        "Your login session could not be restored. "
        "Please sign out and sign in again."
    )
    if st.button("Return to login"):
        sign_out_current_user()
        st.rerun()
    st.stop()

# Clear a previous user's in-memory report if the account changes.
current_user_id = user["id"]
previous_user_id = st.session_state.get("research_owner_id")

if previous_user_id != current_user_id:
    st.session_state["research_owner_id"] = current_user_id
    st.session_state.pop("research_result", None)
    st.session_state.pop("research_metadata", None)
    st.session_state.pop("report_title_input", None)
    st.session_state.pop("storage_test_reports", None)

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.title("🔎 ResearchPilot")
    st.caption("AI-powered research assistant")
    st.write(f"Signed in as **{user.get('email', 'User')}**")

    if st.button("Log out", use_container_width=True):
        sign_out_current_user()
        st.session_state.pop("research_result", None)
        st.session_state.pop("research_metadata", None)
        st.rerun()

    st.divider()
    st.radio(
        "Workspace",
        options=["New research", "Research library"],
        key="workspace",
    )


# -------------------------
# Main interface
# -------------------------
st.title("🔎 ResearchPilot")
st.subheader("An AI-powered web research assistant")

st.write(
    "Investigate a topic using general web sources, academic literature, "
    "or both. Customize your report and download it for later use."
)

with st.form("research_form"):
    input_mode_label = st.radio(
        "How would you like to start?",
        options=["Research question", "Keywords only"],
        horizontal=True,
    )

    user_input = st.text_area(
        "Research question or topic keywords",
        placeholder="Example: Gen Z leadership workplace feedback flexibility",
        height=120,
    )

    source_type_label = st.selectbox(
        "Which sources should ResearchPilot use?",
        options=[
            "Both web and academic sources",
            "General web sources only",
            "Academic papers only",
        ],
    )

    date_filter_label = st.selectbox(
        "Maximum publication age",
        options=[
            "Any date",
            "Past 1 year",
            "Past 3 years",
            "Past 5 years",
            "Past 10 years",
        ],
    )

    st.divider()

    output_mode_label = st.radio(
        "What would you like to generate?",
        options=["Full report", "Abstract only"],
        horizontal=True,
    )

    if output_mode_label == "Full report":
        page_count = st.select_slider(
            "Approximate Word-document length",
            options=[2, 5, 10, 15],
            value=5,
            format_func=lambda value: f"{value} pages",
        )
    else:
        page_count = 5
        st.caption(
            "Abstract mode produces a standalone abstract of approximately "
            "200–300 words. Page length does not apply."
        )

    st.caption(
        "Page counts are approximate and depend on document formatting. "
        "With a date limit active, sources without a verifiable "
        "publication date are excluded."
    )

    submitted = st.form_submit_button(
        "Research this topic",
        type="primary",
        use_container_width=True,
    )


# -------------------------
# Run research only when submitted
# -------------------------
if submitted:
    if not user_input.strip():
        st.warning("Please enter a research question or some keywords.")
    else:
        input_mode = (
            "keywords"
            if input_mode_label == "Keywords only"
            else "question"
        )

        source_types = {
            "Both web and academic sources": "both",
            "General web sources only": "web",
            "Academic papers only": "academic",
        }[source_type_label]

        max_age_years = {
            "Any date": None,
            "Past 1 year": 1,
            "Past 3 years": 3,
            "Past 5 years": 5,
            "Past 10 years": 10,
        }[date_filter_label]

        output_mode = (
            "abstract"
            if output_mode_label == "Abstract only"
            else "full_report"
        )

        status = st.status("Starting research...", expanded=True)

        def update_progress(message):
            status.write(message)
            status.update(label=message, state="running")

        try:
            result = research(
                user_input=user_input.strip(),
                input_mode=input_mode,
                source_types=source_types,
                max_age_years=max_age_years,
                output_mode=output_mode,
                page_count=page_count,
                progress_callback=update_progress,
            )

            # Persist both the result and its settings across reruns.
            st.session_state["research_result"] = result
            st.session_state["research_metadata"] = {
                "user_id": current_user_id,
                "query": user_input.strip(),
                "input_mode": input_mode,
                "source_types": source_types,
                "max_age_years": max_age_years,
                "output_mode": output_mode,
                "page_count": page_count,
                "date_filter_label": date_filter_label,
                "source_type_label": source_type_label,
                "output_mode_label": output_mode_label,
            }
            st.session_state.pop("report_title_input", None)

            status.update(
                label="Research complete!",
                state="complete",
            )

        except Exception as error:
            status.update(
                label="Research failed",
                state="error",
            )

            error_message = str(error).lower()

            if "429" in error_message or "rate_limit" in error_message:
                st.warning(
                    "The AI service has reached a usage limit. "
                    "Check your Groq usage limits before retrying."
                )
            elif "503" in error_message or "unavailable" in error_message:
                st.warning(
                    "The AI service is temporarily unavailable. "
                    "Please try again later."
                )
            else:
                st.error(
                    "The research process could not be completed. "
                    "Check the technical details below."
                )

            with st.expander("Technical error details"):
                st.code(str(error))


# -------------------------
# Display the stored result
# This runs on subsequent reruns too.
# -------------------------
result = st.session_state.get("research_result")
metadata = st.session_state.get("research_metadata")

# Never display a previous user's result.
if metadata and metadata.get("user_id") != current_user_id:
    result = None
    st.session_state.pop("research_result", None)
    st.session_state.pop("research_metadata", None)

if result and metadata:
    st.success("Research report ready.")

    stats = result["source_stats"]
    metric_columns = st.columns(3)

    metric_columns[0].metric(
        "Sources selected",
        stats["sources_selected"],
    )
    metric_columns[1].metric(
        "Excluded by date",
        stats["excluded_by_date"],
    )
    metric_columns[2].metric(
        "Estimated keyword coverage",
        f"{stats['estimated_keyword_coverage']:.0%}",
    )

    st.caption(
        "Keyword coverage estimates vocabulary overlap in the selected "
        "source text. It is not a measure of accuracy or research completeness."
    )

    st.markdown("## Research output")
    st.markdown(result["report"])

    # -------------------------
    # Save report
    # -------------------------
    st.divider()
    st.subheader("Save to your research library")

    default_title = metadata["query"][:80]

    report_title = st.text_input(
        "Report title",
        value=default_title,
        key="report_title_input",
    )

    if st.button(
        "Save report",
        type="primary",
        key="save_report_button",
    ):
        try:
            saved_report = save_report(
                client=client,
                user_id=current_user_id,
                title=report_title,
                research_query=metadata["query"],
                report_content=result["report"],
                sources=result["sources"],
                input_mode=metadata["input_mode"],
                source_types=metadata["source_types"],
                max_age_years=metadata["max_age_years"],
                output_mode=result["output_mode"],
                page_count=(
                    metadata["page_count"]
                    if metadata["output_mode"] == "full_report"
                    else None
                ),
                research_settings={
                    "date_filter": metadata["date_filter_label"],
                    "source_type_label": metadata["source_type_label"],
                    "output_mode_label": metadata["output_mode_label"],
                },
            )
            st.session_state["last_saved_report_id"] = saved_report["id"]
            st.success(
                f"Report saved successfully: {saved_report['title']}"
            )
        except Exception as error:
            st.error(f"Could not save report: {error}")

    # -------------------------
    # Downloads
    # -------------------------
    markdown_content = build_markdown_export(
        result["report"],
        result["sources"],
    )

    document_title = (
        "Research Abstract"
        if result["output_mode"] == "abstract"
        else "Research Report"
    )

    word_content = build_word_document(
        report=result["report"],
        sources=result["sources"],
        title=document_title,
    )

    download_col1, download_col2 = st.columns(2)

    with download_col1:
        st.download_button(
            label="Download Markdown (.md)",
            data=markdown_content,
            file_name="researchpilot_report.md",
            mime="text/markdown",
            use_container_width=True,
            key="download_markdown",
        )

    with download_col2:
        st.download_button(
            label="Download Word (.docx)",
            data=word_content,
            file_name="researchpilot_report.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            use_container_width=True,
            key="download_word",
        )

    # -------------------------
    # Selected sources
    # -------------------------
    with st.expander(
        f"View selected sources ({len(result['sources'])})",
        expanded=True,
    ):
        for index, source in enumerate(result["sources"], start=1):
            source_title = source.get("title", "Untitled source")
            url = source.get("url", "")
            source_type = source.get("source_type", "web")
            publication_date = (
                source.get("publication_date") or "Date not verified"
            )
            relevance = source.get("relevance_score", 0)

            if url:
                st.markdown(f"**{index}. [{source_title}]({url})**")
            else:
                st.markdown(f"**{index}. {source_title}**")

            st.caption(
                f"Type: {source_type.title()} | "
                f"Publication date: {publication_date} | "
                f"Keyword relevance: {relevance:.0%}"
            )

            st.write(source.get("selection_reason", ""))

            if source.get("publisher"):
                st.caption(f"Publication or site: {source['publisher']}")

            content = source.get("content", "")
            if content:
                st.write(content[:1200])

            st.divider()

    # -------------------------
    # Research plan and failures
    # -------------------------
    with st.expander("View research plan"):
        for index, query in enumerate(result["queries"], start=1):
            st.write(f"{index}. {query}")

        if result["follow_up_queries"]:
            st.markdown("**Follow-up searches**")
            for query in result["follow_up_queries"]:
                st.write(f"- {query}")

        st.write(
            "Follow-up search used: "
            + ("Yes" if stats["follow_up_used"] else "No")
        )

    if result["failed_searches"]:
        with st.expander(
            f"Searches with errors ({len(result['failed_searches'])})"
        ):
            for failure in result["failed_searches"]:
                st.write(
                    f"**{failure['provider']}** — {failure['query']}"
                )
                st.code(failure["error"])

    if stats["undated_excluded"]:
        st.caption(
            f"{stats['undated_excluded']} undated sources were excluded "
            "because a publication-age limit was active."
        )
