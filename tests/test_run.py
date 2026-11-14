from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from atlas import run as run_mod
from atlas.models import (
    Candidate, CleanResult, CollectResult, FetchedPage, GateDecision, Item, OutputEnvelope, Refusal,
    ScoutSettings, Source, WatchEntry,
)
from atlas.scout import fallback, settings_store, stories


def make_source(source_id="src_a", **kw) -> Source:
    base = dict(
        source_id=source_id, name=f"{source_id} newsroom", url=f"https://{source_id}.example/news",
        type="competitor", access_method="rss", robots_status="allowed", terms_status="ok",
        vetting_status="working", status="proposed", review_date=date(2026, 10, 29), region="US",
    )
    base.update(kw)
    return Source(**base)


def make_page(source_id, n) -> FetchedPage:
    return FetchedPage(
        source_id=source_id, url=f"https://{source_id}.example/news/{n}",
        final_url=f"https://{source_id}.example/news/{n}", status_code=200, html="<p>secret page text</p>",
        listing_title=f"Title {n}", listing_published="2026-10-01", via="rss",
    )


def make_item(page: FetchedPage, source: Source, compressor=True) -> Item:
    recent = (date.today() - timedelta(days=10)).isoformat()
    return Item(
        id=page.final_url[-12:].rjust(12, "0"), source_id=source.source_id, source_name=source.name,
        source_type=source.type, source_url=page.final_url, licence_note=source.licence_note,
        collected_at=page.fetched_at, published_at=recent, title=page.listing_title,
        page_fingerprint=page.final_url, matched_keywords=["compressor"] if compressor else [],
        mentions_us_location=True,
    )


class FakeGate:
    def __init__(self, sources):
        self.refusals: list[Refusal] = []
        self.blocked = {s.source_id for s in sources if s.vetting_status != "working"}

    def check_source(self, source):
        if source.source_id in self.blocked:
            self.refusals.append(Refusal(source_id=source.source_id, reason="vetting_blocked"))
            return GateDecision(source_id=source.source_id, allowed=False, reasons=["vetting_blocked"])
        return GateDecision(source_id=source.source_id, allowed=True)


@pytest.fixture
def writes(monkeypatch):
    """Capture every storage write; nothing reaches Databricks or disk."""
    store: dict = {}
    monkeypatch.setattr(run_mod.storage, "ensure_folders", lambda: store.setdefault("_folders", True))
    monkeypatch.setattr(run_mod.storage, "write_json", lambda path, obj: store.__setitem__(path, obj))
    return store


def install_stages(monkeypatch, sources, pages_per_source=2, extract=None, collect=None, gate_cls=FakeGate,
                   settings=None, candidates=None, decisions=None, discovery=None, **extra):
    def default_collect(source, gate, max_items=20):
        pages = [make_page(source.source_id, n) for n in range(pages_per_source)]
        return CollectResult(source_id=source.source_id, pages=pages, listing_count=len(pages))

    def default_extract(page, source):
        return make_item(page, source, compressor=not page.final_url.endswith("1"))

    stages = SimpleNamespace(
        ComplianceGate=gate_cls,
        load_register=lambda: sources,
        collect_source=collect or default_collect,
        extract_item=extract or default_extract,
        clean_items=lambda items: CleanResult(items=items, duplicates_dropped=0),
        load_settings=lambda: settings or ScoutSettings(),
        default_settings=lambda: ScoutSettings(),
        load_candidates=lambda: list(candidates or []),
        save_candidates=lambda cands: saved_candidates.extend(cands),
        load_decisions=lambda: list(decisions or []),
        usable_sources=settings_store.usable_sources,
        load_discovery=discovery or (lambda: (_ for _ in ()).throw(RuntimeError("discovery not installed"))),
        plan_switching=fallback.plan_switching,
        collect_fallback_items=fallback.collect_fallback_items,
        apply_fallback_labels=fallback.apply_fallback_labels,
        build_stories=stories.build_stories,
    )
    for key, value in extra.items():
        setattr(stages, key, value)
    saved_candidates = stages.saved_candidates = []
    monkeypatch.setattr(run_mod, "_stages", lambda: stages)
    return stages


def paths_of(writes, prefix):
    return [p for p in writes if p.startswith(prefix)]


