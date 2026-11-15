"""Pure business and presentation logic for the Dashboard screen.

This module is browser-independent and 100% unit-testable offline.
Calculates run metrics, prepares tables, formats story clusters,
prepares chart datasets, and formats in-memory CSV/JSON exports.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Any

from atlas.models import Item, OutputEnvelope, RunLog, SourceSummary, StoryCluster
from app.lib.filters import explain_reasons


def compute_run_metrics(
    envelope: OutputEnvelope,
    log: RunLog | None = None,
    clean_items: list[dict] | None = None,
) -> dict[str, Any]:
    """Compute top-level telemetry metrics for the run overview.

    Handles real Volume outputs, logs, and synthetic fixtures safely.
    """
    sources = envelope.sources or []
    items = envelope.items or []

    # Calculate collected and passed counts
    if clean_items:
        collected_count = len(clean_items)
        passed_count = sum(1 for it in clean_items if (it.get("filter") or {}).get("passed", False))
        fallback_count = sum(1 for it in clean_items if it.get("via_fallback"))
    else:
        collected_count = sum(s.items_collected for s in sources)
        passed_count = sum(s.items_passed for s in sources) if sources else len(items)
        fallback_count = sum(1 for it in items if it.via_fallback)

    dropped_count = max(0, collected_count - passed_count)

    # Count refused sources (blocked status or non-fallback with refusal note)
    refused_sources = 0
    for s in sources:
        kind = getattr(s, "kind", "registered") or "registered"
        status_lower = (s.status or "").lower()
        note_lower = (s.note or "").lower()
        if kind != "fallback" and (status_lower in ("blocked", "refused") or "refused" in note_lower):
            refused_sources += 1

    # Extract scope
    scope_tech = envelope.scope.technology if envelope.scope else "industrial compressors"
    scope_region = envelope.scope.region if envelope.scope else "US"

    # Extract settings summary
    settings_dict: dict[str, Any] = {}
    if envelope.settings_used:
        settings_dict = envelope.settings_used.model_dump(mode="json")

    return {
        "run_id": envelope.run_id,
        "generated_at": envelope.generated_at,
        "scope_tech": scope_tech,
        "scope_region": scope_region,
        "collected_count": collected_count,
        "passed_count": passed_count,
        "dropped_count": dropped_count,
        "stories_count": len(envelope.stories or []),
        "refused_sources_count": refused_sources,
        "fallback_items_count": fallback_count,
        "candidates_considered": envelope.candidates_considered or 0,
        "settings_used": settings_dict,
    }


def prepare_sources_summary(sources: list[SourceSummary]) -> list[dict[str, Any]]:
    """Format SourceSummary records into structured rows for the Sources table.

    Highlights refused sources and marks discovered vs fallback sources clearly.
    """
    rows: list[dict[str, Any]] = []
    for s in sources:
        kind = s.kind or "registered"
        status = s.status or "unknown"
        note = s.note or ""

        # Determine user-facing kind label
        if kind == "discovered":
            kind_label = "Discovered (Not Approved)"
        elif kind == "fallback":
            target = s.fallback_for or "refused source"
            kind_label = f"Fallback (for {target})"
        else:
            kind_label = "Registered"

        # Check refusal status (fallback sources are active stand-ins, not refused)
        status_lower = status.lower()
        note_lower = note.lower()
        is_refused = kind != "fallback" and (status_lower in ("blocked", "refused") or "refused" in note_lower)

        rows.append({
            "source_id": s.source_id,
            "name": s.name,
            "status": status,
            "items_collected": s.items_collected,
            "items_passed": s.items_passed,
            "kind": kind,
            "kind_label": kind_label,
            "fallback_for": s.fallback_for,
            "note": note,
            "is_refused": is_refused,
        })
    return rows


def prepare_stories_view(
    stories: list[StoryCluster],
    items_by_id: dict[str, dict],
) -> list[dict[str, Any]]:
    """Structure story clusters, prioritizing those verified by >= 2 independent sources."""
    formatted_stories: list[dict[str, Any]] = []

    for sc in stories:
        source_count = len(sc.source_ids)
        is_multi_source = source_count >= 2

        # Resolve associated items
        story_items: list[dict] = []
        for item_id in sc.item_ids:
            if item_id in items_by_id:
                story_items.append(items_by_id[item_id])

        formatted_stories.append({
            "story_id": sc.story_id,
            "headline": sc.headline,
            "company": sc.company or "Various / Not stated",
            "product": sc.product or "N/A",
            "event_type": sc.event_type or "General",
            "source_ids": sc.source_ids,
            "source_count": source_count,
            "is_multi_source": is_multi_source,
            "item_ids": sc.item_ids,
            "items": story_items,
            "first_published": sc.first_published or "N/A",
            "last_published": sc.last_published or "N/A",
            "via_fallback_count": sc.via_fallback_count,
        })

    # Sort: multi-source stories first, then by source count descending, then headline
    formatted_stories.sort(
        key=lambda s: (1 if s["is_multi_source"] else 0, s["source_count"], s["headline"]),
        reverse=True,
    )
    return formatted_stories


def prepare_chart_data(items: list[dict]) -> dict[str, dict[str, int]]:
    """Aggregate items for Streamlit native charts.

    Returns:
        Dictionary mapping chart names to label->count mapping.
    """
    if not items:
        return {
            "items_per_source": {},
            "top_companies": {},
            "items_per_event_type": {},
            "items_per_month": {},
        }

    source_counter: Counter[str] = Counter()
    company_counter: Counter[str] = Counter()
    event_counter: Counter[str] = Counter()
    month_counter: Counter[str] = Counter()

    for item in items:
        # Items per source
        src = item.get("source_name") or item.get("source_id") or "Unknown"
        source_counter[src] += 1

        # Items per company (exclude None / empty)
        comp = item.get("company")
        if comp and str(comp).strip():
            company_counter[str(comp).strip()] += 1

        # Items per event type
        evt = item.get("event_type") or "unspecified"
        event_counter[evt] += 1

        # Items per month (YYYY-MM)
        pub = item.get("published_at")
        if pub and isinstance(pub, str) and len(pub) >= 7:
            month_key = pub[:7]
            month_counter[month_key] += 1

    # Top 10 companies
    top_companies_dict = dict(company_counter.most_common(10))

    # Months sorted chronologically
    sorted_months = dict(sorted(month_counter.items()))

    return {
        "items_per_source": dict(source_counter),
        "top_companies": top_companies_dict,
        "items_per_event_type": dict(event_counter),
        "items_per_month": sorted_months,
    }


def prepare_items_csv(items: list[dict]) -> str:
    """Serialize a list of item dictionaries to an in-memory CSV string."""
    output = io.StringIO()
    fieldnames = [
        "id",
        "published_at",
        "company",
        "product",
        "technology",
        "event_type",
        "region",
        "label",
        "passed",
        "title",
        "key_facts",
        "source_name",
        "source_id",
        "source_url",
        "via_fallback",
        "fallback_for",
        "reasons",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for item in items:
        filter_meta = item.get("filter") or {}
        passed = filter_meta.get("passed", True) if isinstance(filter_meta, dict) else True
        reasons = filter_meta.get("reasons", []) if isinstance(filter_meta, dict) else []

        # Flatten key facts
        raw_facts = item.get("key_facts") or []
        facts_str = " | ".join(
            [f if isinstance(f, str) else f.get("text", "") for f in raw_facts]
        )

        row = {
            "id": item.get("id", ""),
            "published_at": item.get("published_at") or "",
            "company": item.get("company") or "",
            "product": item.get("product") or "",
            "technology": item.get("technology") or "",
            "event_type": item.get("event_type") or "",
            "region": item.get("region") or "",
            "label": item.get("label") or "",
            "passed": str(passed),
            "title": item.get("title") or "",
            "key_facts": facts_str,
            "source_name": item.get("source_name") or "",
            "source_id": item.get("source_id") or "",
            "source_url": item.get("source_url") or "",
            "via_fallback": str(item.get("via_fallback", False)),
            "fallback_for": item.get("fallback_for") or "",
            "reasons": ", ".join(reasons),
        }
        writer.writerow(row)

    return output.getvalue()


def get_other_story_items(item: dict, all_items: list[dict]) -> list[dict]:
    """Retrieve all peer items belonging to the same story as the given item."""
    story_id = item.get("story_id")
    if not story_id:
        return []

    item_id = item.get("id")
    return [
        other
        for other in all_items
        if other.get("story_id") == story_id and other.get("id") != item_id
    ]
