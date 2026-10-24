
import re
from datetime import date
from urllib.parse import urlsplit, urlunsplit


STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "also",
    "am", "an", "and", "any", "are", "as", "at", "be", "because",
    "been", "before", "being", "between", "both", "but", "by", "can",
    "could", "did", "do", "does", "during", "each", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "itself", "may", "might", "more", "most", "must", "no",
    "nor", "not", "of", "on", "once", "only", "or", "other", "our",
    "out", "over", "own", "same", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "would",
    "you", "your", "examine", "discuss", "explain", "compare",
    "identify", "explore", "consider", "extent", "implications",
    "impact", "role", "using", "use", "based", "different",
}


def extract_keywords(text: str, max_terms: int = 12) -> list[str]:
    """Extract useful topic terms while preserving their original order."""
    tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9'-]*", text.lower())

    keywords = []
    seen = set()

    for token in tokens:
        if len(token) < 3 or token in STOPWORDS or token in seen:
            continue

        seen.add(token)
        keywords.append(token)

        if len(keywords) >= max_terms:
            break

    return keywords


def parse_publication_date(value):
    """Parse a date or year; return None when it cannot be verified."""
    if not value:
        return None

    value = str(value).strip()

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass

    if re.fullmatch(r"\d{4}", value):
        try:
            return date(int(value), 1, 1)
        except ValueError:
            return None

    return None


def normalize_url(url: str) -> str:
    """Normalize a URL for duplicate detection."""
    if not url:
        return ""

    try:
        parts = urlsplit(url.strip())
        hostname = (parts.hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]

        path = parts.path.rstrip("/")

        # Ignore query strings and fragments, which often contain tracking.
        return urlunsplit(
            (
                parts.scheme.lower() or "https",
                hostname,
                path,
                "",
                "",
            )
        ).lower()
    except ValueError:
        return url.strip().lower()


def deduplicate_sources(sources: list[dict]) -> list[dict]:
    """Remove duplicates by DOI or normalized URL."""
    unique = []
    seen = set()

    for source in sources:
        doi = (source.get("doi") or "").strip().lower()
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        doi = doi.replace("https://dx.doi.org/", "")

        url_key = normalize_url(source.get("url", ""))
        key = "doi:" + doi if doi else "url:" + url_key

        if not url_key and not doi:
            continue

        if key in seen:
            continue

        seen.add(key)
        unique.append(source)

    return unique


def filter_by_date(
    sources: list[dict],
    max_age_years: int | None,
) -> tuple[list[dict], int, int]:
    """
    Apply a publication-date limit.

    Returns: kept sources, total excluded, undated sources excluded.
    When a date limit is active, sources without a verifiable date
    are excluded rather than silently treated as recent.
    """
    if max_age_years is None:
        return sources, 0, 0

    today = date.today()

    try:
        cutoff = today.replace(year=today.year - max_age_years)
    except ValueError:
        # Handle February 29 when the target year is not a leap year.
        cutoff = today.replace(
            year=today.year - max_age_years,
            day=28,
        )

    kept = []
    excluded = 0
    undated = 0

    for source in sources:
        published = parse_publication_date(
            source.get("publication_date")
        )

        if published is None:
            excluded += 1
            undated += 1
            continue

        if published < cutoff or published > today:
            excluded += 1
            continue

        kept.append(source)

    return kept, excluded, undated


def _source_tokens(source: dict) -> set[str]:
    text = " ".join(
        [
            source.get("title", ""),
            source.get("content", ""),
            source.get("publisher", ""),
        ]
    )
    return set(extract_keywords(text, max_terms=500))


def _relevance_score(query_terms: set[str], source: dict) -> float:
    """Estimate topical overlap, not factual accuracy."""
    if not query_terms:
        return 0.0

    title_terms = set(
        extract_keywords(source.get("title", ""), max_terms=100)
    )
    body_terms = _source_tokens(source)

    body_overlap = len(query_terms & body_terms) / len(query_terms)
    title_overlap = len(query_terms & title_terms) / len(query_terms)

    return min(1.0, 0.7 * body_overlap + 0.3 * title_overlap)


def rank_sources(
    query: str,
    sources: list[dict],
    max_sources: int = 10,
) -> list[dict]:
    """Rank sources by relevance, with small metadata-based tie-breakers."""
    query_terms = set(extract_keywords(query, max_terms=30))

    ranked = []

    for original in sources:
        source = dict(original)
        score = _relevance_score(query_terms, source)

        source["relevance_score"] = round(score, 3)

        matching_terms = sorted(
            query_terms & _source_tokens(source)
        )

        if matching_terms:
            reason = (
                "Topical overlap: "
                + ", ".join(matching_terms[:5])
            )
        else:
            reason = "Low direct keyword overlap; inspect before relying on it"

        if source.get("source_type") == "academic":
            reason += "; academic publication metadata available"

        if not source.get("publication_date"):
            reason += "; publication date not verified"

        source["selection_reason"] = reason

        # Relevance drives ranking. Metadata only provides a small tie-break.
        tie_break = 0.0

        if source.get("source_type") == "academic":
            tie_break += 0.02

        if source.get("doi"):
            tie_break += 0.01

        citations = source.get("citation_count") or 0
        if isinstance(citations, (int, float)) and citations > 0:
            tie_break += min(citations, 1000) / 1000 * 0.01

        source["_ranking_score"] = score + tie_break
        ranked.append(source)

    ranked.sort(
        key=lambda item: item["_ranking_score"],
        reverse=True,
    )

    result = ranked[:max_sources]

    for source in result:
        source.pop("_ranking_score", None)

    return result


def evidence_coverage(query: str, sources: list[dict]) -> float:
    """Estimate how much of the query vocabulary appears in source text."""
    query_terms = set(extract_keywords(query, max_terms=30))

    if not query_terms:
        return 1.0 if sources else 0.0

    covered = set()

    for source in sources:
        covered |= _source_tokens(source)

    return round(len(query_terms & covered) / len(query_terms), 3)
