
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agent import research
from auth import restore_authenticated_client, sign_out_current_user
from auth_ui import render_auth_screen
from report_generator import build_markdown_export, build_word_document
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


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------
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

user_id = user["id"]

# Reset private in-memory state when the signed-in user changes.
if st.session_state.get("research_owner_id") != user_id:
    for key in (
        "research_result",
        "research_metadata",
        "opened_library_report",
        "opened_library_report_id",
        "report_title_input",
        "last_saved_report_id",
        "confirm_delete_report_id",
    ):
        st.session_state.pop(key, None)

    st.session_state["research_owner_id"] = user_id

if "workspace" not in st.session_state:
    st.session_state["workspace"] = "New research"

if "library_view" not in st.session_state:
    st.session_state["library_view"] = "list"


# ---------------------------------------------------------
# Reusable rendering helpers
# ---------------------------------------------------------
def render_downloads(report, sources, filename_prefix, output_mode="full_report"):
    markdown_content = build_markdown_export(report, sources or [])

    document_title = (
        "Research Abstract"
        if output_mode == "abstract"
        else "Research Report"
    )

    word_content = build_word_document(
        report=report,
        sources=sources or [],
        title=document_title,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "Download Markdown (.md)",
            data=markdown_content,
            file_name=f"{filename_prefix}.md",
            mime="text/markdown",
            use_container_width=True,
            key=f"{filename_prefix}_markdown_download",
        )

    with col2:
        st.download_button(
            "Download Word (.docx)",
            data=word_content,
            file_name=f"{filename_prefix}.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            use_container_width=True,
            key=f"{filename_prefix}_word_download",
        )


def render_sources(sources):
    sources = sources or []

    with st.expander(f"View selected sources ({len(sources)})"):
        if not sources:
            st.info("No source details were saved with this report.")

        for index, source in enumerate(sources, start=1):
            title = source.get("title", "Untitled source")
            url = source.get("url", "")
            source_type = source.get("source_type", "web")
            publication_date = (
                source.get("publication_date") or "Date not verified"
            )
            relevance = source.get("relevance_score", 0)

            if url:
                st.markdown(f"**{index}. [{title}]({url})**")
            else:
                st.markdown(f"**{index}. {title}**")

            st.caption(
                f"Type: {source_type.title()} | "
                f"Publication date: {publication_date} | "
                f"Keyword relevance: {relevance:.0%}"
            )

            if source.get("selection_reason"):
                st.write(source["selection_reason"])

            if source.get("publisher"):
                st.caption(f"Publication or site: {source['publisher']}")

            content = source.get("content", "")
            if content:
                st.write(content[:1200])

            st.divider()


# ---------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------
with st.sidebar:
    st.title("🔎 ResearchPilot")
    st.caption("AI-powered web research assistant")
    st.write(f"Signed in as **{user.get('email', 'User')}**")

    workspace = st.radio(
        "Workspace",
        options=["New research", "Research library"],
        key="workspace",
    )

    st.divider()

    if st.button("Log out", use_container_width=True):
        sign_out_current_user()
        for key in (
            "research_result",
            "research_metadata",
            "opened_library_report",
            "opened_library_report_id",
            "confirm_delete_report_id",
        ):
            st.session_state.pop(key, None)
        st.rerun()


