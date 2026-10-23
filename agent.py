
import os
import time

from groq import Groq

from tools import search_web


MODEL = "openai/gpt-oss-20b"
MAX_RETRIES = 2
MAX_SOURCES = 4
MAX_SNIPPET_CHARS = 700


def get_client():
    """Create a Groq client."""
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing.")

    return Groq(api_key=api_key)


def generate_with_retry(client, prompt, progress_callback=None):
    """Retry temporary API errors a limited number of times."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                max_completion_tokens=4000,
            )

            return response.choices[0].message.content

        except Exception as error:
            message = str(error).lower()

            temporary = any(
                term in message
                for term in (
                    "429",
                    "rate_limit",
                    "rate limit",
                    "503",
                    "unavailable",
                    "500",
                    "internal",
                    "504",
                    "deadline_exceeded",
                    "timeout",
                    "timed out",
                )
            )

            if not temporary or attempt >= MAX_RETRIES:
                raise

            delay = 2 ** (attempt + 1)

            if progress_callback:
                progress_callback(
                    f"AI service temporarily unavailable. "
                    f"Retrying in {delay} seconds "
                    f"(attempt {attempt + 2} of {MAX_RETRIES + 1})..."
                )

            time.sleep(delay)


def research(question: str, progress_callback=None) -> dict:
    """Search the web and synthesize a concise research report."""

    if progress_callback:
        progress_callback("Preparing focused web searches...")

    # Generate three search queries without using an LLM request.
    queries = [
        question,
        f"{question} empirical research evidence",
        f"{question} limitations contradictory findings",
    ]

    all_sources = []
    failed_searches = []

    for index, query in enumerate(queries, start=1):
        if progress_callback:
            progress_callback(
                f"Searching the web: query {index} of {len(queries)}..."
            )

        try:
            results = search_web(query, max_results=3)

            for result in results:
                url = result.get("url", "")

                if url and not any(
                    source["url"] == url for source in all_sources
                ):
                    all_sources.append(result)

        except Exception as error:
            failed_searches.append(query)

            if progress_callback:
                progress_callback(
                    f"Search {index} failed; continuing with available "
                    f"evidence. Details: {error}"
                )

    if not all_sources:
        raise RuntimeError(
            "No web sources could be retrieved. Check your Tavily API key, "
            "internet connection, quota, and application logs."
        )

    # Limit the evidence sent to the LLM to control token usage.
    selected_sources = all_sources[:MAX_SOURCES]

    if progress_callback:
        progress_callback(
            f"Collected {len(all_sources)} unique sources. "
            f"Using {len(selected_sources)} for report generation..."
        )

    evidence_parts = []

    for index, source in enumerate(selected_sources, start=1):
        snippet = source.get("content", "")[:MAX_SNIPPET_CHARS]

        evidence_parts.append(
            f"SOURCE {index}\n"
            f"TITLE: {source.get('title', 'Untitled')}\n"
            f"URL: {source['url']}\n"
            f"CONTENT: {snippet}"
        )

    evidence = "\n\n".join(evidence_parts)

    synthesis_prompt = f"""
You are ResearchPilot, an evidence-based research assistant.

Research question:
{question}

Evidence from web sources:
{evidence}

Write a concise but useful research report containing:

1. Executive summary.
2. Key findings organized by theme.
3. Relevant source links using Markdown.
4. Contradictory findings, evidence limitations, and uncertainty.
5. Practical implications.

Requirements:
- Base factual claims on the supplied source material.
- Use only the supplied source URLs for citations.
- Do not invent studies, statistics, quotations, or citations.
- Distinguish empirical findings from interpretations.
- Identify important questions the available evidence cannot answer.
- If the sources do not adequately answer part of the question,
  acknowledge the gap rather than inventing an answer.
"""

    if progress_callback:
        progress_callback("Generating the research report with Groq...")

    report = generate_with_retry(
        get_client(),
        synthesis_prompt,
        progress_callback,
    )

    if not report or not report.strip():
        raise RuntimeError("Groq returned an empty research report.")

    if progress_callback:
        progress_callback("Research report complete.")

    return {
        "question": question,
        "queries": queries,
        "sources": selected_sources,
        "report": report,
        "failed_searches": failed_searches,
    }
