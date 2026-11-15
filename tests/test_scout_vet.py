"""Offline tests for atlas/scout/vet.py (httpx.MockTransport, synthetic sites only)."""
import re
from datetime import date
from pathlib import Path

import httpx
import pytest

from atlas.compliance import ComplianceGate
from atlas.models import Candidate, ScoutSettings
from atlas.scout import vet as vet_module
from atlas.scout.vet import (
    MAX_REQUESTS, find_automation_quote, trust_score, vet_candidate,
)

TODAY = date(2026, 11, 10)
SETTINGS = ScoutSettings()


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(vet_module, "_today", lambda: TODAY)


def page(body: str, status: int = 200, ctype: str = "text/html; charset=utf-8", headers=None):
    return (status, {"content-type": ctype, **(headers or {})}, body)


def make_gate(routes: dict, robots: dict | None = None):
    requested: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        requested.append((host, path))
        if path == "/robots.txt":
            return httpx.Response(200, text=(robots or {}).get(host, "User-agent: *\nAllow: /\n"))
        spec = routes.get(f"{host}{path}")
        if spec is None:
            return httpx.Response(404, text="not found")
        if callable(spec):
            return spec(request)
        status, headers, body = spec
        return httpx.Response(status, headers=headers, text=body)

    gate = ComplianceGate([], client=httpx.Client(transport=httpx.MockTransport(handler)), min_delay=0.0,
                          contact_email="test@example.org")
    gate._sleep = lambda s: None
    return gate, requested


def candidate(**kw) -> Candidate:
    base = dict(candidate_id="abc123abc123", name="Acme", url="https://acme.example/", domain="acme.example",
                type_guess="competitor", discovered_via="seed", notes="[seed:unverified] test")
    base.update(kw)
    return Candidate(**base)


def page_requests(requested) -> list[tuple[str, str]]:
    return [r for r in requested if r[1] != "/robots.txt"]


HOME = """<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head><body>
<main><h1>Acme</h1></main>
<footer><a href="/privacy">Privacy</a> <a href="/terms">Terms of Use</a> <a href="/news">News</a></footer></body></html>"""

CLEAN_TERMS = "<html><body><main><p>Welcome. Use this site responsibly.</p><p>Content is provided as is.</p></main></body></html>"

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>Acme</title>
<item><title>Acme launches oil-free compressor</title><link>https://acme.example/news/a</link><pubDate>Fri, 06 Nov 2026 09:00:00 GMT</pubDate></item>
<item><title>Acme opens Texas plant</title><link>https://acme.example/news/b</link><pubDate>Mon, 02 Nov 2026 09:00:00 GMT</pubDate></item>
<item><title>Company picnic</title><link>https://acme.example/news/c</link><pubDate>Tue, 20 Oct 2026 09:00:00 GMT</pubDate></item>
<item><title>Rotary screw compressor service tips</title><link>https://acme.example/news/d</link><pubDate>Tue, 13 Oct 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""


def clean_site(**over) -> dict:
    routes = {"acme.example/": page(HOME), "acme.example/terms": page(CLEAN_TERMS),
              "acme.example/feed.xml": page(FEED, ctype="application/rss+xml")}
    routes.update(over)
    return routes


# ---------- the happy path ----------

def test_clean_site_is_auto_vetted_and_usable():
    gate, requested = make_gate(clean_site())
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.status == "auto_vetted" and c.usable is True
    assert c.robots_status == "allowed" and c.terms_status == "ok" and c.public_ok is True
    assert c.terms_url == "https://acme.example/terms" and c.terms_evidence is None
    assert c.access_method == "rss" and c.feed_url == "https://acme.example/feed.xml"
    assert c.newest_item_date == "2026-11-06"
    assert c.relevance_sample == 0.5  # 2 of 4 titles match a compressor keyword
    assert c.trust_score == 25 + 15 + 15 + 15 + 15 + 5 + 5 and len(c.trust_reasons) == 7
    assert len(page_requests(requested)) <= MAX_REQUESTS


def test_input_candidate_is_not_modified_and_default_settings_change_nothing_else():
    original = candidate()
    snapshot = original.model_dump()
    gate, _ = make_gate(clean_site())
    vet_candidate(original, gate, SETTINGS)
    assert original.model_dump() == snapshot
    # with default settings no discovered source reaches a run (Phase 1 behaviour)
    from atlas.scout.settings_store import default_settings, usable_sources
    vetted = vet_candidate(original, make_gate(clean_site())[0], SETTINGS)
    assert usable_sources(default_settings(), [vetted], []) == []


