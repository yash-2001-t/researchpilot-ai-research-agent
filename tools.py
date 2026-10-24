
import os
import requests


def search_web(query: str, max_results: int = 4) -> list[dict]:
    """Search the web with a bounded request timeout."""

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("TAVILY_API_KEY is missing.")

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
        },
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    return [
        {
            "title": item.get("title", "Untitled"),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        }
        for item in data.get("results", [])
    ]
