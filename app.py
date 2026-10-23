
import streamlit as st
from dotenv import load_dotenv
from agent import research


load_dotenv()

st.set_page_config(
    page_title="ResearchPilot",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 ResearchPilot")
st.subheader("An AI-powered web research assistant")

st.write(
    "Ask a research question. ResearchPilot plans the investigation, "
    "searches the web, and generates an evidence-based report."
)

question = st.text_area(
    "What would you like to research?",
    placeholder=(
        "Example: What are the applications and challenges "
        "of agentic AI in enterprise software?"
    ),
    height=120,
)

if st.button("Research this topic", type="primary"):
    if not question.strip():
        st.warning("Please enter a research question.")
    else:
        try:
            with st.spinner(
                "Planning research, searching the web, and "
                "analyzing sources..."
            ):
                result = research(question.strip())

            st.success("Research complete!")

            st.markdown("## Research report")
            st.markdown(result["report"])

            with st.expander("View research plan"):
                for index, query in enumerate(
                    result["queries"], start=1
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

            report_text = result["report"]

            st.download_button(
                label="Download research report",
                data=report_text,
                file_name="research_report.md",
                mime="text/markdown",
            )

        except Exception as error:
            st.error(
                "The research process failed. Check your API keys, "
                "internet connection, API quotas, and terminal logs."
            )
            with st.expander("Technical details"):
                st.code(str(error))
