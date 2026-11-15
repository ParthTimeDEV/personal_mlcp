"""Offline tests for atlas/scout/discover.py (httpx.MockTransport, synthetic sites only)."""
import logging
import re
from datetime import date
from pathlib import Path

import httpx
import pytest

from atlas.compliance import ComplianceGate, load_register
from atlas.models import ScoutSettings, Source
from atlas.scout import discover as discover_module
from atlas.scout.discover import (
    GatedFetcher, BudgetExhausted, RateLimited, discover_candidates, load_seeds, make_candidate_id,
    probe_source, registered_domain,
)

SEARCH_LABELS = ("google", "bing", "duckduckgo", "yahoo", "baidu", "yandex", "ecosia", "startpage")


def page(body: str, status: int = 200, ctype: str = "text/html; charset=utf-8", headers=None):
    return (status, {"content-type": ctype, **(headers or {})}, body)


def make_gate(routes: dict, robots: dict | None = None):
    """routes: 'host/path' -> page(...) tuple or callable(request). robots: host -> robots.txt text."""
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

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gate = ComplianceGate([], client=client, min_delay=0.0, contact_email="test@example.org")
    gate._sleep = lambda s: None
    return gate, requested


def seeds_file(tmp_path: Path, entries: list[dict] | None = None) -> str:
    lines = []
    for e in entries or []:
        lines.append("- " + ", ".join(f"{k}: {v!r}" if isinstance(v, str) else f"{k}: {str(v).lower()}"
                                       for k, v in e.items()).join("{}"))
    path = tmp_path / "seeds.yaml"
    path.write_text("\n".join(lines) + "\n" if lines else "[]\n", encoding="utf-8")
    return str(path)


def seed(name: str, url: str, **kw) -> dict:
    return {"name": name, "url": url, "type_guess": "trade_news", "region": "US", "why": "test", "verified": False, **kw}


def register_source(**kw) -> Source:
    base = dict(source_id="acme_news", name="Acme News", url="https://acme.example/news", type="trade_news",
                access_method="rss", feed_url="https://acme.example/feed", robots_status="allowed",
                terms_status="ok", vetting_status="working", status="proposed", review_date=date(2026, 10, 29))
    base.update(kw)
    return Source(**base)


SETTINGS = ScoutSettings()
FEED_LINK = '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'


# ---------- helpers ----------

def test_registered_domain_and_ids():
    assert registered_domain("https://www.news.example.co.uk/a/b") == "example.co.uk"
    assert registered_domain("https://sub.acme.example/x") == "acme.example"
    assert registered_domain("WWW.Acme.Example") == "acme.example"
    assert registered_domain("https://www.nrcan.gc.ca/x") == "nrcan.gc.ca"
    cid = make_candidate_id("acme.example")
    assert len(cid) == 12 and cid == make_candidate_id("acme.example")


# ---------- seeds ----------

def test_seed_read_and_candidate_fields(tmp_path):
    path = seeds_file(tmp_path, [seed("Beta", "https://beta.example/", region="CA", association=True),
                                 seed("Gamma", "https://www.gamma.example/", type_guess="government")])
    gate, _ = make_gate({"beta.example/": page("<html></html>"), "www.gamma.example/": page("<html></html>")})
    cands = discover_candidates([], gate, SETTINGS, seeds_path=path)
    assert [c.domain for c in cands] == ["beta.example", "gamma.example"]
    beta, gamma = cands
    assert beta.discovered_via == "seed" and beta.discovered_from == path
    assert beta.region == "CA" and "[association]" in beta.notes and "[seed:unverified]" in beta.notes
    assert gamma.type_guess == "government"
    assert beta.candidate_id == make_candidate_id("beta.example")
    assert all(c.status == "new" and not c.usable and c.trust_score == 0 for c in cands)


def test_known_domains_register_and_duplicates_are_skipped(tmp_path):
    path = seeds_file(tmp_path, [
        seed("Acme again", "https://www.acme.example/"),  # in the register
        seed("Known", "https://known.example/"),          # passed in known_domains
        seed("New", "https://new.example/"),
        seed("New twin", "https://www.new.example/other"),  # same registered domain
    ])
    gate, _ = make_gate({})
    cands = discover_candidates([register_source()], gate, SETTINGS, seeds_path=path,
                                known_domains={"known.example"})
    assert [c.domain for c in cands] == ["new.example"]


def test_max_new_is_honoured(tmp_path):
    path = seeds_file(tmp_path, [seed(f"S{i}", f"https://s{i}.example/") for i in range(6)])
    gate, _ = make_gate({})
    assert len(discover_candidates([], gate, SETTINGS, seeds_path=path, max_new=2)) == 2


