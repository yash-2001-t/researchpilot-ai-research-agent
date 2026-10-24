
from datetime import date, timedelta

from source_quality import (
    deduplicate_sources,
    extract_keywords,
    filter_by_date,
    rank_sources,
)


def test_keyword_extraction_removes_common_words():
    keywords = extract_keywords(
        "How will Gen Z differ in leadership and workplace flexibility?"
    )

    assert "leadership" in keywords
    assert "flexibility" in keywords
    assert "will" not in keywords
    assert "and" not in keywords


def test_duplicate_urls_are_removed():
    sources = [
        {
            "title": "Research paper",
            "url": "https://example.com/paper?utm_source=test",
            "content": "Research findings",
        },
        {
            "title": "Research paper duplicate",
            "url": "https://example.com/paper",
            "content": "Research findings",
        },
    ]

    result = deduplicate_sources(sources)

    assert len(result) == 1


def test_date_filter_excludes_old_and_undated_sources():
    today = date.today()

    sources = [
        {
            "title": "Recent paper",
            "url": "https://example.com/recent",
            "publication_date": today.isoformat(),
        },
        {
            "title": "Old paper",
            "url": "https://example.com/old",
            "publication_date": (
                today - timedelta(days=6 * 365)
            ).isoformat(),
        },
        {
            "title": "Undated page",
            "url": "https://example.com/undated",
            "publication_date": "",
        },
    ]

    kept, excluded, undated = filter_by_date(sources, 5)

    assert [item["title"] for item in kept] == ["Recent paper"]
    assert excluded == 2
    assert undated == 1


def test_ranking_prefers_more_relevant_source():
    sources = [
        {
            "title": "Cooking and recipes",
            "url": "https://example.com/cooking",
            "content": "Ingredients and cooking instructions",
            "source_type": "web",
        },
        {
            "title": "Gen Z leadership and workplace feedback",
            "url": "https://example.com/leadership",
            "content": (
                "Research on Gen Z managers, leadership, feedback "
                "and workplace flexibility."
            ),
            "source_type": "academic",
        },
    ]

    ranked = rank_sources(
        "Gen Z leadership and workplace feedback",
        sources,
    )

    assert ranked[0]["title"] == (
        "Gen Z leadership and workplace feedback"
    )
