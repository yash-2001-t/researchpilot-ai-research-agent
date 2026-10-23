
import os
from google import genai
from tools import search_web


MODEL = "gemini-2.5-flash"


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from your .env file.")

    return genai.Client(api_key=api_key)


def plan_research(question: str, client) -> list[str]:
    """Ask the LLM to break a research question into smaller queries."""

    prompt = f"""
    You are a research planning assistant.

    Break this research question into exactly 3 focused web search queries.
    Each query should investigate a different aspect of the question.
    Make the queries specific enough to find useful evidence.

    Return only the 3 queries, one per line.
    Do not add numbering, introductions, or explanations.

    Research question: {question}
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    queries = [
        line.strip().lstrip("0123456789.-) ")
        for line in response.text.splitlines()
        if line.strip()
    ]

    queries = [q for q in queries if q]

    if not queries:
        return [question]

    return queries[:3]


def research(question: str) -> dict:
    """Plan research, search the web, and synthesize a report."""

    client = get_client()

    # Step 1: Plan the research.
    queries = plan_research(question, client)

    # Step 2: Execute the search tool for each query.
    all_sources = []

    for query in queries:
        results = search_web(query, max_results=4)

        for result in results:
            if result["url"] and not any(
                source["url"] == result["url"]
                for source in all_sources
            ):
                all_sources.append(result)

    if not all_sources:
        raise ValueError(
            "No web sources were found. Try a different research question."
        )

    # Step 3: Give the evidence to the LLM for synthesis.
    evidence = "\n\n".join(
        f"TITLE: {source['title']}\n"
        f"URL: {source['url']}\n"
        f"CONTENT: {source['content']}"
        for source in all_sources
    )

    synthesis_prompt = f"""
    You are a careful research analyst.

    Answer the user's question using the supplied web search evidence.

    USER QUESTION:
    {question}

    RESEARCH QUERIES USED:
    {queries}

    WEB EVIDENCE:
    {evidence}

    Write a concise research report with:
    1. An executive summary.
    2. Key findings with inline source links using Markdown.
    3. Areas of agreement or disagreement across sources.
    4. Limitations and unanswered questions.

    Rules:
    - Cite claims using only URLs supplied in the evidence.
    - Never invent a source, quote, statistic, or URL.
    - Distinguish evidence from your own interpretation.
    - If evidence is insufficient, explicitly say so.
    - Do not claim that a source supports something its content
      does not establish.
    - Be concise, clear, and analytical.
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=synthesis_prompt,
    )

    return {
        "question": question,
        "queries": queries,
        "sources": all_sources,
        "report": response.text or "The model returned an empty report.",
    }
