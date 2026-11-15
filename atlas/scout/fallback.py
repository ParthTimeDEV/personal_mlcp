"""Switching: when a source is refused, follow the same companies through other allowed sources.

This is a visible, labelled feature, not a hidden fallback. The refused site is never contacted again,
and never reached through a mirror, a web archive, a cache, a translation or a proxy: every URL is checked
by a guard and a refusal is recorded as `fallback_forbidden_route`. Everything else goes through the same
Compliance Gate (robots.txt, 3 s delay, 429/503 stop) as a normal run.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, Optional
from urllib.parse import urlsplit

from atlas.clean import normalise_url
from atlas.compliance import ComplianceGate, same_site
from atlas.models import CollectResult, Item, Refusal, ScoutSettings, Source, WatchEntry

log = logging.getLogger(__name__)

FORBIDDEN_ROUTE = "fallback_forbidden_route"
FORBIDDEN_MARKERS = (
    "web.archive.org", "archive.org", "archive.ph", "archive.today", "archive.is", "webcache",
    "cachedview", "cc.bingj.com", "translate.goog", "translate.google", "googleusercontent",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.casefold())).strip()


def _terms(entry: WatchEntry) -> list[str]:
    return [t for t in [entry.name, *entry.aliases] if t and t.strip()]


def _found(term: str, text: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.IGNORECASE))


def _company_of(source: Source) -> str:
    from atlas.extract import company_from_source_name  # local import: extract loads heavy NLP libraries
    return company_from_source_name(source.name) or source.name


# ---------- planning ----------

def plan_switching(refused: list[Source], watchlist: list[WatchEntry]
                   ) -> tuple[list[WatchEntry], dict[str, str], list[str]]:
    """(entries to follow, refused_by {entry name: source_id}, notes). A refused source with no matching
    watch entry produces no entry and a note saying so: nothing to switch to."""
    entries: list[WatchEntry] = []
    refused_by: dict[str, str] = {}
    notes: list[str] = []
    for source in refused:
        haystack = f"{source.name} {_company_of(source)}"
        matched = [
            e for e in watchlist
            if e.follow_when_blocked and any(_found(term, haystack) for term in _terms(e))
        ]
        if not matched:
            notes.append(f"{source.source_id}: no watch entry, nothing to switch to")
            continue
        for entry in matched:
            if entry.name not in refused_by:
                entries.append(entry)
                refused_by[entry.name] = source.source_id
    return entries, refused_by, notes


def plan_fallback(refused: list[Source], watchlist: list[WatchEntry]) -> list[WatchEntry]:
    entries, _refused_by, notes = plan_switching(refused, watchlist)
    for note in notes:
        log.info(note)
    return entries


# ---------- the guard ----------

def forbidden_reason(url: str, refused_hosts: list[str]) -> Optional[str]:
    """Why this URL may never be fetched during switching, or None. Covers the refused sites themselves
    (host or subdomain) and archive / cache / translation / proxy routes to them."""
    lowered = url.lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in lowered:
            return f"{FORBIDDEN_ROUTE}: {marker}"
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    for refused in refused_hosts:
        if host == refused or host.endswith("." + refused):
            return f"{FORBIDDEN_ROUTE}: {refused}"
    return None


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


class _GuardedGate:
    """Wraps the real gate: same rules, plus the forbidden-route guard and a skip list of URLs this run
    already has (those are not fetched again, and not recorded as refusals)."""

    def __init__(self, gate: ComplianceGate, refused_hosts: list[str], skip_urls: set[str]) -> None:
        self._gate = gate
        self._hosts = refused_hosts
        self._skip = skip_urls

    def __getattr__(self, name: str):
        return getattr(self._gate, name)

    def can_fetch(self, source: Source, url: str) -> tuple[bool, str]:
        if normalise_url(url) in self._skip:
            return False, "already_collected"
        reason = forbidden_reason(url, self._hosts)
        if reason:
            self._gate.refusals.append(Refusal(source_id=source.source_id, url=url, reason=reason))
            return False, reason
        return self._gate.can_fetch(source, url)


# ---------- matching and labelling ----------

def find_matches(item: Item, entries: list[WatchEntry]) -> list[str]:
    """Names of watch entries mentioned in the item's title, key facts or company (whole word, any case).
    The company field is the extractor's own finding from the page text, which is gone by now."""
    text = " ".join([item.title or "", item.company or "", *item.key_facts])
    return [e.name for e in entries if any(_found(t, text) for t in _terms(e))]