def test_revetting_does_not_pile_up_notes():
    gate, _ = make_gate(clean_site(**{"acme.example/terms": page("<html></html>")}))
    first = vet_candidate(candidate(), gate, SETTINGS)
    second = vet_candidate(first, make_gate(clean_site(**{"acme.example/terms": page("<html></html>")}))[0], SETTINGS)
    assert second.notes.count(" | vet: ") == 1


# ---------- terms ----------

def test_scraping_ban_deep_in_a_long_page_is_found_with_a_short_quote():
    filler = "<p>" + ("We provide compressors and service for industry. " * 40) + "</p>"
    ban = ("<footer><p>Users agree not to use any robot, spider, scraper or other automated means to access "
           "this website or to extract its content for any purpose without our express written permission, "
           "including but not limited to the creation of datasets, indexes or databases, whether for commercial "
           "or non-commercial purposes, and whether or not the extracted material is later republished.</p></footer>")
    terms = f"<html><body><main>{filler * 30}</main>{ban}</body></html>"
    gate, requested = make_gate(clean_site(**{"acme.example/terms": page(terms)}))
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.terms_status == "forbids_automation" and c.status == "rejected_by_rules" and not c.usable
    assert c.terms_evidence and len(c.terms_evidence) <= 200 and re.search(r"scraper|robot|spider", c.terms_evidence)
    assert c.trust_score == 0
    assert ("acme.example", "/feed.xml") not in requested, "the feed must not be fetched after a ban"


def test_quote_is_cut_to_200_characters():
    sentence = "x" * 150 + " you may not use a web crawler " + "y" * 400 + "."
    quote = find_automation_quote(sentence)
    assert quote is not None and len(quote) <= 200 and "crawler" in quote


def test_clean_terms_are_ok_and_unrelated_words_do_not_trigger():
    terms = "<html><body><p>These terms govern your use of the site. Robotics products are described elsewhere.</p></body></html>"
    gate, _ = make_gate(clean_site(**{"acme.example/terms": page(terms)}))
    assert vet_candidate(candidate(), gate, SETTINGS).terms_status == "ok"


def test_no_terms_page_is_unknown_and_not_usable():
    home = HOME.replace('<a href="/terms">Terms of Use</a>', "")
    gate, _ = make_gate(clean_site(**{"acme.example/": page(home)}))
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.terms_status == "unknown" and c.status == "needs_review" and c.usable is False
    assert "no terms page" in c.notes


def test_unreadable_terms_page_is_unknown():
    gate, _ = make_gate(clean_site(**{"acme.example/terms": page("gone", status=404)}))
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.terms_status == "unknown" and c.usable is False


# ---------- robots, rate limits, budget ----------

def test_robots_disallowing_the_feed_rejects_and_stops_before_terms():
    gate, requested = make_gate(clean_site(), robots={"acme.example": "User-agent: *\nDisallow: /feed.xml\n"})
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.robots_status == "disallowed" and c.status == "rejected_by_rules" and not c.usable
    assert ("acme.example", "/terms") not in requested and ("acme.example", "/feed.xml") not in requested


def test_candidate_rejected_by_discovery_is_never_fetched():
    gate, requested = make_gate(clean_site())
    c = vet_candidate(candidate(status="rejected_by_rules", robots_status="disallowed"), gate, SETTINGS)
    assert requested == [] and c.status == "rejected_by_rules" and c.usable is False


def test_http_429_stops_that_candidate():
    gate, requested = make_gate(clean_site(**{"acme.example/feed.xml": page("slow", status=429)}))
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.status == "needs_review" and c.usable is False and "rate limited" in c.notes
    assert page_requests(requested)[-1] == ("acme.example", "/feed.xml"), "nothing is fetched after the 429"


def test_homepage_429_stops_immediately():
    gate, requested = make_gate({"acme.example/": page("slow", status=503)})
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.status == "needs_review" and len(page_requests(requested)) == 1


