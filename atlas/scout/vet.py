"""Automatic vetting of one candidate source, and its transparent trust score.

Owner: Ragini. Reproduces the hand procedure of docs/source_vetting.md: robots.txt, terms, feed or list,
public check, a small sample. Every request goes through the Compliance Gate, at most MAX_REQUESTS page
requests per candidate (robots.txt, fetched by the gate once per host, is extra). A 429/503 stops the candidate.

Vetting never approves a source. `usable` only means "every automatic rule passed"; terms must be
positively `ok` (unknown means a human has to look). The trust score is a pure, rule-based function.
Nothing is written to disk.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlsplit

import feedparser
import yaml
from dateutil import parser as date_parser

from atlas.compliance import ComplianceGate, same_site
from atlas.models import Candidate, ScoutSettings
from atlas.scout.discover import (
    BudgetExhausted, GatedFetcher, Page, RateLimited, find_feed_links, parse_html, probe_source,
    registered_domain,
)

log = logging.getLogger("atlas.scout.vet")

ROOT = Path(__file__).resolve().parent.parent.parent
MAX_REQUESTS = 8
MAX_TERMS_PAGES = 2
SAMPLE_SIZE = 10
ARTICLES_TO_FETCH = 3
VET_MARK = " | vet: "

# Words the hand vetting looked for in a terms page.
_AUTOMATION_RE = re.compile(
    r"\b(scrap(?:e|es|ed|ing|er|ers)|crawl(?:s|ed|er|ers|ing)?|spiders?|robots?|bots?|data[- ]mining|"
    r"harvest(?:s|ed|ing)?|automated means|machine[- ]learning)\b", re.I)
_TERMS_STRONG_RE = re.compile(r"\bterms\b|conditions[- ]of[- ]use|website[- ]terms", re.I)
_TERMS_WEAK_RE = re.compile(r"\blegal\b|disclaimer|imprint", re.I)
_LISTING_RANKS = [
    (1, re.compile(r"\b(newsroom|news|press[- ]releases?)\b", re.I)),
    (2, re.compile(r"\b(press|media)\b", re.I)),
    (3, re.compile(r"\b(blog|stories|insights|articles|updates)\b", re.I)),
]
_PAYWALL_RE = re.compile(
    r"subscribe to (continue|read|unlock)|(sign|log) ?in to (read|view|continue)|members[- ]only|"
    r"create an account to (read|continue)|paywall", re.I)
_LOGIN_PATH_RE = re.compile(r"/(log-?in|sign-?in|signin|auth)(/|$|\?)", re.I)
_NOT_AN_ITEM = {"page", "feed", "rss", "category", "tag", "tags", "archive", "search"}


def _today() -> date:
    return date.today()


# ---------- trust score (pure) ----------

def trust_score(candidate: Candidate, today: Optional[date] = None) -> tuple[int, list[str]]:
    """(score 0-100, one reason line per row, including rows that earned 0). No model, no clock beyond `today`."""
    today = today or _today()
    c = candidate
    rows = ("terms", "robots", "feed", "freshness", "relevance", "source type", "https")
    if c.terms_status == "forbids_automation":
        return 0, ["terms: +0 forbid automation, automatic fail, score forced to 0"] + [
            f"{name}: +0 not scored (automatic fail)" for name in rows[1:]]

    scored: list[tuple[str, int, str]] = []
    scored.append(("terms", 25, "read and ok") if c.terms_status == "ok"
                  else ("terms", 0, "unknown, needs a human to read them"))
    scored.append(("robots", 15, "allowed") if c.robots_status == "allowed"
                  else ("robots", 0, f"not confirmed allowed ({c.robots_status})"))
    if c.feed_url and c.access_method == "rss":
        scored.append(("feed", 15, "a feed exists"))
    elif c.access_method == "html" and c.item_url_pattern:
        scored.append(("feed", 10, "only an HTML listing"))
    else:
        scored.append(("feed", 0, "no feed or listing found"))

    if c.newest_item_date:
        age = max(0, (today - date.fromisoformat(c.newest_item_date)).days)
        pts = 15 if age <= 30 else 10 if age <= 90 else 5 if age <= 365 else 0
        scored.append(("freshness", pts, f"newest dated item is {age} days old"))
    else:
        scored.append(("freshness", 0, "no dated item seen"))

    rel = c.relevance_sample
    if rel is None:
        scored.append(("relevance", 0, "no sample taken"))
    else:
        pts = 15 if rel >= 0.5 else 10 if rel >= 0.25 else 5 if rel > 0 else 0
        scored.append(("relevance", pts, f"{rel:.0%} of sampled titles match a compressor keyword"))

    if c.type_guess == "government" or "[association]" in c.notes:
        scored.append(("source type", 10, "government or association site"))
    elif "[seed:verified]" in c.notes:
        scored.append(("source type", 10, "official site named in a verified seed"))
    elif c.discovered_via == "seed":
        scored.append(("source type", 5, "named in an unverified seed"))
    else:
        scored.append(("source type", 0, "found by chance, no seed"))

    same_domain = (not c.feed_url) or registered_domain(c.feed_url) == c.domain
    if c.url.startswith("https://") and (c.feed_url or c.item_url_pattern) and same_domain:
        scored.append(("https", 5, "HTTPS, feed and site share one registered domain"))
    else:
        scored.append(("https", 0, "not HTTPS, no feed or listing, or the feed is on another domain"))

    total = min(100, sum(points for _, points, _ in scored))
    return total, [f"{name}: +{points} {why}" for name, points, why in scored]


# ---------- terms ----------

def page_text(body: bytes) -> str:
    """The text of the WHOLE page (footers and side blocks included, not only the main article block):
    a clause on automation often sits outside the main content."""
    doc = parse_html(body)
    if doc is None:
        return ""
    for bad in doc.xpath("//script|//style|//noscript"):
        bad.drop_tree()
    return "\n".join(t.strip() for t in doc.itertext() if t.strip())


def find_automation_quote(text: str) -> Optional[str]:
    """The first sentence that mentions scraping, bots, mining ... cut to at most 200 characters around the hit."""
    for sentence in re.split(r"\n+|(?<=[.!?])\s+", text):
        match = _AUTOMATION_RE.search(sentence)
        if not match:
            continue
        sentence = " ".join(sentence.split())
        if len(sentence) <= 200:
            return sentence
        start = max(0, _AUTOMATION_RE.search(sentence).start() - 100)
        return sentence[start:start + 200]
    return None


def find_terms_links(doc, base_url: str, domain: str) -> list[str]:
    """Terms-like links on the candidate's own domain, best first (terms before legal notices)."""
    ranked: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for order, anchor in enumerate(doc.iter("a")):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urldefrag(urljoin(base_url, href))[0]
        if urlsplit(absolute).scheme not in ("http", "https") or absolute in seen:
            continue
        if registered_domain(absolute) != domain:
            continue
        hay = " ".join(anchor.text_content().split()).lower() + " " + href.lower()
        if _TERMS_STRONG_RE.search(hay):
            rank = 1
        elif _TERMS_WEAK_RE.search(hay):
            rank = 2
        else:
            continue
        seen.add(absolute)
        ranked.append((rank, order, absolute))
    return [url for _, _, url in sorted(ranked)]


