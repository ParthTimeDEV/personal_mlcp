from datetime import date

import httpx
import pytest

from atlas.collect import collect_source
from atlas.compliance import ComplianceGate
from atlas.models import CollectResult, FetchedPage, Item, ScoutSettings, Source, WatchEntry
from atlas.scout import fallback as fb

ENTRIES = [WatchEntry(name="Ingersoll Rand", aliases=["Ingersoll-Rand"]),
           WatchEntry(name="Kaeser Compressors", aliases=["Kaeser"]),
           WatchEntry(name="Opted Out", follow_when_blocked=False)]


def src(source_id, name, host, **kw) -> Source:
    base = dict(source_id=source_id, name=name, url=f"https://{host}/news", type="trade_news",
                access_method="rss", feed_url=f"https://{host}/feed", robots_status="allowed",
                terms_status="ok", vetting_status="working", review_date=date(2026, 10, 1))
    base.update(kw)
    return Source(**base)


IR = src("ingersoll_rand_news", "Ingersoll Rand Newsroom", "irco.example", vetting_status="unreachable")
TRADE = src("trade_news", "Trade Weekly", "trade.example")
GOV = src("gov_news", "Energy Dept", "gov.example", type="government")


def item(n, source="trade_news", title="Ingersoll Rand opens a new plant", facts=(), **kw) -> Item:
    base = dict(id=f"i{n:011d}", source_id=source, source_name=source, source_type="trade_news",
                source_url=f"https://trade.example/a{n}", licence_note="x", collected_at="2026-10-29T10:00:00Z",
                published_at="2026-10-20", title=title, key_facts=list(facts), page_fingerprint=str(n))
    base.update(kw)
    return Item(**base)


# ---- planning ----

def test_plan_matches_by_name_and_company():
    entries, refused_by, notes = fb.plan_switching([IR], ENTRIES)
    assert [e.name for e in entries] == ["Ingersoll Rand"]
    assert refused_by == {"Ingersoll Rand": "ingersoll_rand_news"} and notes == []


def test_plan_matches_by_alias():
    kaeser = src("kaeser", "Kaeser Kompressoren Newsroom", "k.example")
    entries, _, _ = fb.plan_switching([kaeser], ENTRIES)
    assert [e.name for e in entries] == ["Kaeser Compressors"]


def test_no_watch_entry_means_nothing_to_switch_to():
    entries, refused_by, notes = fb.plan_switching([src("x", "Unknown Maker News", "x.example")], ENTRIES)
    assert entries == [] and refused_by == {}
    assert notes == ["x: no watch entry, nothing to switch to"]


def test_entries_that_do_not_follow_when_blocked_are_ignored():
    entries, _, notes = fb.plan_switching([src("o", "Opted Out Newsroom", "o.example")], ENTRIES)
    assert entries == [] and notes


def test_plan_fallback_contract_returns_entries():
    assert [e.name for e in fb.plan_fallback([IR], ENTRIES)] == ["Ingersoll Rand"]


# ---- labelling ----

def test_items_mentioning_an_entry_are_labelled_by_copy():
    original = [item(1), item(2, title="Unrelated dryer news"), item(3, title="Plant news", facts=["Ingersoll-Rand said so."])]
    labelled = fb.apply_fallback_labels(original, ENTRIES[:1], {"Ingersoll Rand": "ingersoll_rand_news"})
    assert [i.via_fallback for i in labelled] == [True, False, True]
    assert labelled[0].fallback_for == "ingersoll_rand_news" and labelled[0].watch_matches == ["Ingersoll Rand"]
    assert original[0].via_fallback is False  # not mutated


def test_company_field_counts_even_when_title_and_facts_do_not_name_it():
    # live case: an EXPO article whose extracted company is Kaeser, but whose title never says so
    expo = item(1, title="Best Practices 2026 EXPO delivers record attendance", company="Kaeser Compressors")
    assert fb.find_matches(expo, ENTRIES) == ["Kaeser Compressors"]
    assert fb.find_matches(item(2, title="Unrelated dryer news", company="Acme"), ENTRIES) == []


def test_whole_word_match_only():
    assert fb.find_matches(item(1, title="Ingersoll Randolph visits"), ENTRIES[:1]) == []