def test_request_budget_is_respected_with_many_terms_links_and_articles():
    home = ('<html><body><a href="/terms">Terms</a><a href="/legal">Legal</a><a href="/terms-2">Terms of use</a>'
            '<a href="/conditions">Conditions of use</a><a href="/news">Press releases</a></body></html>')
    listing = "<html><body>" + "".join(f'<a href="/news/story-{i}">Story {i}</a>' for i in range(12)) + "</body></html>"
    article = '<html><head><meta property="article:published_time" content="2026-11-01"></head></html>'
    routes = {"acme.example/": page(home), "acme.example/news": page(listing)}
    for i in range(12):
        routes[f"acme.example/news/story-{i}"] = page(article)
    for p in ("terms", "legal", "terms-2", "conditions"):
        routes[f"acme.example/{p}"] = page(CLEAN_TERMS)
    gate, requested = make_gate(routes)
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert len(page_requests(requested)) <= MAX_REQUESTS
    assert c.access_method == "html" and c.newest_item_date == "2026-11-01"


# ---------- feed or listing, public check ----------

def test_html_listing_derives_pattern_and_reads_dates_from_articles():
    home = '<html><body><a href="/terms">Terms of Use</a><a href="/news">Newsroom</a></body></html>'
    listing = ('<html><body><a href="/news/oil-free-compressor-launch">Oil-free compressor launch</a>'
               '<a href="/news/new-texas-plant">New Texas plant</a><a href="/news/page">Next</a>'
               '<a href="/about">About</a></body></html>')
    art_a = '<html><head><meta property="article:published_time" content="2026-11-03T08:00:00Z"></head></html>'
    art_b = '<html><body><script type="application/ld+json">{"datePublished": "2026-10-01"}</script></body></html>'
    gate, _ = make_gate({"acme.example/": page(home), "acme.example/terms": page(CLEAN_TERMS),
                         "acme.example/news": page(listing),
                         "acme.example/news/oil-free-compressor-launch": page(art_a),
                         "acme.example/news/new-texas-plant": page(art_b)})
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.access_method == "html" and c.feed_url is None
    assert re.search(c.item_url_pattern, "https://acme.example/news/oil-free-compressor-launch")
    assert not re.search(c.item_url_pattern, "https://acme.example/news/page/2")
    assert c.newest_item_date == "2026-11-03" and c.relevance_sample == 0.5
    assert c.status == "auto_vetted" and c.usable is True


def test_no_feed_and_no_listing_needs_review():
    gate, _ = make_gate({"acme.example/": page("<html><body><a href='/terms'>Terms</a></body></html>"),
                         "acme.example/terms": page(CLEAN_TERMS)})
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.status == "needs_review" and c.usable is False and c.feed_url is None
    assert c.newest_item_date is None and c.relevance_sample is None


def test_login_redirect_means_not_public():
    gate, _ = make_gate(clean_site(**{
        "acme.example/feed.xml": page("", status=302, headers={"location": "/login"}),
        "acme.example/login": page("<html>please sign in</html>")}))
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.public_ok is False and c.status == "needs_review" and c.usable is False


def test_paywall_marker_on_an_html_listing_means_not_public():
    home = '<html><body><a href="/terms">Terms</a><a href="/news">News</a></body></html>'
    listing = '<html><body><p>Subscribe to continue reading.</p><a href="/news/story-one">One</a><a href="/news/story-two">Two</a></body></html>'
    gate, _ = make_gate({"acme.example/": page(home), "acme.example/terms": page(CLEAN_TERMS),
                         "acme.example/news": page(listing)})
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.public_ok is False and c.usable is False


def test_undated_feed_reads_dates_from_articles():
    feed = ("<?xml version='1.0'?><rss version='2.0'><channel><title>A</title>"
            "<item><title>Compressor news</title><link>https://acme.example/news/a</link></item></channel></rss>")
    art = '<html><head><meta property="article:published_time" content="2026-10-30"></head></html>'
    gate, _ = make_gate(clean_site(**{"acme.example/feed.xml": page(feed, ctype="application/rss+xml"),
                                      "acme.example/news/a": page(art)}))
    assert vet_candidate(candidate(), gate, SETTINGS).newest_item_date == "2026-10-30"