# ---------- listing, dates, relevance ----------

def find_listing_link(doc, base_url: str, domain: str) -> Optional[str]:
    """The most news-like link on the homepage (news, press releases before media before blog)."""
    best: Optional[tuple[int, int, str]] = None
    for order, anchor in enumerate(doc.iter("a")):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = urldefrag(urljoin(base_url, href))[0]
        if urlsplit(absolute).scheme not in ("http", "https") or registered_domain(absolute) != domain:
            continue
        hay = " ".join(anchor.text_content().split()).lower() + " " + urlsplit(absolute).path.lower()
        for rank, pattern in _LISTING_RANKS:
            if pattern.search(hay):
                if best is None or (rank, order) < best[:2]:
                    best = (rank, order, absolute)
                break
    return best[2] if best else None


def _listing_links(doc, listing_url: str) -> list[tuple[str, str]]:
    """(link, anchor text) for every same-site link one level below the listing's path."""
    base = urlsplit(listing_url)
    prefix = base.path.rstrip("/")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    if not prefix:
        return out
    for anchor in doc.iter("a"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        link = urldefrag(urljoin(listing_url, href))[0]
        parts = urlsplit(link)
        if link in seen or not same_site(link, listing_url) or not parts.path.startswith(prefix + "/"):
            continue
        rest = parts.path[len(prefix) + 1:].strip("/")
        if not rest or "/" in rest or rest.lower() in _NOT_AN_ITEM or not re.fullmatch(r"[A-Za-z0-9_%.\-]{4,}", rest):
            continue
        seen.add(link)
        out.append((link, " ".join(anchor.text_content().split())))
    return out


def derive_item_pattern(links: list[tuple[str, str]], listing_url: str) -> Optional[str]:
    """A regex for article links on an HTML listing, if at least two article-like links exist."""
    if len(links) < 2:
        return None
    base = urlsplit(listing_url)
    return "^" + re.escape(f"{base.scheme}://{base.netloc}{base.path.rstrip('/')}") + r"/[A-Za-z0-9_%.\-]+/?$"


def article_date(doc) -> Optional[date]:
    """Publication date of an article page from its metadata (never guessed from the text)."""
    raw: list[str] = []
    for xp in ("//meta[@property='article:published_time']/@content", "//meta[@name='date']/@content",
               "//meta[@itemprop='datePublished']/@content", "//*[@itemprop='datePublished']/@datetime",
               "//time/@datetime"):
        raw.extend(doc.xpath(xp))
    for script in doc.xpath("//script[@type='application/ld+json']/text()"):
        raw.extend(re.findall(r'"datePublished"\s*:\s*"([^"]+)"', script))
    for value in raw:
        try:
            return date_parser.parse(value.strip()).date()
        except (ValueError, OverflowError):
            continue
    return None


@lru_cache(maxsize=4)
def _keyword_regex(extra: tuple[str, ...], path: str = "config/keywords.yaml") -> re.Pattern:
    with open(ROOT / path, encoding="utf-8") as fh:
        words = list((yaml.safe_load(fh) or {}).get("compressor", []))
    words += list(extra)
    return re.compile("|".join(rf"(?<!\w){re.escape(w)}(?!\w)" for w in words if w), re.I)


def relevance_share(texts: list[str], settings: ScoutSettings) -> Optional[float]:
    """Share of the sampled texts (at most 10) that contain a compressor-family keyword."""
    sample = texts[:SAMPLE_SIZE]
    if not sample:
        return None
    pattern = _keyword_regex(tuple(settings.extra_compressor_keywords))
    return round(sum(1 for t in sample if pattern.search(t)) / len(sample), 2)


# ---------- the vetting run ----------

@dataclass
class _State:
    notes: list[str] = field(default_factory=list)
    listing_ok: bool = False  # a feed with entries, or an HTML listing with article links
    interrupted: bool = False  # rate limited or out of budget


def _plausible(d: date, today: date) -> bool:
    return d <= today + timedelta(days=2)  # an obviously future date is a parsing error, not news


def _read_terms(c: Candidate, doc, home: Page, f: GatedFetcher, st: _State) -> None:
    links = find_terms_links(doc, home.url, c.domain)[:MAX_TERMS_PAGES]
    read_any = False
    for url in links:
        page = f.get(url)
        if page is None or page.status != 200:
            st.notes.append(f"terms page {url} not read ({f.refusal if page is None else 'HTTP ' + str(page.status)})")
            continue
        text = page_text(page.body)
        if not text.strip():
            st.notes.append(f"terms page {url} had no readable text")
            continue
        if not read_any:
            c.terms_url = url
        read_any = True
        quote = find_automation_quote(text)
        if quote:
            c.terms_status = "forbids_automation"
            c.terms_url = url
            c.terms_evidence = quote
            return
    if read_any:
        c.terms_status = "ok"
    else:
        c.terms_status = "unknown"
        st.notes.append("no terms page found or readable" if not links else "terms page(s) could not be read")


def _sample_feed(c: Candidate, listing: Page, f: GatedFetcher, settings: ScoutSettings, today: date,
                 st: _State) -> None:
    feed = feedparser.parse(listing.body)
    entries = list(feed.entries)
    if not entries:
        st.notes.append("feed has no entries")
        return
    st.listing_ok = True
    texts, dates = [], []
    for entry in entries[:SAMPLE_SIZE]:
        texts.append(f"{entry.get('title', '')} {entry.get('summary', '')}")
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            d = date(parsed[0], parsed[1], parsed[2])
            if _plausible(d, today):
                dates.append(d)
    if not dates:  # an undated feed: read dates from the article pages, at most 3
        for entry in entries[:ARTICLES_TO_FETCH]:
            link = (entry.get("link") or "").strip()
            if link and same_site(link, c.url):
                d = _date_of_page(f.get(link), today)
                if d:
                    dates.append(d)
    c.relevance_sample = relevance_share(texts, settings)
    c.newest_item_date = str(max(dates)) if dates else None


def _date_of_page(page: Optional[Page], today: date) -> Optional[date]:
    if page is None or page.status != 200:
        return None
    doc = parse_html(page.body)
    d = article_date(doc) if doc is not None else None
    return d if d and _plausible(d, today) else None


def _sample_html(c: Candidate, doc, listing: Page, f: GatedFetcher, settings: ScoutSettings, today: date,
                 st: _State) -> None:
    links = _listing_links(doc, listing.url)
    pattern = derive_item_pattern(links, listing.url)
    if pattern is None:
        st.notes.append("listing found but no article-like links to derive a pattern from")
        return
    c.item_url_pattern = pattern
    st.listing_ok = True
    dates = []
    for link, _title in links[:ARTICLES_TO_FETCH]:
        d = _date_of_page(f.get(link), today)
        if d:
            dates.append(d)
    c.relevance_sample = relevance_share([t or link for link, t in links], settings)
    c.newest_item_date = str(max(dates)) if dates else None


def _vet(c: Candidate, f: GatedFetcher, settings: ScoutSettings, today: date, st: _State) -> None:
    # 1. homepage (also finds the terms, feed and news links)
    home = f.get(c.url)
    if home is None:
        if f.refusal == "robots_disallow":
            c.robots_status = "disallowed"
            st.notes.append("robots.txt disallows the homepage")
        else:
            st.notes.append(f"homepage not fetched ({f.refusal})")
        return
    c.robots_status = "allowed"  # the homepage passed; the listing URL is checked below
    if home.status != 200:
        st.notes.append(f"homepage answered HTTP {home.status}")
        if home.status in (401, 403):
            c.public_ok = False
        return
    doc = parse_html(home.body)
    if doc is None:
        st.notes.append("homepage could not be parsed")
        return

    # choose the listing: a feed (given, or advertised), else a news or press page
    feed_url = c.feed_url
    if not feed_url:
        advertised = find_feed_links(doc, home.url)
        feed_url = advertised[0] if advertised else None
    method, listing_url = ("rss", feed_url) if feed_url else ("html", find_listing_link(doc, home.url, c.domain))

    # robots.txt for the listing or feed URL decides robots_status
    if listing_url:
        allowed, reason = f.allowed(listing_url)
        if not allowed:
            if reason == "robots_disallow":
                c.robots_status = "disallowed"
                st.notes.append("robots.txt disallows the feed or listing URL")
            else:
                c.robots_status = "unknown"
                st.notes.append(f"robots.txt for the listing could not be read ({reason})")
            return

    # 2. terms (a forbidding clause ends the vetting here)
    _read_terms(c, doc, home, f, st)
    if c.terms_status == "forbids_automation":
        return

    # 3. feed or list
    if not listing_url:
        st.notes.append("no feed and no news or press listing found")
        return
    listing = f.get(listing_url)
    if listing is None:
        st.notes.append(f"feed or listing not fetched ({f.refusal})")
        return
    c.access_method = method
    c.feed_url = feed_url if method == "rss" else c.feed_url
    # 4. public check
    if listing.status in (401, 403):
        c.public_ok = False
        st.notes.append(f"listing answered HTTP {listing.status} (login or refusal)")
        return
    if listing.status != 200:
        st.notes.append(f"listing answered HTTP {listing.status}")
        return
    login_redirect = bool(_LOGIN_PATH_RE.search(urlsplit(listing.url).path))
    list_doc = parse_html(listing.body) if method == "html" else None
    paywalled = method == "html" and bool(_PAYWALL_RE.search(listing.text[:300_000]))
    c.public_ok = not (login_redirect or paywalled)
    if not c.public_ok:
        st.notes.append("listing redirects to a login or shows a paywall marker")
        return
    # 5. sample
    if method == "rss":
        _sample_feed(c, listing, f, settings, today, st)
    elif list_doc is not None:
        _sample_html(c, list_doc, listing, f, settings, today, st)
    else:
        st.notes.append("listing could not be parsed")


def _status_and_usable(c: Candidate, st: _State) -> None:
    if c.robots_status == "disallowed" or c.terms_status == "forbids_automation":
        c.status = "rejected_by_rules"
    elif st.interrupted or c.terms_status == "unknown" or not st.listing_ok or c.public_ok is not True:
        c.status = "needs_review"
    else:
        c.status = "auto_vetted"
    c.usable = (c.status == "auto_vetted" and c.terms_status == "ok" and c.robots_status == "allowed"
                and c.public_ok is True and c.newest_item_date is not None)


def vet_candidate(candidate: Candidate, gate: ComplianceGate, settings: ScoutSettings) -> Candidate:
    """Vet one candidate and return an updated copy (the argument is not modified)."""
    c = candidate.model_copy(deep=True)
    today = _today()
    st = _State()
    if c.status == "rejected_by_rules" and c.robots_status == "disallowed":
        # discovery already found the homepage disallowed: never fetched further
        pass
    else:
        fetcher = GatedFetcher(gate, probe_source(c.url, c.domain, c.type_guess), budget=MAX_REQUESTS)
        try:
            _vet(c, fetcher, settings, today, st)
        except RateLimited:
            st.interrupted = True
            st.notes.append("rate limited (HTTP 429/503): stopped for this site")
        except BudgetExhausted:
            st.interrupted = True
            st.notes.append(f"request budget of {MAX_REQUESTS} used up")
        except Exception as exc:  # recorded on the candidate; the caller's loop goes on
            st.interrupted = True
            st.notes.append(f"vetting error: {type(exc).__name__}: {exc}")
            log.warning("vetting %s failed: %s", c.domain, exc)
    _status_and_usable(c, st)
    c.trust_score, c.trust_reasons = trust_score(c, today)
    base = c.notes.split(VET_MARK)[0]
    c.notes = base + (VET_MARK + "; ".join(st.notes) if st.notes else "")
    return c
