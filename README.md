
# ResearchPilot — AI Research Assistant

ResearchPilot is a lightweight LLM-powered research assistant
that converts a research question into a structured report
using live web search and AI-generated synthesis.

## Features

- LLM-generated research queries
- Web search using Tavily
- Evidence synthesis using Google's Gemini API
- Source links and research-plan visibility
- Downloadable Markdown reports
- Simple Streamlit user interface

## Architecture

User question
    -> Gemini research planner
    -> Tavily web search tool
    -> Gemini evidence synthesis
    -> Research report with source links

## Tech Stack

- Python
- Google Gemini API
- Tavily Search API
- Streamlit

## Setup

1. Clone this repository.
2. Create and activate a Python virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Create a `.env` file in the project root.
5. Add your own API keys:

   GEMINI_API_KEY=your_gemini_key
   TAVILY_API_KEY=your_tavily_key

6. Run the application:

   streamlit run app.py

## Limitations

- Search results depend on the search provider.
- Reports may contain errors or unsupported interpretations.
- Source links should be checked before relying on claims.
- The research workflow is bounded and does not independently
  decide to continue searching based on evidence gaps.

## Future Improvements

- Iterative search based on identified evidence gaps
- Source credibility and recency assessment
- Research history and saved reports
- Automated evaluation of citation accuracy
- Unit tests and structured logging

## Security

Never commit API keys, environment files, or private research data.
