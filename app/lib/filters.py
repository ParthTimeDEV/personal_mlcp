"""Pure filtering and sorting logic for intelligence items.

This module is browser-independent and 100% unit-testable offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


# Plain-English human-readable labels for all closed-set filter reason codes
REASON_LABELS: dict[str, str] = {
    # Phase 1 Core Filter Codes (parent.md)
    "no_compressor_keyword": "No compressor-related keyword found in text or title",
    "not_north_america": "Not confirmed as North American source or location",
    "source_not_credible": "Source is not approved, working, or credible",
    "date_missing": "Publication dateline missing on source page",
    "date_in_future": "Publication date is in the future",
    "too_old": "Published outside the configured recent-months window",
    # Phase 2 Settings-Aware Filter Codes (nikhil2.md / atlas.filter)
    "region_not_selected": "Item region is not in selected regions",
    "technology_not_selected": "Technology does not match selected technologies",
    "event_type_not_selected": "News event type is not in selected event types",
    "excluded_keyword": "Contains an excluded keyword",
    "not_industrial": "Does not meet industrial compressor requirement",
    "source_type_not_selected": "Source type is not in selected source types",
    # Switching & Compliance Codes
    "fallback_forbidden_route": "URL routed through forbidden archive, mirror, or refused host",
}


@dataclass
class ItemFilters:
    """Filter criteria combinable across multiple dimensions."""
    source_id: str | None = None
    source_type: str | None = None
    label: str | None = None  # "fact" or "claim"
    passed: bool | None = None  # True: passed only, False: failed only, None: all
    company: str | None = None
    technology: str | None = None
    event_type: str | None = None
    region: str | None = None  # "US", "CA", "MX"
    date_from: date | str | None = None
    date_to: date | str | None = None
    story_id: str | None = None
    via_fallback_only: bool = False
    query: str | None = None  # Free text query in title and key facts
    sort_by: str = "date"  # "date", "company", "source"
    sort_desc: bool = True


def parse_reason_label(code: str) -> str:
    """Return a plain-English explanation for a filter reason code."""
    return REASON_LABELS.get(code, f"Failed check: {code.replace('_', ' ')}")


def explain_reasons(reasons: list[str]) -> list[str]:
    """Return plain-English explanations for a list of reason codes."""
    return [parse_reason_label(r) for r in reasons]


def _parse_date(d: Any) -> date | None:
    if not d:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(d[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def filter_items(items: list[dict], f: ItemFilters) -> list[dict]:
    """Filter and sort a list of item dictionaries according to ItemFilters.

    Pure function: does not mutate the input items.
    """
    filtered: list[dict] = []

    date_from_parsed = _parse_date(f.date_from)
    date_to_parsed = _parse_date(f.date_to)
    query_clean = f.query.strip().casefold() if f.query else None
    company_clean = f.company.strip().casefold() if f.company else None
    tech_clean = f.technology.strip().casefold() if f.technology else None

    for item in items:
        # 1. Source ID
        if f.source_id and item.get("source_id") != f.source_id:
            continue

        # 2. Source Type
        if f.source_type and item.get("source_type") != f.source_type:
            continue

        # 3. Label (fact vs claim)
        if f.label and item.get("label") != f.label:
            continue

        # 4. Passed vs Failed (looks at filter.passed or top-level passed)
        filter_meta = item.get("filter") or {}
        item_passed = filter_meta.get("passed", True) if isinstance(filter_meta, dict) else True
        if f.passed is not None and item_passed != f.passed:
            continue

        # 5. Company match
        item_company = (item.get("company") or "").casefold()
        if company_clean and company_clean not in item_company:
            continue

        # 6. Technology match
        item_tech = (item.get("technology") or "").casefold()
        if tech_clean and tech_clean != item_tech:
            continue

        # 7. Event Type
        if f.event_type and item.get("event_type") != f.event_type:
            continue

        # 8. Region
        if f.region and item.get("region") != f.region:
            continue

        # 9. Date Range
        item_date = _parse_date(item.get("published_at"))
        if date_from_parsed:
            if not item_date or item_date < date_from_parsed:
                continue
        if date_to_parsed:
            if not item_date or item_date > date_to_parsed:
                continue

        # 10. Story ID
        if f.story_id and item.get("story_id") != f.story_id:
            continue

        # 11. Via Fallback Only
        if f.via_fallback_only and not item.get("via_fallback"):
            continue

        # 12. Free-text search in title and key facts
        if query_clean:
            title_text = (item.get("title") or "").casefold()
            key_facts = item.get("key_facts") or []
            facts_text = " ".join([kf if isinstance(kf, str) else kf.get("text", "") for kf in key_facts]).casefold()
            combined = f"{title_text} {facts_text}"
            if query_clean not in combined:
                continue

        filtered.append(item)

    # Sorting
    def sort_key(x: dict) -> Any:
        if f.sort_by == "company":
            return (x.get("company") or "").casefold()
        elif f.sort_by == "source":
            return (x.get("source_id") or "").casefold()
        else:  # default "date"
            d = _parse_date(x.get("published_at"))
            return d or date.min

    filtered.sort(key=sort_key, reverse=f.sort_desc)
    return filtered
