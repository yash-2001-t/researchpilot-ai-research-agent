
import requests


OPENALEX_API_URL = "https://api.openalex.org/works"


def reconstruct_abstract(inverted_index):
    """Reconstruct an abstract from OpenAlex's inverted index."""
    if not inverted_index:
        return ""

    try:
        max_position = max(
            position
            for positions in inverted_index.values()
            for position in positions
        )
        words = [""] * (max_position + 1)

        for word, positions in inverted_index.items():
            for position in positions:
                words[position] = word

        return " ".join(word for word in words if word)
    except (ValueError, TypeError):
        return ""


def search_academic(
    query: str,
    max_results: int = 5,
    start_date: str | None = None,
) -> list[dict]:
    """Search OpenAlex for academic works."""
    params = {
        "search": query,
        "per-page": max_results,
        "sort": "relevance_score:desc",
    }

    if start_date:
        params["filter"] = f"from_publication_date:{start_date}"

    response = requests.get(
        OPENALEX_API_URL,
        params=params,
        headers={"User-Agent": "ResearchPilot/1.0"},
        timeout=20,
    )
    response.raise_for_status()

    results = response.json().get("results", [])
    sources = []

    for item in results:
        title = item.get("title") or "Untitled academic work"
        doi = item.get("doi") or ""
        primary_location = item.get("primary_location") or {}
        location_source = primary_location.get("source") or {}
        open_access_location = item.get("best_oa_location") or {}

        url = (
            doi
            or open_access_location.get("landing_page_url")
            or primary_location.get("landing_page_url")
            or item.get("id")
            or ""
        )

        publication_date = item.get("publication_date") or ""
        abstract = reconstruct_abstract(
            item.get("abstract_inverted_index")
        )

        venue = location_source.get("display_name") or ""
        authorships = item.get("authorships") or []
        author_names = [
            (entry.get("author") or {}).get("display_name", "")
            for entry in authorships[:6]
        ]
        author_names = [name for name in author_names if name]

        metadata_parts = []

        if author_names:
            metadata_parts.append("Authors: " + ", ".join(author_names))

        if venue:
            metadata_parts.append("Publication: " + venue)

        if publication_date:
            metadata_parts.append("Publication date: " + publication_date)

        if item.get("cited_by_count") is not None:
            metadata_parts.append(
                f"Citations recorded by OpenAlex: {item['cited_by_count']}"
            )

        if item.get("type"):
            metadata_parts.append("Work type: " + item["type"])

        content = "\n".join(metadata_parts)

        if abstract:
            content += "\n\nAbstract: " + abstract
        else:
            content += "\n\nNo abstract was available in OpenAlex."

        sources.append(
            {
                "title": title,
                "url": url,
                "content": content,
                "publication_date": publication_date,
                "source_type": "academic",
                "publisher": venue,
                "doi": doi,
                "citation_count": item.get("cited_by_count", 0),
                "has_abstract": bool(abstract),
                "open_access": (
                    item.get("open_access") or {}
                ).get("is_oa"),
            }
        )

    return sources
