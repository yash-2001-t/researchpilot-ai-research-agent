
import os

import streamlit as st
from dotenv import load_dotenv

from agent import research


load_dotenv()

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

st.title("🔎 ResearchPilot")
st.subheader("An AI-powered web research assistant")

st.write(
    "Research a topic using general web sources, academic literature, "
    "or both. ResearchPilot filters and ranks sources before generating "
    "a report."
)

st.info(
    "Phase 1: question or keyword input, publication-age filters, "
    "academic discovery, source ranking and bounded follow-up searches."
)

with st.form("research_form"):
    input_mode_label = st.radio(
        "How would you like to start?",
        options=["Research question", "Keywords only"],
        horizontal=True,
    )

    user_input = st.text_area(
        "Research question or topic keywords",
        placeholder=(
            "Enter a question or a few keywords, such as: "
            "Gen Z leadership workplace feedback flexibility"
        ),
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
        "When a date limit is active, sources without a verifiable "
        "publication date are excluded. The filter uses publication "
        "dates where available, not merely the date a page was updated."
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
                progress_callback=update_progress,
            )

            status.update(
                label="Research complete!",
                state="complete",
            )

            st.success("Research completed successfully!")

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
                "Keyword coverage measures overlap between the input "
                "vocabulary and selected source text. It is not a measure "
                "of factual accuracy or research completeness."
            )

            st.markdown("## Research report")
            st.markdown(result["report"])

            st.download_button(
                label="Download research report (.md)",
                data=result["report"],
                file_name="research_report.md",
                mime="text/markdown",
            )

            with st.expander(
                f"View selected sources ({len(result['sources'])})",
                expanded=True,
            ):
                for index, source in enumerate(
                    result["sources"],
                    start=1,
                ):
                    title = source.get("title", "Untitled source")
                    url = source.get("url", "")
                    source_type = source.get("source_type", "web")
                    publication_date = (
                        source.get("publication_date")
                        or "Date not verified"
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

                    st.write(source.get("selection_reason", ""))

                    if source.get("publisher"):
                        st.caption(
                            f"Publication or site: {source['publisher']}"
                        )

                    content = source.get("content", "")
                    if content:
                        st.write(content[:1200])

                    st.divider()

            with st.expander("View research plan"):
                for index, query in enumerate(
                    result["queries"],
                    start=1,
                ):
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
                            f"**{failure['provider']}** — "
                            f"{failure['query']}"
                        )
                        st.code(failure["error"])

            if stats["undated_excluded"]:
                st.caption(
                    f"{stats['undated_excluded']} undated sources were "
                    "excluded because a publication-age limit was active."
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
                    "Wait before retrying and check your Groq usage limits."
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