def test_malformed_seed_raises_and_names_the_entry(tmp_path):
    path = seeds_file(tmp_path, [seed("Bad", "https://bad.example/", type_guess="newspaper")])
    with pytest.raises(ValueError, match="Bad"):
        load_seeds(path)
    path2 = seeds_file(tmp_path, [seed("NoScheme", "bad.example")])
    with pytest.raises(ValueError, match="NoScheme"):
        load_seeds(path2)


def test_shipped_seed_file_is_valid_unverified_and_new():
    seeds = load_seeds()
    assert 30 <= len(seeds) <= 40
    assert all(s["verified"] is False for s in seeds)
    domains = [registered_domain(s["url"]) for s in seeds]
    assert len(domains) == len(set(domains)), "duplicate seed domains"
    register_domains = {registered_domain(s.url) for s in load_register()}
    assert not (set(domains) & register_domains), "a seed is already in config/sources.yaml"
    regions = {s["region"] for s in seeds}
    assert {"US", "CA"} <= regions


# ---------- outbound links ----------

def test_outbound_links_are_filtered(empty_seeds):
    feed = """<?xml version="1.0"?><rss version="2.0"><channel><title>Acme</title>
    <item><title>One</title><link>https://acme.example/news/one</link></item>
    <item><title>Two</title><link>https://acme.example/news/two</link></item></channel></rss>"""
    article = """<html><body>
    <a href="https://www.facebook.com/acme">fb</a> <a href="https://twitter.com/acme">tw</a>
    <a href="https://www.google.com/search?q=x">g</a> <a href="https://bit.ly/abc">short</a>
    <a href="https://www.linkedin.com/company/acme">li</a> <a href="/news/internal">internal</a>
    <a href="https://acme.example/about">own</a> <a href="https://known.example/page">known</a>
    <a href="https://www.publisher.example/story">publisher</a> <a href="mailto:a@b.example">mail</a>
    <a href="https://nrcan.gc.ca/energy">gov</a> <a href="https://shop.maker.example/x">maker</a>
    </body></html>"""
    routes = {"acme.example/feed": page(feed, ctype="application/rss+xml"),
              "acme.example/news/one": page(article), "acme.example/news/two": page(article),
              "www.publisher.example/": page("<html></html>"), "nrcan.gc.ca/": page("<html></html>"),
              "shop.maker.example/": page("<html></html>")}
    gate, requested = make_gate(routes)
    cands = discover_candidates([register_source()], gate, SETTINGS, seeds_path=empty_seeds,
                                known_domains={"known.example"})
    by_domain = {c.domain: c for c in cands}
    assert set(by_domain) == {"publisher.example", "nrcan.gc.ca", "maker.example"}
    assert all(c.discovered_via == "outbound_link" for c in cands)
    assert by_domain["nrcan.gc.ca"].type_guess == "government"
    assert by_domain["publisher.example"].type_guess == "trade_news"
    assert "type unknown" in by_domain["publisher.example"].notes
    hosts = {h for h, _ in requested}
    assert not any(label in h for h in hosts for label in ("facebook", "twitter", "linkedin", "bit.ly"))
    assert not any(label in h for h in hosts for label in SEARCH_LABELS)


@pytest.fixture
def empty_seeds(tmp_path) -> str:
    """An empty seed file, so tests do not read the shipped one."""
    return seeds_file(tmp_path)


def test_blocked_or_unvetted_sources_are_not_used_for_outbound_links(empty_seeds):
    blocked = register_source(source_id="blocked", vetting_status="blocked", status="blocked",
                              terms_status="forbids_automation")
    gate, requested = make_gate({})
    assert discover_candidates([blocked], gate, SETTINGS, seeds_path=empty_seeds) == []
    assert requested == []


# ---------- feed autodiscovery ----------

def test_feed_autodiscovery_rss_atom_and_none(tmp_path):
    path = seeds_file(tmp_path, [seed("Rss", "https://rss.example/"), seed("Atom", "https://atom.example/"),
                                 seed("Plain", "https://plain.example/")])
    routes = {
        "rss.example/": page(f"<html><head>{FEED_LINK}</head></html>"),
        "atom.example/": page('<html><head><link rel="alternate" type="application/atom+xml" href="https://atom.example/atom"></head></html>'),
        "plain.example/": page("<html><head></head></html>"),
    }
    gate, _ = make_gate(routes)
    by = {c.domain: c for c in discover_candidates([], gate, SETTINGS, seeds_path=path)}
    assert by["rss.example"].feed_url == "https://rss.example/feed.xml" and by["rss.example"].access_method == "rss"
    assert by["atom.example"].feed_url == "https://atom.example/atom"
    assert by["plain.example"].feed_url is None and by["plain.example"].access_method == "html"
    assert "no feed advertised" in by["plain.example"].notes