def test_happy_path_two_sources(monkeypatch, writes, capsys):
    sources = [make_source("src_a"), make_source("src_b")]
    install_stages(monkeypatch, sources)
    code = run_mod.main([])
    out = capsys.readouterr().out

    assert code == 0
    assert "source_register/sources.json" in writes
    for prefix in ("raw/src_a/", "raw/src_b/", "clean/src_a/", "clean/src_b/", "facts/src_a/", "facts/src_b/"):
        assert len(paths_of(writes, prefix)) == 1, prefix
    (output_path,) = paths_of(writes, "output/")
    (log_path,) = paths_of(writes, "logs/")
    envelope = OutputEnvelope.model_validate(writes[output_path])
    assert len(envelope.sources) == 2
    # each source: 2 pages, page "...1" has no compressor keyword -> 1 passed
    assert [s.items_collected for s in envelope.sources] == [2, 2]
    assert [s.items_passed for s in envelope.sources] == [1, 1]
    assert writes[log_path]["counts"]["src_a"]["passed"] == 1
    assert "output validated: PASS" in out and "local data check: PASS" in out


def test_output_has_only_passed_clean_has_all(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a")])
    run_mod.main([])
    (output_path,) = paths_of(writes, "output/")
    (clean_path,) = paths_of(writes, "clean/")
    (facts_path,) = paths_of(writes, "facts/")
    assert len(writes[clean_path]) == 2
    assert len(writes[facts_path]) == 1
    assert len(writes[output_path]["items"]) == 1
    failed = [i for i in writes[clean_path] if not i["filter"]["passed"]]
    assert failed and failed[0]["filter"]["reasons"] == ["no_compressor_keyword"]


def test_raw_has_metadata_but_no_page_text(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a")])
    run_mod.main([])
    (raw_path,) = paths_of(writes, "raw/")
    assert writes[raw_path][0]["title"] == "Title 0"
    assert "secret page text" not in str(writes)


def test_refused_source_is_skipped_and_reported(monkeypatch, writes, capsys):
    sources = [make_source("src_a"), make_source("src_blocked", vetting_status="blocked")]
    install_stages(monkeypatch, sources)
    code = run_mod.main([])
    out = capsys.readouterr().out

    assert code == 0  # a blocked source is a finding, not an error
    assert paths_of(writes, "raw/src_blocked/") == []
    (output_path,) = paths_of(writes, "output/")
    blocked = next(s for s in writes[output_path]["sources"] if s["source_id"] == "src_blocked")
    assert "vetting_blocked" in blocked["note"]
    assert "src_blocked: vetting_blocked" in out
    (log_path,) = paths_of(writes, "logs/")
    assert any(r["reason"] == "vetting_blocked" for r in writes[log_path]["refusals"])


def test_extract_error_is_logged_and_run_continues(monkeypatch, writes, capsys):
    def flaky_extract(page, source):
        if page.final_url.endswith("0"):
            raise ValueError("unparseable page")
        return make_item(page, source)

    install_stages(monkeypatch, [make_source("src_a")], extract=flaky_extract)
    code = run_mod.main([])
    out = capsys.readouterr().out

    assert code == 1
    (log_path,) = paths_of(writes, "logs/")
    assert any("ValueError: unparseable page" in e for e in writes[log_path]["errors"])
    (output_path,) = paths_of(writes, "output/")
    assert len(writes[output_path]["items"]) == 1  # the other page still made it
    assert "unparseable page" in out


def test_collector_crash_does_not_stop_other_sources(monkeypatch, writes):
    def collect(source, gate, max_items=20):
        if source.source_id == "src_a":
            raise RuntimeError("boom")
        return CollectResult(source_id=source.source_id, pages=[make_page(source.source_id, 0)], listing_count=1)

    install_stages(monkeypatch, [make_source("src_a"), make_source("src_b")], collect=collect)
    code = run_mod.main([])

    assert code == 1
    assert paths_of(writes, "facts/src_b/")
    (output_path,) = paths_of(writes, "output/")
    summaries = {s["source_id"]: s for s in writes[output_path]["sources"]}
    assert "RuntimeError: boom" in summaries["src_a"]["note"]
    assert summaries["src_b"]["items_passed"] == 1


def test_only_flag_limits_to_one_source(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a"), make_source("src_b")])
    assert run_mod.main(["--only", "src_b"]) == 0
    assert paths_of(writes, "raw/src_a/") == []
    assert paths_of(writes, "raw/src_b/")


def test_unknown_only_returns_2(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a")])
    assert run_mod.main(["--only", "nope"]) == 2
    assert paths_of(writes, "output/") == []


def test_max_items_is_passed_to_collector(monkeypatch, writes):
    seen = {}

    def collect(source, gate, max_items=20):
        seen["max_items"] = max_items
        return CollectResult(source_id=source.source_id)

    install_stages(monkeypatch, [make_source("src_a")], collect=collect)
    run_mod.main(["--max-items", "5"])
    assert seen["max_items"] == 5


def test_missing_contact_email_stops_the_run(monkeypatch, writes, capsys):
    class NoEmailGate:
        def __init__(self, sources):
            raise RuntimeError("CONTACT_EMAIL is not set in .env")

    install_stages(monkeypatch, [make_source("src_a")], gate_cls=NoEmailGate)
    assert run_mod.main([]) == 1
    assert "CONTACT_EMAIL" in capsys.readouterr().err
    assert paths_of(writes, "output/") == []


def test_collection_refusals_reach_the_log(monkeypatch, writes):
    def collect(source, gate, max_items=20):
        return CollectResult(
            source_id=source.source_id, pages=[make_page(source.source_id, 0)], listing_count=2,
            refusals=[Refusal(source_id=source.source_id, url="https://x.example/p", reason="http_404")],
        )

    install_stages(monkeypatch, [make_source("src_a")], collect=collect)
    assert run_mod.main([]) == 0
    (log_path,) = paths_of(writes, "logs/")
    assert [r["reason"] for r in writes[log_path]["refusals"]] == ["http_404"]


def test_no_local_files_written(monkeypatch, writes, tmp_path):
    monkeypatch.chdir(tmp_path)
    install_stages(monkeypatch, [make_source("src_a")])
    run_mod.main([])
    assert list(tmp_path.iterdir()) == []


# ---------------- phase 2 ----------------

def ir_blocked() -> Source:
    return make_source("ingersoll_rand_news", name="Ingersoll Rand Newsroom", vetting_status="unreachable")


def mention_extract(page, source):
    """Pages numbered 1, 5 and 6 are about Ingersoll Rand (the refused company); the rest are not."""
    item = make_item(page, source)
    if page.final_url.endswith(("1", "5", "6")):
        item = item.model_copy(update={"title": "Ingersoll Rand opens new plant", "matched_keywords": ["compressor"]})
    return item


def two_pass_collect():
    """First call per source: pages 0 and 1. Later calls (switching): pages 0, 1, 5, 6."""
    calls: dict = {}

    def collect(source, gate, max_items=20):
        calls[source.source_id] = calls.get(source.source_id, 0) + 1
        numbers = [0, 1] if calls[source.source_id] == 1 else [0, 1, 5, 6]
        pages = [make_page(source.source_id, n) for n in numbers]
        return CollectResult(source_id=source.source_id, pages=pages, listing_count=len(pages))
    return collect


def output_of(writes):
    (path,) = paths_of(writes, "output/")
    return OutputEnvelope.model_validate(writes[path])


def test_refused_source_with_watch_entry_triggers_visible_switching(monkeypatch, writes, capsys):
    install_stages(monkeypatch, [make_source("src_a"), ir_blocked()], extract=mention_extract,
                   collect=two_pass_collect(), settings=ScoutSettings(watchlist=[WatchEntry(name="Ingersoll Rand")]))
    code = run_mod.main([])
    out = capsys.readouterr().out
    assert code == 0  # switching is a finding, not an error

    env = output_of(writes)
    (row,) = [s for s in env.sources if s.kind == "fallback"]
    assert row.fallback_for == "ingersoll_rand_news" and row.source_id == "fallback_ingersoll_rand_news"
    assert row.items_collected == 3 and "src_a newsroom" in row.note  # page 1 (first pass) + 5 and 6 (second pass)
    labelled = [i for i in env.items if i.via_fallback]
    assert len(labelled) == 3 and {i.fallback_for for i in labelled} == {"ingersoll_rand_news"}
    assert all(i.watch_matches == ["Ingersoll Rand"] for i in labelled)
    assert all(i.source_id == "src_a" for i in env.items)  # nothing came from the refused source
    assert "Switched: ingersoll_rand_news -> 3 item(s) from 1 other source(s)" in out
    (log_path,) = paths_of(writes, "logs/")
    assert any("Switched: ingersoll_rand_news" in n for n in writes[log_path]["notes"])
    assert paths_of(writes, "facts/fallback_ingersoll_rand_news/")
    # the first-pass item's own facts file was rewritten with the label
    assert any(i["via_fallback"] for i in writes[paths_of(writes, "facts/src_a/")[0]])


def test_no_fallback_flag_turns_switching_off(monkeypatch, writes, capsys):
    install_stages(monkeypatch, [make_source("src_a"), ir_blocked()], extract=mention_extract,
                   collect=two_pass_collect(), settings=ScoutSettings(watchlist=[WatchEntry(name="Ingersoll Rand")]))
    assert run_mod.main(["--no-fallback"]) == 0
    env = output_of(writes)
    assert not [s for s in env.sources if s.kind == "fallback"]
    assert not any(i.via_fallback for i in env.items)
    assert "Switching is off" in capsys.readouterr().out


def test_fallback_disabled_in_settings_means_no_switching(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a"), ir_blocked()], extract=mention_extract,
                   collect=two_pass_collect(),
                   settings=ScoutSettings(fallback_enabled=False, watchlist=[WatchEntry(name="Ingersoll Rand")]))
    run_mod.main([])
    assert not [s for s in output_of(writes).sources if s.kind == "fallback"]


def test_refused_source_without_watch_entry_logs_nothing_to_switch_to(monkeypatch, writes, capsys):
    install_stages(monkeypatch, [make_source("src_a"), ir_blocked()], settings=ScoutSettings(watchlist=[]))
    assert run_mod.main([]) == 0
    assert not [s for s in output_of(writes).sources if s.kind == "fallback"]
    (log_path,) = paths_of(writes, "logs/")
    assert any("no watch entry, nothing to switch to" in n for n in writes[log_path]["notes"])


def test_zero_pages_also_triggers_switching(monkeypatch, writes):
    two_pass = two_pass_collect()

    def collect(source, gate, max_items=20):
        if source.source_id == "src_empty":
            return CollectResult(source_id=source.source_id)
        return two_pass(source, gate, max_items)

    install_stages(monkeypatch, [make_source("src_a"), make_source("src_empty", name="Ingersoll Rand Newsroom")],
                   extract=mention_extract, collect=collect,
                   settings=ScoutSettings(watchlist=[WatchEntry(name="Ingersoll Rand")]))
    run_mod.main([])
    (row,) = [s for s in output_of(writes).sources if s.kind == "fallback"]
    assert row.fallback_for == "src_empty" and "no pages collected" in row.note


def test_rate_limit_triggers_switching(monkeypatch, writes):
    two_pass = two_pass_collect()

    def collect(source, gate, max_items=20):
        if source.source_id == "src_429":
            return CollectResult(source_id=source.source_id, pages=[make_page("src_429", 9)], listing_count=3,
                                 refusals=[Refusal(source_id="src_429", reason="rate_limited_stop")])
        return two_pass(source, gate, max_items)

    install_stages(monkeypatch, [make_source("src_a"), make_source("src_429", name="Ingersoll Rand Newsroom")],
                   extract=mention_extract, collect=collect,
                   settings=ScoutSettings(watchlist=[WatchEntry(name="Ingersoll Rand")]))
    run_mod.main([])
    (row,) = [s for s in output_of(writes).sources if s.kind == "fallback"]
    assert "rate limited" in row.note


def test_settings_reach_the_filter(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a")], settings=ScoutSettings(excluded_keywords=["title"]))
    run_mod.main([])
    env = output_of(writes)
    assert env.items == []  # every default title contains "Title"
    (clean_path,) = paths_of(writes, "clean/")
    assert all("excluded_keyword" in i["filter"]["reasons"] for i in writes[clean_path])
    assert env.settings_used.excluded_keywords == ["title"]


def test_default_settings_flag_ignores_saved_settings(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a")], settings=ScoutSettings(excluded_keywords=["title"]))
    run_mod.main(["--use-default-settings"])
    assert len(output_of(writes).items) == 1  # same as Phase 1


def test_default_settings_give_the_phase_1_result(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a"), make_source("src_b")])
    run_mod.main([])
    env = output_of(writes)
    assert [s.items_passed for s in env.sources] == [1, 1] and len(env.items) == 2
    assert env.scope.region == "US" and env.scope.technology == "industrial compressors"
    assert env.stories and all(i.story_id for i in env.items)


def test_max_items_defaults_to_the_saved_setting(monkeypatch, writes):
    seen = {}

    def collect(source, gate, max_items=20):
        seen["n"] = max_items
        return CollectResult(source_id=source.source_id)

    install_stages(monkeypatch, [make_source("src_a")], collect=collect,
                   settings=ScoutSettings(max_items_per_source=7))
    run_mod.main([])
    assert seen["n"] == 7
    run_mod.main(["--max-items", "3"])
    assert seen["n"] == 3


def test_invalid_saved_settings_stop_the_run(monkeypatch, writes, capsys):
    def broken():
        raise settings_store.StoredFileError("settings/scout_settings.json is not valid")

    stages = install_stages(monkeypatch, [make_source("src_a")])
    stages.load_settings = broken
    assert run_mod.main([]) == 1
    assert "settings/scout_settings.json" in capsys.readouterr().err
    assert paths_of(writes, "output/") == []


def discovered_candidate() -> Candidate:
    return Candidate(candidate_id="cccccccccccc", name="Found Site", url="https://found.example/news",
                     domain="found.example", type_guess="trade_news", discovered_via="seed",
                     access_method="rss", feed_url="https://found.example/feed", robots_status="allowed",
                     terms_status="ok", public_ok=True, newest_item_date="2026-10-01", trust_score=88,
                     status="auto_vetted", usable=True)


def test_discovery_adds_a_source_to_the_run(monkeypatch, writes, capsys):
    cand = discovered_candidate()
    stages = install_stages(
        monkeypatch, [make_source("src_a")],
        settings=ScoutSettings(discovery_enabled=True, use_discovered_sources=True),
        discovery=lambda: (lambda *a, **k: [cand], lambda c, gate, settings: c))
    assert run_mod.main([]) == 0
    env = output_of(writes)
    row = next(s for s in env.sources if s.source_id == "disc_cccccccccccc")
    assert row.kind == "discovered" and row.items_collected == 2
    assert [c.candidate_id for c in stages.saved_candidates] == ["cccccccccccc"]
    assert env.candidates_considered == 1
    assert "1 candidate(s) found, 1 vetted, 1 usable" in capsys.readouterr().out
    registered = writes["source_register/sources.json"]
    assert next(s for s in registered if s["source_id"] == "disc_cccccccccccc")["status"] == "proposed"


def test_no_discovery_flag_skips_discovery(monkeypatch, writes):
    called = []
    install_stages(monkeypatch, [make_source("src_a")], settings=ScoutSettings(discovery_enabled=True),
                   discovery=lambda: called.append(1))
    assert run_mod.main(["--no-discovery"]) == 0
    assert called == []


def test_discovery_error_is_logged_and_the_run_continues(monkeypatch, writes):
    install_stages(monkeypatch, [make_source("src_a")], settings=ScoutSettings(discovery_enabled=True))
    code = run_mod.main([])
    assert code == 1  # a logged error is an error
    (log_path,) = paths_of(writes, "logs/")
    assert any("discovery: RuntimeError: discovery not installed" in e for e in writes[log_path]["errors"])
    assert len(output_of(writes).items) == 1  # sources still ran


def test_one_candidate_failing_to_vet_does_not_stop_the_rest(monkeypatch, writes):
    good = discovered_candidate()
    bad = good.model_copy(update={"candidate_id": "dddddddddddd", "domain": "bad.example"})

    def vet(c, gate, settings):
        if c.candidate_id == "dddddddddddd":
            raise ValueError("terms page unreadable")
        return c

    stages = install_stages(monkeypatch, [make_source("src_a")],
                            settings=ScoutSettings(discovery_enabled=True),
                            discovery=lambda: (lambda *a, **k: [bad, good], vet))
    run_mod.main([])
    saved = {c.candidate_id: c for c in stages.saved_candidates}
    assert set(saved) == {"cccccccccccc", "dddddddddddd"}
    assert "terms page unreadable" in saved["dddddddddddd"].notes


def test_stories_group_items_from_different_sources(monkeypatch, writes):
    def extract(page, source):
        return make_item(page, source).model_copy(update={"company": "Acme Compressors", "event_type": "acquisition",
                                                          "title": "Acme acquires Delta Pumps"})

    install_stages(monkeypatch, [make_source("src_a"), make_source("src_b")], pages_per_source=1, extract=extract)
    run_mod.main([])
    env = output_of(writes)
    (story,) = env.stories
    assert sorted(story.source_ids) == ["src_a", "src_b"] and len(story.item_ids) == 2