def apply_fallback_labels(items: list[Item], entries: list[WatchEntry],
                          refused_by: dict[str, str]) -> list[Item]:
    """Copies of the items, labelled `via_fallback` when they mention a followed entry. An item from a
    refused source itself is never labelled (that source was not read)."""
    refused_ids = set(refused_by.values())
    out: list[Item] = []
    for item in items:
        matches = find_matches(item, entries) if item.source_id not in refused_ids else []
        if matches:
            item = item.model_copy(update={
                "via_fallback": True, "fallback_for": refused_by[matches[0]], "watch_matches": matches,
            })
        out.append(item)
    return out


# ---------- collection ----------

def collect_fallback_items(
    entries: list[WatchEntry], refused_by: dict[str, str], allowed: list[Source], gate: ComplianceGate,
    settings: ScoutSettings, already: list[Item], refused: list[Source] | None = None,
    collect: Callable | None = None, extract: Callable | None = None,
) -> tuple[CollectResult, list[Item]]:
    """Second pass of switching. For each allowed source, collect up to
    `settings.fallback_max_items_per_source` NEW pages, extract them, and keep only those whose title or
    key facts mention a followed entry. Returns the kept pages (with refusals) and their items.

    Items already collected this run (`already`) are not fetched again; labelling them is
    apply_fallback_labels' job (the first pass). `collect` and `extract` default to the real stages.
    """
    result = CollectResult(source_id="fallback")
    if not settings.fallback_enabled or not entries:
        return result, []
    if collect is None:
        from atlas.collect import collect_source as collect
    if extract is None:
        from atlas.extract import extract_item as extract

    by_id = getattr(gate, "sources", {})
    refused_sources = list(refused or [])
    known = {s.source_id for s in refused_sources}
    for source_id in set(refused_by.values()) - known:
        if source_id not in by_id:
            raise ValueError(f"cannot resolve refused source '{source_id}' to its host; pass `refused`")
        refused_sources.append(by_id[source_id])
    refused_hosts = sorted({_host(u) for s in refused_sources for u in (s.url, s.feed_url) if u})
    refused_ids = {s.source_id for s in refused_sources}

    skip = {normalise_url(i.source_url) for i in already}
    cap = settings.fallback_max_items_per_source
    guarded = _GuardedGate(gate, refused_hosts, skip)
    items: list[Item] = []

    for source in allowed:
        if source.source_id in refused_ids or source.type not in settings.source_types:
            continue
        bad = next((r for u in (source.url, source.feed_url) if u
                    for r in [forbidden_reason(u, refused_hosts)] if r), None)
        if bad or any(same_site(source.url, s.url) for s in refused_sources):
            result.refusals.append(Refusal(
                source_id=source.source_id, url=source.url, reason=bad or f"{FORBIDDEN_ROUTE}: same site"))
            continue
        already_here = sum(1 for i in already if i.source_id == source.source_id)
        got = collect(source, guarded, max_items=already_here + cap)
        result.refusals.extend(got.refusals)
        result.listing_count += got.listing_count
        kept = 0
        for page in got.pages:
            if kept >= cap:
                break
            if normalise_url(page.final_url) in skip:  # never count a page this run already has
                continue
            try:
                item = extract(page, source)
            except Exception as exc:  # recorded, never hidden
                result.refusals.append(Refusal(
                    source_id=source.source_id, url=page.final_url,
                    reason=f"fallback_extract_error:{type(exc).__name__}"))
                continue
            if find_matches(item, entries):
                result.pages.append(page)
                items.append(item)
                kept += 1
    return result, items


def collect_fallback(entries: list[WatchEntry], refused_by: dict[str, str], allowed: list[Source],
                     gate: ComplianceGate, settings: ScoutSettings, already: list[Item]) -> CollectResult:
    """Contract signature (parent2.md section 10). run.py uses collect_fallback_items to also get the items."""
    return collect_fallback_items(entries, refused_by, allowed, gate, settings, already)[0]
