
import os
import time
from datetime import date

from groq import Groq

from academic_sources import search_academic
from source_quality import (
    deduplicate_sources,
    evidence_coverage,
    extract_keywords,
    filter_by_date,
    rank_sources,
)
from tools import search_web


MODEL = "openai/gpt-oss-20b"
MAX_RETRIES = 2
MAX_SOURCES = 10
MAX_SNIPPET_CHARS = 1100
MAX_FOLLOW_UP_ROUNDS = 1


def get_client():
    """Create a Groq client using the configured API key."""
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing.")

    return Groq(api_key=api_key)


def generate_with_retry(client, prompt, progress_callback=None):
    """Generate text and retry temporary service errors a limited number of times."""
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


def calculate_start_date(max_age_years):
    """Return an ISO date cutoff for the requested source age."""
    if max_age_years is None:
        return None

    today = date.today()

    try:
        cutoff = today.replace(year=today.year - max_age_years)
    except ValueError:
        cutoff = today.replace(
            year=today.year - max_age_years,
            day=28,
        )

    return cutoff.isoformat()


def build_search_plan(user_input, input_mode):
    """Create bounded web and academic search queries."""
    keywords = extract_keywords(user_input, max_terms=12)
    keyword_query = " ".join(keywords) if keywords else user_input.strip()

    if input_mode == "keywords":
        research_question = (
            "Prepare a balanced research overview of the following topic: "
            + user_input.strip()
        )
        web_queries = [
            keyword_query,
            f"{keyword_query} evidence and findings",
            f"{keyword_query} limitations criticism contradictory findings",
        ]
    else:
        research_question = user_input.strip()
        web_queries = [
            user_input.strip(),
            f"{keyword_query} empirical evidence research findings",
            f"{keyword_query} limitations contradictory findings",
        ]

    academic_queries = [
        keyword_query,
        f"{keyword_query} empirical research",
    ]

    return research_question, keyword_query, web_queries, academic_queries


def collect_sources(
    web_queries,
    academic_queries,
    source_types,
    start_date,
    progress_callback=None,
):
    """Collect results from the selected search providers."""
    all_sources = []
    attempted_queries = []
    failed_searches = []

    if source_types in ("both", "web"):
        for index, query in enumerate(web_queries, start=1):
            attempted_queries.append(query)

            if progress_callback:
                progress_callback(
                    f"Searching the web: query {index} of "
                    f"{len(web_queries)}..."
                )

            try:
                all_sources.extend(
                    search_web(
                        query,
                        max_results=4,
                        start_date=start_date,
                    )
                )
            except Exception as error:
                failed_searches.append(
                    {
                        "provider": "Tavily",
                        "query": query,
                        "error": str(error),
                    }
                )

                if progress_callback:
                    progress_callback(
                        f"A web search failed; continuing with other "
                        f"sources. Details: {error}"
                    )

    if source_types in ("both", "academic"):
        for index, query in enumerate(academic_queries, start=1):
            attempted_queries.append(query)

            if progress_callback:
                progress_callback(
                    f"Searching academic literature: query {index} of "
                    f"{len(academic_queries)}..."
                )

            try:
                all_sources.extend(
                    search_academic(
                        query,
                        max_results=5,
                        start_date=start_date,
                    )
                )
            except Exception as error:
                failed_searches.append(
                    {
                        "provider": "OpenAlex",
                        "query": query,
                        "error": str(error),
                    }
                )

                if progress_callback:
                    progress_callback(
                        f"An academic search failed; continuing with "
                        f"available sources. Details: {error}"
                    )

    return all_sources, attempted_queries, failed_searches


def prepare_sources(query, all_sources, max_age_years):
    """Deduplicate, apply the date filter, rank and assess coverage."""
    unique_sources = deduplicate_sources(all_sources)

    filtered_sources, excluded_count, undated_count = filter_by_date(
        unique_sources,
        max_age_years,
    )

    ranked_sources = rank_sources(
        query,
        filtered_sources,
        max_sources=MAX_SOURCES,
    )

    coverage = evidence_coverage(query, ranked_sources)

    return {
        "unique_sources": unique_sources,
        "ranked_sources": ranked_sources,
        "excluded_count": excluded_count,
        "undated_count": undated_count,
        "coverage": coverage,
    }


