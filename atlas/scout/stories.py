"""Story clustering: items from different sources about the same company / product / event.

Rule-based (no model). Two items join one story when they have the same canonical company AND
(the same product, OR the same event type with similar titles) AND were published within `window_days`
of each other. Items without a date can join only on the same product. Groups are transitive (union-find).
A company or product that no item has is never invented, and different companies are never merged.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date
from typing import Optional

from rapidfuzz import fuzz, utils

from atlas.models import Item, StoryCluster

TITLE_SIMILARITY = 80


def _norm(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.casefold())).strip()
    return text or None


def _date(value: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _related(a: Item, b: Item, window_days: int) -> bool:
    company_a, company_b = _norm(a.company), _norm(b.company)
    if company_a is None or company_a != company_b:
        return False
    same_product = _norm(a.product) is not None and _norm(a.product) == _norm(b.product)
    da, db = _date(a.published_at), _date(b.published_at)
    if da is not None and db is not None and abs((da - db).days) > window_days:
        return False
    if same_product:
        return True
    if da is None or db is None:
        return False  # no date: joins only on the same product
    if a.event_type is None or a.event_type != b.event_type or not a.title or not b.title:
        return False
    return fuzz.token_set_ratio(a.title, b.title, processor=utils.default_process) >= TITLE_SIMILARITY


def make_story_id(item_ids: list[str], company: Optional[str]) -> str:
    """First 12 hex of sha256(earliest item id + company). Stable for the same members."""
    return hashlib.sha256(f"{sorted(item_ids)[0]}|{_norm(company) or ''}".encode("utf-8")).hexdigest()[:12]


def _single(values: list[Optional[str]]) -> Optional[str]:
    """The one value all items agree on; None if there is none or they differ (nothing is invented)."""
    distinct = {v for v in values if v}
    return distinct.pop() if len(distinct) == 1 else None


def build_stories(items: list[Item], window_days: int = 10) -> tuple[list[Item], list[StoryCluster]]:
    """Return (items with story_id set, clusters). Every item gets a story_id; a story with one item is
    still produced. Multi-source stories (2 or more distinct source_ids) are listed first."""
    n = len(items)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if _related(items[i], items[j], window_days):
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters: list[StoryCluster] = []
    story_of: dict[int, str] = {}
    for members in groups.values():
        group = [items[i] for i in members]
        ordered = sorted(group, key=lambda it: (it.published_at or "9999-99-99", it.id))
        company = Counter(it.company for it in group if it.company).most_common(1)
        company_name = company[0][0] if company else None
        story_id = make_story_id([it.id for it in group], company_name)
        for i in members:
            story_of[i] = story_id
        dated = sorted(it.published_at for it in group if _date(it.published_at))
        headline_item = next((it for it in ordered if it.title), None)
        clusters.append(StoryCluster(
            story_id=story_id,
            headline=headline_item.title if headline_item else "(no title)",
            company=company_name,
            product=_single([it.product for it in group]),
            event_type=_single([it.event_type for it in group]),
            item_ids=[it.id for it in ordered],
            source_ids=list(dict.fromkeys(it.source_id for it in ordered)),
            first_published=dated[0] if dated else None,
            last_published=dated[-1] if dated else None,
            via_fallback_count=sum(1 for it in group if it.via_fallback),
        ))

    clusters.sort(key=lambda c: (-len(c.source_ids), _neg(c.last_published), c.story_id))
    return [it.model_copy(update={"story_id": story_of[i]}) for i, it in enumerate(items)], clusters


def _neg(iso: Optional[str]) -> tuple:
    """Sort key: newest first, undated last."""
    return (1, "") if iso is None else (0, "".join(chr(255 - ord(ch)) for ch in iso))