# ---------------------------------------------------------
# Workspace 1: New research
# ---------------------------------------------------------
if workspace == "New research":
    st.session_state["library_view"] = "list"

    st.title("🔎 ResearchPilot")
    st.subheader("An AI-powered web research assistant")
    st.write(
        "Investigate a topic using general web sources, academic literature, "
        "or both. Customize your report and download it for later use."
    )

    # These controls are OUTSIDE the form so switching modes reruns
    # Streamlit immediately and changes the displayed length selector.
    output_mode_label = st.radio(
        "What would you like to generate?",
        options=["Full report", "Abstract only"],
        horizontal=True,
        key="output_mode_selector",
    )

    if output_mode_label == "Full report":
        page_count = st.select_slider(
            "Approximate Word-document length",
            options=list(range(1, 16)),
            value=5,
            format_func=lambda value: (
                f"{value} page" if value == 1 else f"{value} pages"
            ),
            key="report_page_count",
        )
        abstract_word_count = 1000

        st.caption(
            "Each page represents approximately 400 words. "
            "Actual Word-document pagination may vary."
        )
    else:
        page_count = 5

        abstract_word_count = st.select_slider(
            "Target abstract length",
            options=list(range(200, 5001, 200)),
            value=1000,
            format_func=lambda value: f"{value:,} words",
            key="abstract_word_count",
        )

        st.caption(
            "The abstract uses a title, an Abstract heading, and continuous "
            "academic prose without bullets or additional section headings. "
            "Longer selections produce extended abstracts or research syntheses."
        )

    st.divider()

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

        st.caption(
            "With a publication-age limit active, sources without a "
            "verifiable publication date are excluded."
        )

        submitted = st.form_submit_button(
            "Research this topic",
            type="primary",
            use_container_width=True,
        )

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
                    abstract_word_count=abstract_word_count,
                    progress_callback=update_progress,
                )

                st.session_state["research_result"] = result
                st.session_state["research_metadata"] = {
                    "user_id": user_id,
                    "query": user_input.strip(),
                    "input_mode": input_mode,
                    "source_types": source_types,
                    "max_age_years": max_age_years,
                    "output_mode": output_mode,
                    "page_count": (
                        page_count if output_mode == "full_report" else None
                    ),
                    "abstract_word_count": (
                        abstract_word_count
                        if output_mode == "abstract"
                        else None
                    ),
                    "date_filter_label": date_filter_label,
                    "source_type_label": source_type_label,
                    "output_mode_label": output_mode_label,
                }

                st.session_state.pop("report_title_input", None)
                status.update(label="Research complete!", state="complete")

            except Exception as error:
                status.update(label="Research failed", state="error")
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

    result = st.session_state.get("research_result")
    metadata = st.session_state.get("research_metadata")

    if result and metadata and metadata.get("user_id") == user_id:
        st.success("Research output ready!")

        stats = result["source_stats"]
        metrics = st.columns(3)

        metrics[0].metric("Sources selected", stats["sources_selected"])
        metrics[1].metric("Excluded by date", stats["excluded_by_date"])
        metrics[2].metric(
            "Estimated keyword coverage",
            f"{stats['estimated_keyword_coverage']:.0%}",
        )

        st.caption(
            "Keyword coverage estimates vocabulary overlap. "
            "It is not a measure of accuracy or research completeness."
        )

        if result["output_mode"] == "abstract":
            actual_target = (
                result.get("abstract_word_count")
                or metadata.get("abstract_word_count")
                or 1000
            )
            st.caption(f"Requested abstract length: {actual_target:,} words")
        else:
            actual_pages = result.get("page_count") or metadata.get("page_count")
            st.caption(
                f"Requested report length: {actual_pages} pages "
                f"(approximately {actual_pages * 400:,} words)"
            )

        st.markdown("## Research output")
        st.markdown(result["report"])

        st.divider()
        st.subheader("Save to your research library")

        st.text_input(
            "Report title",
            value=metadata["query"][:80],
            key="report_title_input",
        )

        if st.button(
            "Save report",
            type="primary",
            key="save_report_button",
        ):
            try:
                saved = save_report(
                    client=client,
                    user_id=user_id,
                    title=st.session_state["report_title_input"],
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
                    abstract_word_count=(
                        metadata["abstract_word_count"]
                        if metadata["output_mode"] == "abstract"
                        else None
                    ),
                    research_settings={
                        "date_filter": metadata["date_filter_label"],
                        "source_type_label": metadata["source_type_label"],
                        "output_mode_label": metadata["output_mode_label"],
                        "page_count": metadata["page_count"],
                        "abstract_word_count": metadata["abstract_word_count"],
                    },
                )

                st.session_state["last_saved_report_id"] = saved["id"]
                st.success(f"Report saved successfully: {saved['title']}")

            except Exception as error:
                st.error(f"Could not save report: {error}")

        render_downloads(
            result["report"],
            result["sources"],
            "researchpilot_abstract"
            if result["output_mode"] == "abstract"
            else "researchpilot_report",
            result["output_mode"],
        )

        render_sources(result["sources"])

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