def test_no_dates_anywhere_is_not_usable():
    feed = ("<?xml version='1.0'?><rss version='2.0'><channel><title>A</title>"
            "<item><title>Compressor news</title><link>https://acme.example/news/a</link></item></channel></rss>")
    gate, _ = make_gate(clean_site(**{"acme.example/feed.xml": page(feed, ctype="application/rss+xml"),
                                      "acme.example/news/a": page("<html></html>")}))
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.newest_item_date is None and c.usable is False and c.status == "auto_vetted"


def test_future_dates_are_ignored():
    feed = ("<?xml version='1.0'?><rss version='2.0'><channel><title>A</title>"
            "<item><title>Compressor</title><link>https://acme.example/n/a</link>"
            "<pubDate>Wed, 01 Jan 2031 09:00:00 GMT</pubDate></item></channel></rss>")
    gate, _ = make_gate(clean_site(**{"acme.example/feed.xml": page(feed, ctype="application/rss+xml"),
                                      "acme.example/n/a": page("<html></html>")}))
    assert vet_candidate(candidate(), gate, SETTINGS).newest_item_date is None


def test_unexpected_error_is_recorded_and_not_raised():
    def boom(request):
        raise RuntimeError("synthetic")
    gate, _ = make_gate(clean_site(**{"acme.example/feed.xml": boom}))
    c = vet_candidate(candidate(), gate, SETTINGS)
    assert c.usable is False and "vetting error: RuntimeError" in c.notes


def test_no_search_engine_address_in_the_vetting_code():
    text = Path(vet_module.__file__).read_text(encoding="utf-8")
    assert not re.search(r"https?://[^\s'\"]*(google|bing|duckduckgo|yahoo|baidu|yandex)", text, re.I)


# ---------- trust score ----------

def scored(**kw) -> Candidate:
    return candidate(**kw)


def test_trust_score_table_for_five_hand_made_candidates():
    a = scored(terms_status="ok", robots_status="allowed", access_method="rss", feed_url="https://acme.example/f",
               newest_item_date="2026-10-31", relevance_sample=0.6, type_guess="government")
    b = scored(terms_status="unknown", robots_status="allowed", access_method="html",
               item_url_pattern="^https://acme.example/news/[a-z]+$", newest_item_date="2026-09-11",
               relevance_sample=0.3, notes="[seed:unverified]", discovered_via="seed")
    c = scored(terms_status="forbids_automation", robots_status="allowed", access_method="rss",
               feed_url="https://acme.example/f", newest_item_date="2026-11-09", relevance_sample=1.0)
    d = scored(terms_status="ok", robots_status="allowed", access_method="html", notes="",
               discovered_via="outbound_link")
    e = scored(terms_status="ok", robots_status="unknown", access_method="rss", feed_url="https://feeds.other.example/x",
               newest_item_date="2026-04-24", relevance_sample=0.1, notes="[seed:verified]", discovered_via="seed")
    expected = [(a, 100), (b, 55), (c, 0), (d, 40), (e, 60)]
    for cand, points in expected:
        score, reasons = trust_score(cand, TODAY)
        assert score == points, (cand.name, reasons)
        assert len(reasons) == 7 and all(re.match(r"^[a-z ]+: \+\d+ ", line) for line in reasons)
        assert 0 <= score <= 100
    assert "automatic fail" in trust_score(c, TODAY)[1][0]


@pytest.mark.parametrize("age,points", [(0, 15), (30, 15), (31, 10), (90, 10), (91, 5), (365, 5), (366, 0)])
def test_freshness_boundaries(age, points):
    newest = date.fromordinal(TODAY.toordinal() - age).isoformat()
    _, reasons = trust_score(scored(newest_item_date=newest), TODAY)
    assert reasons[3].startswith(f"freshness: +{points} ")


@pytest.mark.parametrize("share,points", [(None, 0), (0.0, 0), (0.05, 5), (0.24, 5), (0.25, 10), (0.49, 10), (0.5, 15), (1.0, 15)])
def test_relevance_boundaries(share, points):
    _, reasons = trust_score(scored(relevance_sample=share), TODAY)
    assert reasons[4].startswith(f"relevance: +{points} ")


def test_trust_score_is_pure_and_never_above_100():
    cand = scored(terms_status="ok", robots_status="allowed", access_method="rss", feed_url="https://acme.example/f",
                  newest_item_date="2026-11-10", relevance_sample=1.0, type_guess="government")
    snapshot = cand.model_dump()
    assert trust_score(cand, TODAY) == trust_score(cand, TODAY)
    assert cand.model_dump() == snapshot and trust_score(cand, TODAY)[0] == 100