def test_item_from_the_refused_source_itself_is_never_labelled():
    own = item(1, source="ingersoll_rand_news")
    (out,) = fb.apply_fallback_labels([own], ENTRIES[:1], {"Ingersoll Rand": "ingersoll_rand_news"})
    assert out.via_fallback is False


# ---- the guard ----

@pytest.mark.parametrize("url", [
    "https://web.archive.org/web/2026/https://irco.example/news",
    "https://archive.ph/abc", "https://webcache.googleusercontent.com/search?q=cache:x",
    "https://irco-example.translate.goog/news", "https://irco.example/news", "https://www.irco.example/a",
    "https://press.irco.example/a",
])
def test_forbidden_routes_are_refused(url):
    assert fb.forbidden_reason(url, ["irco.example"]).startswith("fallback_forbidden_route")


def test_other_sites_are_allowed():
    assert fb.forbidden_reason("https://trade.example/news/1", ["irco.example"]) is None
    assert fb.forbidden_reason("https://notirco.example/a", ["irco.example"]) is None


# ---- collection (mocked transport; the request log is the proof) ----

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>"""
ENTRY = "<item><title>{t}</title><link>{l}</link><pubDate>Tue, 20 Oct 2026 10:00:00 GMT</pubDate></item>"


def make_gate(handler, sources):
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    gate = ComplianceGate(sources, client=client, contact_email="t@example.org")
    gate._sleep = lambda s: None
    return gate


def site(requests, links):
    """Mock web: robots allow all, the feed lists `links`, every article is a trivial HTML page."""
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if path == "/feed":
            body = RSS.format(items="".join(ENTRY.format(t=f"T{i}", l=l) for i, l in enumerate(links)))
            return httpx.Response(200, text=body, headers={"content-type": "application/rss+xml"})
        return httpx.Response(200, text="<html><body>x</body></html>", headers={"content-type": "text/html"})
    return handler


def page_extract(mentions: set[str]):
    """Extractor stand-in: an item mentions the entry only if its URL is in `mentions`."""
    def extract(page: FetchedPage, source: Source) -> Item:
        title = "Ingersoll Rand news" if page.final_url in mentions else "Dryer news"
        return item(abs(hash(page.final_url)) % 10**9, source=source.source_id, title=title,
                    source_url=page.final_url)
    return extract


def run_fb(requests, links, mentions, settings=None, already=(), allowed=None, **kw):
    gate = make_gate(site(requests, links), [IR, TRADE, GOV])
    settings = settings or ScoutSettings()
    entries, refused_by, _ = fb.plan_switching([IR], ENTRIES)
    return fb.collect_fallback_items(
        entries, refused_by, allowed or [TRADE], gate, settings, list(already), refused=[IR],
        collect=collect_source, extract=page_extract(set(mentions)), **kw)


def test_second_pass_keeps_only_matching_items_and_never_touches_the_refused_host():
    requests: list[str] = []
    links = [f"https://trade.example/a{i}" for i in range(4)]
    result, items = run_fb(requests, links, mentions={links[1], links[3]})
    assert sorted(i.source_url for i in items) == [links[1], links[3]]
    assert len(result.pages) == 2
    assert requests and not any("irco.example" in r for r in requests)
    assert not any(m in r for r in requests for m in fb.FORBIDDEN_MARKERS)


def test_cap_per_source_is_honoured():
    requests: list[str] = []
    links = [f"https://trade.example/a{i}" for i in range(6)]
    result, items = run_fb(requests, links, mentions=set(links),
                           settings=ScoutSettings(fallback_max_items_per_source=2))
    assert len(items) == 2 and len(result.pages) == 2
    assert sum(1 for r in requests if "/a" in r) == 2  # nothing extra was fetched


def test_pages_already_collected_are_not_fetched_again():
    requests: list[str] = []
    links = [f"https://trade.example/a{i}" for i in range(3)]
    have = [item(1, source_url=links[0]), item(2, source_url=links[1])]
    _, items = run_fb(requests, links, mentions=set(links), already=have)
    assert [i.source_url for i in items] == [links[2]]
    assert not any(r.endswith("/a0") or r.endswith("/a1") for r in requests)


def test_switching_disabled_means_no_second_pass():
    requests: list[str] = []
    result, items = run_fb(requests, ["https://trade.example/a0"], {"https://trade.example/a0"},
                           settings=ScoutSettings(fallback_enabled=False))
    assert items == [] and result.pages == [] and requests == []


def test_source_types_not_selected_are_skipped():
    requests: list[str] = []
    settings = ScoutSettings(source_types=["government"])
    _, items = run_fb(requests, ["https://trade.example/a0"], {"https://trade.example/a0"}, settings=settings)
    assert items == [] and requests == []


def test_an_allowed_source_on_the_refused_domain_is_not_used():
    requests: list[str] = []
    twin = src("twin", "Twin", "irco.example")
    result, items = run_fb(requests, [], set(), allowed=[twin])
    assert items == [] and requests == []
    assert result.refusals[0].reason.startswith("fallback_forbidden_route")


def test_a_link_into_the_refused_site_is_refused_and_recorded():
    requests: list[str] = []
    links = ["https://irco.example/secret", "https://trade.example/a1"]
    # the feed itself is on trade.example; same_site() already drops the foreign link, the guard is the backstop
    result, items = run_fb(requests, links, mentions={"https://trade.example/a1"})
    assert not any("irco.example" in r for r in requests)
    assert [i.source_url for i in items] == ["https://trade.example/a1"]


def test_rate_limit_stops_that_source_only():
    requests: list[str] = []
    gov_link = "https://gov.example/a0"
    trade_web = site(requests, ["https://trade.example/a0"])
    gov_web = site(requests, [gov_link])

    def handler(request):
        if request.url.host == "trade.example" and request.url.path.startswith("/a"):
            requests.append(str(request.url))
            return httpx.Response(429)
        return (gov_web if request.url.host == "gov.example" else trade_web)(request)

    gate = make_gate(handler, [IR, TRADE, GOV])
    entries, refused_by, _ = fb.plan_switching([IR], ENTRIES)
    result, items = fb.collect_fallback_items(
        entries, refused_by, [TRADE, GOV], gate, ScoutSettings(), [], refused=[IR],
        collect=collect_source, extract=page_extract({gov_link}))
    assert any(r.reason == "rate_limited_stop" for r in result.refusals)
    assert [i.source_url for i in items] == [gov_link]  # the other source was still read


def test_extract_error_is_recorded_not_hidden():
    def boom(page, source):
        raise ValueError("bad page")

    requests: list[str] = []
    gate = make_gate(site(requests, ["https://trade.example/a0"]), [IR, TRADE])
    entries, refused_by, _ = fb.plan_switching([IR], ENTRIES)
    result, items = fb.collect_fallback_items(entries, refused_by, [TRADE], gate, ScoutSettings(), [],
                                              refused=[IR], collect=collect_source, extract=boom)
    assert items == [] and result.refusals[-1].reason == "fallback_extract_error:ValueError"


def test_delay_is_kept_between_requests():
    requests: list[str] = []
    sleeps: list[float] = []
    gate = make_gate(site(requests, ["https://trade.example/a0", "https://trade.example/a1"]), [IR, TRADE])
    gate._sleep = sleeps.append
    gate._now = lambda: 100.0  # the clock never advances, so each request must wait the full delay
    entries, refused_by, _ = fb.plan_switching([IR], ENTRIES)
    fb.collect_fallback_items(entries, refused_by, [TRADE], gate, ScoutSettings(), [], refused=[IR],
                              collect=collect_source, extract=page_extract(set()))
    assert sleeps and all(s >= 3.0 for s in sleeps)


def test_unresolvable_refused_source_raises():
    gate = make_gate(site([], []), [TRADE])
    with pytest.raises(ValueError, match="cannot resolve"):
        fb.collect_fallback_items(ENTRIES[:1], {"Ingersoll Rand": "ghost"}, [TRADE], gate, ScoutSettings(), [])


def test_contract_wrapper_returns_a_collect_result(monkeypatch):
    monkeypatch.setattr(fb, "collect_fallback_items",
                        lambda *a, **k: (CollectResult(source_id="fallback"), []))
    assert isinstance(fb.collect_fallback([], {}, [], None, ScoutSettings(), []), CollectResult)
