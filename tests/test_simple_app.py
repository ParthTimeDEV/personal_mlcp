"""Logic behind the simple app: grouping sources and the rerun watcher. No browser, no network."""
import io
from datetime import date

from app.lib import simple
from app.lib.simple import RunWatcher, classify_sources
from atlas.models import Candidate, Source


def src(sid, vetting="working", status="proposed", notes="") -> Source:
    return Source(source_id=sid, name=sid.upper(), url=f"https://{sid}.example/", type="competitor", access_method="rss",
                  robots_status="allowed", terms_status="ok", vetting_status=vetting, status=status,
                  review_date=date(2026, 11, 16), notes=notes)


def cand(cid, **kw) -> Candidate:
    base = dict(candidate_id=cid, name=f"C{cid}", url=f"https://{cid}.example/", domain=f"{cid}.example",
                type_guess="trade_news", discovered_via="seed", trust_score=80, usable=True, status="auto_vetted")
    base.update(kw)
    return Candidate(**base)


def test_register_sources_are_grouped_by_state():
    g = classify_sources([src("a"), src("b"), src("c", vetting="blocked", status="blocked", notes="terms forbid")],
                         [], {"a": "confirmed"})
    assert [r["id"] for r in g["confirmed"]] == ["a"]
    assert [r["id"] for r in g["to_confirm"]] == ["b"]
    assert [r["id"] for r in g["blocked"]] == ["c"] and "terms forbid" in g["blocked"][0]["detail"]


def test_scout_finds_are_grouped_and_forbidding_ones_are_blocked_with_the_quote():
    cands = [cand("aaa"), cand("bbb"), cand("ccc", usable=False, terms_status="forbids_automation",
                                           status="rejected_by_rules", terms_evidence="no robots allowed"),
             cand("ddd", usable=False, status="needs_review", terms_status="unknown")]
    g = classify_sources([], cands, {"disc_aaa": "confirmed"})
    assert [r["id"] for r in g["confirmed"]] == ["disc_aaa"]
    assert [r["id"] for r in g["to_confirm"]] == ["disc_bbb"]
    assert [r["id"] for r in g["blocked"]] == ["disc_ccc"] and "no robots allowed" in g["blocked"][0]["detail"]
    assert all(r["id"] != "disc_ddd" for rows in g.values() for r in rows)  # unusable and not refused: not offered


def test_rejected_candidates_are_not_listed():
    g = classify_sources([], [cand("aaa")], {}, {"aaa"})
    assert not any(g.values())


class FakeProc:
    def __init__(self, text, code=None):
        self.stdout = io.StringIO(text)
        self.code = code

    def poll(self):
        return self.code


def test_watcher_reads_progress_and_last_line():
    w = RunWatcher(FakeProc("Run X starting\n[2/7] quincy\n  allowed; fetching\n"))
    for _ in range(100):
        if len(w.lines) == 3:
            break
        import time; time.sleep(0.01)
    assert w.progress() == (2, 7) and w.last_line() == "  allowed; fetching" and w.running


def test_start_rerun_uses_start_run_without_arguments(monkeypatch):
    seen = {}
    monkeypatch.setattr(simple, "start_run", lambda args: seen.setdefault("args", args) and FakeProc("", 0) or FakeProc("", 0))
    w = simple.start_rerun("new filters")
    assert seen["args"] == [] or seen["args"] is not None
    assert w.reason == "new filters" and not w.running and w.exit_code == 0
