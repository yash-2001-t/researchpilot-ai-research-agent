
from typing import Any


def save_report(
    client,
    user_id: str,
    title: str,
    research_query: str,
    report_content: str,
    sources: list,
    input_mode: str = "question",
    source_types: str = "both",
    max_age_years: int | None = None,
    output_mode: str = "full_report",
    page_count: int | None = None,
    abstract_word_count: int | None = None,
    research_settings: dict | None = None,
) -> dict[str, Any]:
    """Save a report for the authenticated user."""

    record = {
        "user_id": user_id,
        "title": title.strip() or "Untitled research",
        "research_query": research_query,
        "report_content": report_content,
        "sources": sources or [],
        "input_mode": input_mode,
        "source_types": source_types,
        "max_age_years": max_age_years,
        "output_mode": output_mode,
        "page_count": page_count,
        "abstract_word_count": abstract_word_count,
        "research_settings": research_settings or {},
    }

    response = client.table("reports").insert(record).execute()

    if not response.data:
        raise RuntimeError("Supabase did not return the saved report.")

    return response.data[0]


def list_reports(client) -> list[dict[str, Any]]:
    """Return reports visible to the authenticated user, newest first."""

    response = (
        client.table("reports")
        .select(
            "id, title, research_query, output_mode, created_at"
        )
        .order("created_at", desc=True)
        .execute()
    )

    return response.data or []


def get_report(client, report_id: str) -> dict[str, Any] | None:
    """Load a single report visible to the authenticated user."""

    response = (
        client.table("reports")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def delete_report(client, report_id: str) -> None:
    """Delete a report visible to the authenticated user."""

    client.table("reports").delete().eq("id", report_id).execute()
