
import os
from tavily import TavilyClient


def search_web(query: str, max_results: int = 4) -> list[dict]:
    """Search the web and return useful source information."""
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise ValueError("TAVILY_API_KEY is missing from your .env file.")

    client = TavilyClient(api_key=api_key)

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
    )

    sources = []

    for item in response.get("results", []):
        sources.append({
            "title": item.get("title", "Untitled"),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        })

    return sources