# ---------- website terms, not purchase terms (found in the Phase 2 demo run: Sundyne / Honeywell) ----------

PURCHASE_ONLY_HOME = """<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head><body>
<footer><a href="/purchase-terms">Supplier Terms and Conditions</a> <a href="/sales-terms">Terms and Conditions of Sales/Service</a>
<a href="/news">News</a></footer></body></html>"""


def test_purchase_and_sales_terms_alone_are_not_terms_ok():
    routes = clean_site(**{"acme.example/": page(PURCHASE_ONLY_HOME), "acme.example/purchase-terms": page(CLEAN_TERMS),
                           "acme.example/sales-terms": page(CLEAN_TERMS)})
    c = vet_candidate(candidate(), make_gate(routes)[0], SETTINGS)
    assert c.terms_status == "unknown" and not c.usable
    assert "purchase or sales conditions" in c.notes


PARENT_HOME = """<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head><body>
<footer><a href="/purchase-terms">Supplier Terms and Conditions</a>
<a href="https://parent.example/terms-and-conditions">Terms &amp; Conditions</a><a href="/news">News</a></footer></body></html>"""

PARENT_BAN = ("<html><body><p>You may not use any robot, spider, or other automatic device, process, or means "
              "to access the Site for any purpose, including monitoring or copying any of the material.</p></body></html>")


def test_a_parent_companys_website_terms_are_followed_and_can_forbid():
    routes = clean_site(**{"acme.example/": page(PARENT_HOME), "acme.example/purchase-terms": page(CLEAN_TERMS),
                           "parent.example/terms-and-conditions": page(PARENT_BAN)})
    c = vet_candidate(candidate(), make_gate(routes)[0], SETTINGS)
    assert c.terms_status == "forbids_automation" and c.status == "rejected_by_rules" and not c.usable
    assert c.terms_url == "https://parent.example/terms-and-conditions" and "robot" in c.terms_evidence


def test_website_terms_of_use_are_read_before_sales_terms():
    from lxml import html as lxml_html
    from atlas.scout.vet import find_terms_links
    doc = lxml_html.fromstring(
        '<body><a href="/general-terms">General terms and conditions</a><a href="/sales">Terms of Sale</a>'
        '<a href="/terms-of-use">Terms of use</a></body>')
    links = find_terms_links(doc, "https://acme.example/", "acme.example")
    assert links[0] == "https://acme.example/terms-of-use" and links[-1] == "https://acme.example/sales"


def test_a_third_party_platforms_terms_are_not_the_sites_terms():
    from lxml import html as lxml_html
    from atlas.scout.vet import find_terms_links
    doc = lxml_html.fromstring(
        '<body><a href="https://policies.google.com/terms">Terms</a><a href="https://www.facebook.com/terms">Terms</a>'
        '<a href="https://parent.example/terms">Terms &amp; Conditions</a><a href="/terms-of-use">Terms of use</a></body>')
    links = find_terms_links(doc, "https://acme.example/", "acme.example")
    assert links == ["https://acme.example/terms-of-use", "https://parent.example/terms"]


def test_a_parent_terms_page_that_redirects_within_its_own_host_is_read():
    routes = clean_site(**{
        "acme.example/": page(PARENT_HOME), "acme.example/purchase-terms": page(CLEAN_TERMS),
        "parent.example/terms-and-conditions": (301, {"location": "https://parent.example/us/en/terms"}, ""),
        "parent.example/us/en/terms": page(PARENT_BAN)})
    c = vet_candidate(candidate(), make_gate(routes)[0], SETTINGS)
    assert c.terms_status == "forbids_automation" and c.terms_url == "https://parent.example/terms-and-conditions"


def test_a_redirect_to_another_site_is_still_refused():
    routes = clean_site(**{
        "acme.example/": page(PARENT_HOME), "acme.example/purchase-terms": page(CLEAN_TERMS),
        "parent.example/terms-and-conditions": (301, {"location": "https://elsewhere.example/terms"}, ""),
        "elsewhere.example/terms": page(PARENT_BAN)})
    c = vet_candidate(candidate(), make_gate(routes)[0], SETTINGS)
    assert c.terms_status == "unknown"
