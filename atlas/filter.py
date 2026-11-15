"""Relevance filter: four transparent yes/no checks per item (parent.md section 10)."""
import re
from datetime import date
from pathlib import Path

import yaml
from dateutil.relativedelta import relativedelta

from atlas.models import FilterResult, Item, ScoutSettings, Source

ROOT = Path(__file__).resolve().parent.parent
NORTH_AMERICA = {"US", "CA", "MX", "NA"}
CREDIBLE_STATUSES = {"proposed", "approved"}


def _load_keywords(path: str) -> dict[str, list[str]]:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with open(p, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {key: list(data.get(key) or []) for key in ("compressor", "industrial", "us_locations")}


def _has_term(text: str, terms: list[str]) -> bool:
    """Case-insensitive whole-word / whole-phrase match."""
    return any(
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE) for term in terms
    )


def _parse_published(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _clean_terms(terms: list[str]) -> list[str]:
    return [t.strip() for t in terms if t and t.strip()]


def _facts_text(item: Item) -> str:
    """Title plus key facts: the only text left once the page text is dropped."""
    return " ".join([item.title or "", *item.key_facts])


def _region_selected(item: Item, source: Source | None, regions: list[str]) -> bool:
    """The item's own region if known; otherwise the phase 1 evidence (source region, a US location in
    the text), restricted to the chosen regions."""
    if item.region is not None:
        return item.region in regions
    if source is not None:
        source_region = source.region.upper()
        if source_region in regions:
            return True
        if source_region == "NA":  # a source that covers all of North America
            return bool(regions)
    return item.mentions_us_location and "US" in regions


def _settings_reasons(item: Item, source: Source | None, settings: ScoutSettings) -> list[str]:
    """Extra checks from ScoutSettings, in a fixed order. Each returns a reason code when it fails."""
    reasons: list[str] = []
    if not _region_selected(item, source, list(settings.regions)):
        reasons.append("region_not_selected")
    if settings.technologies and (item.technology or "").casefold() not in {
            t.casefold() for t in settings.technologies}:
        reasons.append("technology_not_selected")
    if settings.event_types and item.event_type not in settings.event_types:
        reasons.append("event_type_not_selected")
    if _has_term(_facts_text(item), _clean_terms(settings.excluded_keywords)):
        reasons.append("excluded_keyword")
    if settings.require_industrial and not item.industrial_hint:
        reasons.append("not_industrial")
    if item.source_type not in settings.source_types:
        reasons.append("source_type_not_selected")
    return reasons


def _judge(item: Item, source: Source | None, today: date, recent_months: int,
           compressor_terms: list[str], settings: ScoutSettings | None = None) -> FilterResult:
    reasons: list[str] = []

    compressor_related = bool(item.matched_keywords) or _has_term(item.title or "", compressor_terms)
    if not compressor_related and settings is not None:
        compressor_related = _has_term(_facts_text(item), _clean_terms(settings.extra_compressor_keywords))
    if not compressor_related:
        reasons.append("no_compressor_keyword")

    if source is not None and source.region.upper() in NORTH_AMERICA:
        north_america = True
    else:
        north_america = item.mentions_us_location
    if not north_america:
        reasons.append("not_north_america")

    credible_source = (
        source is not None
        and bool(source.type)
        and source.vetting_status == "working"
        and source.status in CREDIBLE_STATUSES
    )
    if not credible_source:
        reasons.append("source_not_credible")

    published = _parse_published(item.published_at)
    date_missing = published is None
    recent = False
    if published is None:
        reasons.append("date_missing")
    elif published > today:
        date_missing = True
        reasons.extend(["date_missing", "date_in_future"])
    elif published >= today - relativedelta(months=recent_months):
        recent = True
    else:
        reasons.append("too_old")

    extra_reasons = _settings_reasons(item, source, settings) if settings is not None else []
    reasons.extend(extra_reasons)

    return FilterResult(
        compressor_related=compressor_related,
        north_america=north_america,
        credible_source=credible_source,
        recent=recent,
        passed=compressor_related and north_america and credible_source and recent and not extra_reasons,
        reasons=reasons,
        date_missing=date_missing,
    )


def apply_filter(items: list[Item], sources_by_id: dict[str, Source],
                 today: date | None = None, recent_months: int = 12,
                 keywords_path: str = "config/keywords.yaml",
                 settings: ScoutSettings | None = None) -> list[Item]:
    """Return the items with `.filter` set. Nothing is dropped here; run.py decides what goes where.

    settings=None is the phase 1 behaviour exactly. With settings, settings.recent_months replaces
    `recent_months` and the extra rules (region, technology, event type, extra and excluded keywords,
    require_industrial, source types) add reason codes after the four phase 1 checks.
    """
    today = today or date.today()
    if settings is not None:
        recent_months = settings.recent_months
    compressor_terms = _load_keywords(keywords_path)["compressor"]
    return [
        item.model_copy(update={
            "filter": _judge(item, sources_by_id.get(item.source_id), today, recent_months,
                          compressor_terms, settings)
        })
        for item in items
    ]
