
import os
from urllib.parse import urlsplit

import requests


TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def search_web(
    query: str,
    max_results: int = 4,
    start_date: str | None = None,
) -> list[dict]:
    """Search the web using Tavily and normalize the results."""
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("TAVILY_API_KEY is missing.")

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "topic": "general",
    }

    if start_date:
        payload["start_date"] = start_date

    response = requests.post(
        TAVILY_SEARCH_URL,
        json=payload,
        timeout=25,
    )
    response.raise_for_status()

    data = response.json()
    normalized = []

    for item in data.get("results", []):
        url = item.get("url", "")
        hostname = urlsplit(url).hostname or ""

        normalized.append(
            {
                "title": item.get("title") or "Untitled web result",
                "url": url,
                "content": item.get("content") or "",
                "publication_date": (
                    item.get("published_date")
                    or item.get("published_time")
                    or ""
                ),
                "source_type": "web",
                "publisher": hostname.removeprefix("www."),
                "doi": "",
                "citation_count": 0,
                "has_abstract": False,
                "open_access": None,
            }
        )

    return normalized