def research(
    user_input: str,
    input_mode: str = "question",
    source_types: str = "both",
    max_age_years: int | None = None,
    progress_callback=None,
) -> dict:
    """Search, evaluate and synthesize evidence into a research report."""
    user_input = user_input.strip()

    if not user_input:
        raise ValueError("Enter a research question or some keywords.")

    if input_mode not in ("question", "keywords"):
        raise ValueError("Unsupported input mode.")

    if source_types not in ("both", "web", "academic"):
        raise ValueError("Unsupported source type selection.")

    if max_age_years not in (None, 1, 3, 5, 10):
        raise ValueError("Unsupported publication-age filter.")

    if progress_callback:
        progress_callback("Planning the research searches...")

    (
        research_question,
        keyword_query,
        web_queries,
        academic_queries,
    ) = build_search_plan(user_input, input_mode)

    start_date = calculate_start_date(max_age_years)

    all_sources, attempted_queries, failed_searches = collect_sources(
        web_queries,
        academic_queries,
        source_types,
        start_date,
        progress_callback,
    )

    prepared = prepare_sources(
        keyword_query,
        all_sources,
        max_age_years,
    )

    follow_up_queries = []
    follow_up_used = False

    # One bounded follow-up round when the initial evidence set appears weak.
    needs_follow_up = (
        len(prepared["ranked_sources"]) < 5
        or prepared["coverage"] < 0.30
    )

    if needs_follow_up and MAX_FOLLOW_UP_ROUNDS > 0:
        follow_up_used = True

        if progress_callback:
            progress_callback(
                "Initial evidence appears limited. Running one "
                "targeted follow-up search..."
            )

        follow_up_web = (
            f"{keyword_query} evidence limitations counterarguments"
        )
        follow_up_academic = (
            f"{keyword_query} systematic review empirical studies"
        )

        extra_sources, extra_queries, extra_failures = collect_sources(
            [follow_up_web],
            [follow_up_academic],
            source_types,
            start_date,
            progress_callback,
        )

        all_sources.extend(extra_sources)
        attempted_queries.extend(extra_queries)
        failed_searches.extend(extra_failures)
        follow_up_queries = extra_queries

        prepared = prepare_sources(
            keyword_query,
            all_sources,
            max_age_years,
        )

    selected_sources = prepared["ranked_sources"]

    if not selected_sources:
        raise RuntimeError(
            "No usable sources were found for the selected settings. "
            "Try a broader topic, a longer publication window, or both "
            "source types. Check the search error details if available."
        )

    if progress_callback:
        progress_callback(
            f"Selected {len(selected_sources)} sources after filtering "
            f"and ranking. Estimated keyword coverage: "
            f"{prepared['coverage']:.0%}."
        )

    evidence_parts = []

    for index, source in enumerate(selected_sources, start=1):
        snippet = source.get("content", "")[:MAX_SNIPPET_CHARS]
        publication_date = (
            source.get("publication_date") or "Date not verified"
        )
        source_type = source.get("source_type", "web")

        evidence_parts.append(
            f"SOURCE {index}\n"
            f"TITLE: {source.get('title', 'Untitled')}\n"
            f"URL: {source.get('url', '')}\n"
            f"SOURCE TYPE: {source_type}\n"
            f"PUBLICATION DATE: {publication_date}\n"
            f"SELECTION REASON: {source.get('selection_reason', '')}\n"
            f"CONTENT:\n{snippet}"
        )

    evidence = "\n\n".join(evidence_parts)

    synthesis_prompt = f"""
You are ResearchPilot, an evidence-based research assistant.

Research question or topic:
{research_question}

Evidence from retrieved sources:
{evidence}

Write a clear, balanced research report with:
1. An executive summary.
2. Key findings organized into meaningful themes.
3. Evidence and examples supporting the findings.
4. Contradictory findings, limitations, and uncertainty.
5. Practical implications or conclusions relevant to the topic.

Source and citation rules:
- Use only the source URLs supplied in the evidence.
- Link factual claims to relevant sources using Markdown links.
- Never invent studies, statistics, quotations, authors, or citations.
- Do not treat citation count or website reputation as proof of correctness.
- Distinguish empirical evidence from opinion and interpretation.
- For academic works, do not claim to have read the full paper when only
  its abstract or metadata was provided.
- Clearly state when the supplied evidence is insufficient to support
  a conclusion.
- Identify any important aspects of the question that remain unanswered.
- Do not imply that the sources represent an exhaustive literature review.
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
        "question": research_question,
        "input_mode": input_mode,
        "source_types": source_types,
        "max_age_years": max_age_years,
        "queries": attempted_queries,
        "follow_up_queries": follow_up_queries,
        "sources": selected_sources,
        "report": report,
        "failed_searches": failed_searches,
        "source_stats": {
            "unique_sources_found": len(prepared["unique_sources"]),
            "sources_selected": len(selected_sources),
            "excluded_by_date": prepared["excluded_count"],
            "undated_excluded": prepared["undated_count"],
            "estimated_keyword_coverage": prepared["coverage"],
            "follow_up_used": follow_up_used,
        },
    }