# ---------------------------------------------------------
# Workspace 2: Research library
# ---------------------------------------------------------
elif st.session_state["library_view"] == "list":
    st.title("📚 Research library")
    st.write("Your saved research, all in one place.")

    try:
        reports = list_reports(client)
    except Exception as error:
        reports = []
        st.error(f"Could not load your research library: {error}")

    if not reports:
        st.info(
            "Your library is empty. Generate a report in New research "
            "and select Save report to add it here."
        )
    else:
        st.caption(f"{len(reports)} saved report(s)")

        for report in reports:
            report_id = report["id"]
            title = report.get("title") or "Untitled research"
            created_at = report.get("created_at", "")
            query = report.get("research_query", "")

            with st.container(border=True):
                open_col, delete_col = st.columns([5, 1])

                with open_col:
                    if st.button(
                        f"📄  {title}",
                        key=f"open_report_{report_id}",
                        use_container_width=True,
                    ):
                        st.session_state["opened_library_report_id"] = report_id
                        st.session_state["library_view"] = "report"
                        st.rerun()

                    st.caption(
                        f"Saved {created_at}"
                        + (f" · {query}" if query and query != title else "")
                    )

                with delete_col:
                    if st.button(
                        "🗑️",
                        key=f"delete_report_{report_id}",
                        help="Delete this report",
                        use_container_width=True,
                    ):
                        st.session_state["confirm_delete_report_id"] = report_id

                if st.session_state.get("confirm_delete_report_id") == report_id:
                    st.warning(f"Delete **{title}** permanently?")
                    confirm_col, cancel_col = st.columns(2)

                    with confirm_col:
                        if st.button(
                            "Confirm delete",
                            key=f"confirm_delete_{report_id}",
                            type="primary",
                        ):
                            try:
                                delete_report(client, report_id)

                                if (
                                    st.session_state.get(
                                        "opened_library_report_id"
                                    )
                                    == report_id
                                ):
                                    st.session_state.pop(
                                        "opened_library_report_id", None
                                    )
                                    st.session_state["library_view"] = "list"

                                st.session_state.pop(
                                    "confirm_delete_report_id", None
                                )
                                st.success("Report deleted.")
                                st.rerun()

                            except Exception as error:
                                st.error(f"Could not delete report: {error}")

                    with cancel_col:
                        if st.button(
                            "Cancel",
                            key=f"cancel_delete_{report_id}",
                        ):
                            st.session_state.pop(
                                "confirm_delete_report_id", None
                            )
                            st.rerun()


# ---------------------------------------------------------
# Workspace 2: Dedicated report viewer
# ---------------------------------------------------------
else:
    report_id = st.session_state.get("opened_library_report_id")

    if st.button("← Back to library", key="back_to_library"):
        st.session_state["library_view"] = "list"
        st.session_state.pop("opened_library_report_id", None)
        st.rerun()

    if not report_id:
        st.session_state["library_view"] = "list"
        st.rerun()

    try:
        saved_report = get_report(client, report_id)
    except Exception as error:
        saved_report = None
        st.error(f"Could not load this report: {error}")

    if not saved_report:
        st.warning("This report could not be found. It may have been deleted.")
        if st.button("Return to library"):
            st.session_state["library_view"] = "list"
            st.session_state.pop("opened_library_report_id", None)
            st.rerun()
    else:
        st.title(saved_report.get("title") or "Saved report")
        st.caption(
            f"Research question: {saved_report.get('research_query', '')}"
        )

        created_at = saved_report.get("created_at")
        if created_at:
            st.caption(f"Created: {created_at}")

        output_mode = saved_report.get("output_mode", "full_report")
        page_count = saved_report.get("page_count")
        abstract_word_count = saved_report.get("abstract_word_count")

        if output_mode == "abstract" and abstract_word_count:
            st.caption(
                f"Requested abstract length: {abstract_word_count:,} words"
            )
        elif output_mode == "full_report" and page_count:
            st.caption(
                f"Requested report length: {page_count} pages "
                f"(approximately {page_count * 400:,} words)"
            )

        report_content = saved_report.get("report_content", "")
        sources = saved_report.get("sources") or []

        st.divider()
        st.markdown(report_content)

        st.divider()
        render_downloads(
            report_content,
            sources,
            f"saved_report_{report_id}",
            output_mode,
        )
        render_sources(sources)