# ---------- robots ----------

def test_robots_disallowed_homepage_is_rejected_and_nothing_else_is_fetched(tmp_path):
    path = seeds_file(tmp_path, [seed("Closed", "https://closed.example/"), seed("Open", "https://open.example/")])
    routes = {"closed.example/": page("<html>secret</html>"), "open.example/": page(f"<html><head>{FEED_LINK}</head></html>")}
    gate, requested = make_gate(routes, robots={"closed.example": "User-agent: *\nDisallow: /\n"})
    by = {c.domain: c for c in discover_candidates([], gate, SETTINGS, seeds_path=path)}
    closed = by["closed.example"]
    assert closed.robots_status == "disallowed" and closed.status == "rejected_by_rules" and not closed.usable
    assert [p for h, p in requested if h == "closed.example"] == ["/robots.txt"]
    assert by["open.example"].feed_url == "https://open.example/feed.xml"


# ---------- never a search engine ----------

def test_no_search_engine_address_in_requests_or_code(tmp_path):
    path = seeds_file(tmp_path, [seed("A", "https://a.example/")])
    gate, requested = make_gate({"a.example/": page("<html></html>")})
    discover_candidates([register_source()], gate, SETTINGS, seeds_path=path)
    assert not [h for h, _ in requested if any(label in h for label in SEARCH_LABELS)]
    source_text = Path(discover_module.__file__).read_text(encoding="utf-8")
    assert not re.search(r"https?://[^\s'\"]*(" + "|".join(SEARCH_LABELS) + ")", source_text, re.I)


def test_search_api_is_skipped_with_one_log_line(caplog, monkeypatch, tmp_path):
    monkeypatch.setenv("SEARCH_API_KEY", "dummy")
    gate, requested = make_gate({})
    with caplog.at_level(logging.INFO, logger="atlas.scout.discover"):
        assert discover_candidates([], gate, SETTINGS, seeds_path=seeds_file(tmp_path)) == []
    assert len([r for r in caplog.records if "search_api" in r.getMessage()]) == 1
    assert requested == []


# ---------- failures ----------

def test_one_failing_candidate_does_not_stop_the_rest(tmp_path):
    path = seeds_file(tmp_path, [seed("Down", "https://down.example/"), seed("Boom", "https://boom.example/"),
                                 seed("Limited", "https://limited.example/"), seed("Fine", "https://fine.example/")])

    def boom(request):
        raise RuntimeError("synthetic failure")

    def down(request):
        raise httpx.ConnectError("no route", request=request)

    routes = {"down.example/": down, "boom.example/": boom,
              "limited.example/": page("slow down", status=429),
              "fine.example/": page(f"<html><head>{FEED_LINK}</head></html>")}
    gate, _ = make_gate(routes)
    by = {c.domain: c for c in discover_candidates([], gate, SETTINGS, seeds_path=path)}
    assert set(by) == {"down.example", "boom.example", "limited.example", "fine.example"}
    assert "fetch_error" in by["down.example"].notes
    assert "discovery error: RuntimeError" in by["boom.example"].notes
    assert "rate limited" in by["limited.example"].notes
    assert by["fine.example"].feed_url == "https://fine.example/feed.xml"


# ---------- Phase 1 is untouched ----------

def test_inputs_are_not_modified(tmp_path):
    path = seeds_file(tmp_path, [seed("A", "https://a.example/")])
    src, settings = register_source(), ScoutSettings()
    before = (src.model_dump(), settings.model_dump())
    gate, _ = make_gate({"a.example/": page("<html></html>")})
    discover_candidates([src], gate, settings, seeds_path=path)
    assert (src.model_dump(), settings.model_dump()) == before


# ---------- the gated fetcher ----------

def test_fetcher_never_follows_a_redirect_off_the_site():
    routes = {"a.example/": page("", status=302, headers={"location": "https://evil.example/x"})}
    gate, requested = make_gate(routes)
    f = GatedFetcher(gate, probe_source("https://a.example/", "a.example"))
    assert f.get("https://a.example/") is None and f.refusal == "redirect_off_host"
    assert ("evil.example", "/x") not in requested


def test_fetcher_budget_and_rate_limit():
    gate, _ = make_gate({"a.example/": page("ok"), "a.example/limited": page("x", status=429)})
    f = GatedFetcher(gate, probe_source("https://a.example/", "a.example"), budget=1)
    assert f.get("https://a.example/").status == 200
    with pytest.raises(BudgetExhausted):
        f.get("https://a.example/")
    g = GatedFetcher(gate, probe_source("https://a.example/", "a.example"))
    with pytest.raises(RateLimited):
        g.get("https://a.example/limited")
