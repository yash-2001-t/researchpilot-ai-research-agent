
import os

import streamlit as st
from dotenv import load_dotenv

from agent import research


load_dotenv()

# Load credentials from Streamlit Cloud Secrets when available.
try:
    for key in ("GROQ_API_KEY", "TAVILY_API_KEY"):
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except Exception:
    # Local development can use the .env file.
    pass


st.set_page_config(
    page_title="ResearchPilot",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 ResearchPilot")
st.subheader("An AI-powered web research assistant")

st.write(
    "Enter a research question. ResearchPilot plans the investigation, "
    "searches the web, and generates a report with source links."
)

question = st.text_area(
    "What would you like to research?",
    placeholder=(
        "Example: How will Gen Z differ from previous generations "
        "as managers?"
    ),
    height=120,
)

if st.button("Research this topic", type="primary"):
    if not question.strip():
        st.warning("Please enter a research question.")

    else:
        status = st.status(
            "Starting research...",
            expanded=True,
        )

        def update_progress(message):
            status.write(message)
            status.update(
                label=message,
                state="running",
            )

        try:
            result = research(
                question.strip(),
                progress_callback=update_progress,
            )

            status.update(
                label="Research complete!",
                state="complete",
            )

            st.success("Research completed successfully!")

            st.markdown("## Research report")
            st.markdown(result["report"])

            if result.get("failed_searches"):
                with st.expander("Searches that failed"):
                    for query in result["failed_searches"]:
                        st.write(f"- {query}")

            with st.expander("View research plan"):
                for index, query in enumerate(
                    result["queries"],
                    start=1,
                ):
                    st.write(f"{index}. {query}")

            with st.expander(
                f"View sources ({len(result['sources'])})"
            ):
                for source in result["sources"]:
                    st.markdown(
                        f"**[{source['title']}]({source['url']})**"
                    )
                    st.write(source["content"])
                    st.divider()

            st.download_button(
                label="Download research report",
                data=result["report"],
                file_name="research_report.md",
                mime="text/markdown",
            )

        except Exception as error:
            status.update(
                label="Research failed",
                state="error",
            )

            st.error(
                "The research process could not be completed. "
                "Check the error details below."
            )

            with st.expander("Technical error details", expanded=True):
                st.code(str(error))
