from datetime import date

import pytest

from atlas.models import Candidate, CandidateDecision, ScoutSettings, Source
from atlas.scout import settings_store as ss


@pytest.fixture
def volume(monkeypatch):
    """In-memory stand-in for the Volume: nothing reaches Databricks or disk."""
    files: dict = {}
    monkeypatch.setattr(ss.storage, "read_json_or_none", lambda path: files.get(path))
    monkeypatch.setattr(ss.storage, "write_json", lambda path, obj: files.__setitem__(path, obj))
    return files


def cand(cid="aaaaaaaaaaaa", domain="newsite.example", **kw) -> Candidate:
    base = dict(
        candidate_id=cid, name="New Site", url=f"https://{domain}/news", domain=domain, type_guess="trade_news",
        discovered_via="seed", access_method="rss", feed_url=f"https://{domain}/feed", robots_status="allowed",
        terms_status="ok", public_ok=True, newest_item_date="2026-10-01", trust_score=85, status="auto_vetted",
        usable=True,
    )
    base.update(kw)
    return Candidate(**base)


def register_source(url="https://old.example/news") -> Source:
    return Source(source_id="old", name="Old", url=url, type="competitor", access_method="rss",
                  robots_status="allowed", terms_status="ok", vetting_status="working", review_date=date(2026, 10, 1))


ON = ScoutSettings(use_discovered_sources=True)


def test_default_settings_are_the_phase_2_defaults():
    s = ss.default_settings()
    assert s.regions == ["US", "CA"] and s.recent_months == 12 and s.require_industrial is False
    assert s.use_discovered_sources is False and s.discovery_enabled is False
    assert {w.name for w in s.watchlist} >= {"Ingersoll Rand", "Sullair"}


def test_load_returns_defaults_when_nothing_saved(volume):
    assert ss.load_settings() == ss.default_settings()


def test_save_then_load_round_trip(volume):
    saved = ScoutSettings(regions=["US", "CA"], recent_months=6, excluded_keywords=["lawsuit"])
    ss.save_settings(saved)
    assert "settings/scout_settings.json" in volume
    assert ss.load_settings() == saved


def test_invalid_saved_file_raises_naming_the_file(volume):
    volume["settings/scout_settings.json"] = {"recent_months": 999}
    with pytest.raises(ss.StoredFileError, match="settings/scout_settings.json"):
        ss.load_settings()  # never silently replaced by defaults


def test_invalid_settings_cannot_be_saved(volume):
    bad = ScoutSettings()
    bad.recent_months = 999  # pydantic does not validate assignment
    with pytest.raises(Exception):
        ss.save_settings(bad)
    assert volume == {}


def test_candidates_round_trip_and_empty(volume):
    assert ss.load_candidates() == []
    ss.save_candidates([cand()])
    assert ss.load_candidates() == [cand()]


def test_corrupt_candidates_file_raises(volume):
    volume["scout/candidates.json"] = [{"candidate_id": "x"}]
    with pytest.raises(ss.StoredFileError, match="candidates.json"):
        ss.load_candidates()


def test_save_decision_replaces_earlier_decision_for_same_candidate(volume):
    ss.save_decision(CandidateDecision(candidate_id="a", decision="accepted", decided_by="Parth"))
    ss.save_decision(CandidateDecision(candidate_id="b", decision="accepted", decided_by="Parth"))
    ss.save_decision(CandidateDecision(candidate_id="a", decision="rejected", decided_by="Ragini", note="paywall"))
    decisions = {d.candidate_id: d for d in ss.load_decisions()}
    assert len(decisions) == 2
    assert decisions["a"].decision == "rejected" and decisions["a"].decided_by == "Ragini"


# ---- usable_sources ----

def test_usable_source_is_converted_and_never_approved():
    (src,) = ss.usable_sources(ON, [cand()], [])
    assert src.origin == "discovered" and src.status == "proposed" and src.vetting_status == "working"
    assert src.trust_score == 85 and src.source_id == "disc_aaaaaaaaaaaa" and src.feed_url
    assert "Not approved by Atlas Copco" in src.notes


def test_discovered_sources_off_by_default():
    assert ss.usable_sources(ScoutSettings(), [cand()], []) == []


@pytest.mark.parametrize("override", [
    {"usable": False}, {"trust_score": 69}, {"type_guess": "government"},
])
def test_ineligible_candidates_are_excluded(override):
    settings = ScoutSettings(use_discovered_sources=True, source_types=["trade_news"])
    assert ss.usable_sources(settings, [cand(**override)], []) == []


def test_rejected_decision_excludes():
    d = CandidateDecision(candidate_id="aaaaaaaaaaaa", decision="rejected", decided_by="Parth")
    assert ss.usable_sources(ON, [cand()], [d]) == []


def test_accepted_decision_cannot_make_an_unusable_candidate_usable():
    d = CandidateDecision(candidate_id="aaaaaaaaaaaa", decision="accepted", decided_by="Parth")
    assert ss.usable_sources(ON, [cand(usable=False, terms_status="unknown")], [d]) == []


def test_trust_threshold_is_from_settings():
    settings = ScoutSettings(use_discovered_sources=True, min_trust_score=90)
    assert ss.usable_sources(settings, [cand(trust_score=85)], []) == []
    assert len(ss.usable_sources(ScoutSettings(use_discovered_sources=True, min_trust_score=80), [cand()], [])) == 1


def test_site_already_in_register_is_skipped():
    reg = [register_source("https://www.newsite.example/press")]
    assert ss.usable_sources(ON, [cand()], [], reg) == []
    assert len(ss.usable_sources(ON, [cand()], [], [register_source()])) == 1


def test_duplicate_candidate_ids_produce_one_source():
    assert len(ss.usable_sources(ON, [cand(), cand()], [])) == 1
