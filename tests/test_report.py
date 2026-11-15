"""Tests for atlas/report (sachi2.md S6 to S8). Synthetic envelopes only; no network, no disk.

Fixtures: tests/fixtures/report_envelope.json (Sachi, synthetic) and tests/fixtures/sample_output.json
(Nikhil, pushed on D0; its tests are skipped with a reason until it exists).
"""
import builtins
import json
import re
from io import BytesIO
from pathlib import Path

import matplotlib  # imported before any test patches open(): its font cache is set up here
import pytest
from pptx import Presentation

from atlas.models import Item, OutputEnvelope
from atlas.report import PersonalDataError, build_report, compute, write_report
from atlas.report import build as build_mod
from atlas.report import charts
from atlas.report.build import DISCOVERED_NOTE, PREPARED_FOR
from atlas.report.pptx_builder import expected_slide_count

FIXTURES = Path(__file__).parent / "fixtures"
MINE = FIXTURES / "report_envelope.json"
NIKHIL = FIXTURES / "sample_output.json"
assert matplotlib  # keep the import


def load(path: Path) -> OutputEnvelope:
    return OutputEnvelope.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture
def env() -> OutputEnvelope:
    return load(MINE)


def pptx_text(data: bytes) -> list[str]:
    """All text per slide, notes excluded."""
    prs = Presentation(BytesIO(data))
    out = []
    for slide in prs.slides:
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
            if shape.has_table:
                parts += [c.text for row in shape.table.rows for c in row.cells]
        out.append("\n".join(parts))
    return out


def in_pdf(text: str, pdf: bytes) -> bool:
    """Text as reportlab writes it into an uncompressed page stream (parentheses are escaped)."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("latin-1") in pdf


def pdf_pages(data: bytes) -> int:
    return len(re.findall(rb"/Type /Page[^s]", data))


# ---------- both formats build and reopen ----------

@pytest.mark.parametrize("path", [MINE, NIKHIL], ids=["sachi_fixture", "nikhil_sample_output"])
def test_builds_both_formats(path):
    if not path.exists():
        pytest.skip(f"{path.name} not pushed yet (Nikhil, D0)")
    envelope = load(path)
    pptx = build_report(envelope, "pptx")
    prs = Presentation(BytesIO(pptx))
    assert len(prs.slides) == expected_slide_count(compute(envelope))
    pdf = build_report(envelope, "pdf")
    assert pdf.startswith(b"%PDF")
    assert pdf_pages(pdf) >= 10


def test_slide_count_for_fixture(env):
    # 9 fixed slides + 2 appendix slides (14 items, 12 per slide)
    assert len(Presentation(BytesIO(build_report(env, "pptx"))).slides) == 11


def test_unknown_format_raises(env):
    with pytest.raises(ValueError):
        build_report(env, "docx")  # type: ignore[arg-type]


# ---------- numbers come from the envelope ----------

def test_numbers_equal_envelope_counts(env):
    n_items = len(env.items)
    n_sources = sum(1 for s in env.sources if s.kind != "fallback")
    with_items = sum(1 for s in env.sources if s.items_passed > 0 and s.kind != "fallback")
    refused = sum(1 for s in env.sources if (s.note or "").startswith("refused"))
    fallback = sum(1 for i in env.items if i.via_fallback)
    data = compute(env)
    assert (data.n_items, data.n_sources, data.n_refused, data.n_fallback_items) == (n_items, n_sources, refused, fallback)
    assert data.n_multi_source_stories == 2

    first = f"found {n_items} items that passed the filter, from {with_items} of {n_sources} sources"
    slides = pptx_text(build_report(env, "pptx"))
    assert first in slides[1]
    assert f"{refused} source refused by the compliance gate; {fallback} items from switching" in slides[1]
    pdf = build_report(env, "pdf")
    assert first.encode() in pdf
    assert f"{fallback} items from switching".encode() in pdf


def test_both_formats_show_same_summary(env):
    data = compute(env)
    slide2 = pptx_text(build_report(env, "pptx"))[1]
    pdf = build_report(env, "pdf")
    for sentence in data.summary_sentences:
        assert sentence in slide2
        assert in_pdf(sentence.split(";")[0][:60], pdf)


def test_company_counts(env):
    data = compute(env)
    assert data.by_company[0] == ("Acme Air", 5)
    assert dict(data.by_label) == {"claim": 10, "fact": 4}


def test_ranking_rule(env):
    top = compute(env).top_items
    # the three items of the 3-source story come first, newest first; then the 2-source story
    assert [r.item_id for r in top[:5]] == ["item00000003", "item00000002", "item00000001", "item00000005", "item00000004"]
    assert top[-1].date is not None  # the undated item is not in the top 8


# ---------- compliance content ----------

def test_refused_fallback_and_discovered_are_visible(env):
    slides = "\n".join(pptx_text(build_report(env, "pptx")))
    assert "REFUSED by compliance gate: robots_disallow" in slides
    assert "Refused sources: 1, marked REFUSED in the table" in slides
    assert "Coverage for Delta Compressors Newsroom came from Gamma Canada Industry." in slides
    assert "via switching (for Delta Compressors Newsroom)" in slides
    assert DISCOVERED_NOTE in slides
    pdf = build_report(env, "pdf")
    assert b"Coverage for Delta Compressors Newsroom came from Gamma Canada Industry." in pdf
    assert b"REFUSED" in pdf


def test_prepared_for_statement_on_every_slide(env):
    for text in pptx_text(build_report(env, "pptx")):
        assert PREPARED_FOR in text
    assert PREPARED_FOR.encode() in build_report(env, "pdf")


def test_links_present(env):
    prs = Presentation(BytesIO(build_report(env, "pptx")))
    addresses = set()
    for slide in prs.slides:
        for shape in slide.shapes:
            cells = [c for row in shape.table.rows for c in row.cells] if shape.has_table else []
            frames = [shape.text_frame] if shape.has_text_frame else []
            for tf in frames + [c.text_frame for c in cells]:
                for p in tf.paragraphs:
                    for r in p.runs:
                        if r.hyperlink.address:
                            addresses.add(r.hyperlink.address)
    assert {i.source_url for i in env.items} <= addresses
    pdf = build_report(env, "pdf")
    assert all(f"/URI ({i.source_url})".encode() in pdf for i in env.items)


def test_speaker_notes_on_slides_2_to_8(env):
    prs = Presentation(BytesIO(build_report(env, "pptx")))
    for idx in range(1, 8):
        assert "output/poc_" in prs.slides[idx].notes_slide.notes_text_frame.text


def test_only_stored_key_facts_no_other_text(env):
    data = compute(env)
    assert all(len(f) <= 200 for r in data.all_items for f in r.key_facts)


# ---------- empty and small envelopes ----------

def test_empty_envelope_gives_honest_report(env):
    empty = env.model_copy(update={"items": [], "stories": []})
    slides = pptx_text(build_report(empty, "pptx"))
    assert len(slides) == 10
    assert "No items passed the filter in run" in slides[1]
    assert "No items passed the filter in this run." in slides[-1]
    pdf = build_report(empty, "pdf")
    assert pdf.startswith(b"%PDF") and b"No items passed the filter" in pdf


def test_single_item_envelope_shows_sentence_not_chart(env):
    one = env.model_copy(update={"items": env.items[:1], "stories": []})
    slides = pptx_text(build_report(one, "pptx"))
    assert "Only one company in this run: Acme Air (1 item). No chart is drawn." in slides[4]
    assert build_report(one, "pdf").startswith(b"%PDF")


def test_chart_needs_two_points():
    assert charts.bar_chart([("A", 3)], "t") is None
    png = charts.bar_chart([("A", 3), ("B", 1)], "t")
    assert png is not None and png.startswith(b"\x89PNG")


# ---------- personal data guard ----------

@pytest.mark.parametrize("field,value", [
    ("title", "Contact jane.doe@acme-example.com for details"),
    ("key_facts", ["Call 555-123-4567 to order the unit."]),
    ("key_facts", ["Sales line +44 20 7946 0958 opens Monday."]),
])
def test_pii_like_string_raises(env, field, value):
    bad: Item = env.items[0].model_copy(update={field: value})
    envelope = env.model_copy(update={"items": [bad] + env.items[1:]})
    with pytest.raises(PersonalDataError):
        build_report(envelope, "pdf")


def test_numbers_and_codes_are_not_mistaken_for_phones(env):
    item = env.items[0].model_copy(update={"key_facts": ["Rated 500 cfm at 125 psi, 2026-10-29, model OFE1550."]})
    envelope = env.model_copy(update={"items": [item]})
    assert build_report(envelope, "pptx")


# ---------- nothing touches local disk ----------

def test_no_file_written(env, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    real_open = builtins.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(m in mode for m in ("w", "a", "x", "+")):
            raise AssertionError(f"report tried to write a file: {file}")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    assert build_report(env, "pptx")
    assert build_report(env, "pdf")
    assert list(tmp_path.iterdir()) == []


# ---------- write_report goes through atlas.storage ----------

def test_write_report_uses_storage(env, monkeypatch):
    from atlas import storage

    uploads: dict[str, bytes] = {}
    reads: list[str] = []

    def fake_read_json(path):
        reads.append(path)
        return env.model_dump(mode="json")

    monkeypatch.setattr(storage, "read_json", fake_read_json)
    monkeypatch.setattr(storage, "write_bytes", lambda path, data: uploads.__setitem__(path, data), raising=False)
    monkeypatch.setattr(build_mod, "_volume_path", lambda rel: f"/Volumes/atlas_poc/default/data/dev/sachi/{rel}")

    path = write_report(env.run_id, "pdf")
    assert reads == [f"output/poc_{env.run_id}.json"]
    assert list(uploads) == [f"reports/report_{env.run_id}.pdf"]
    assert uploads[f"reports/report_{env.run_id}.pdf"].startswith(b"%PDF")
    assert path == f"/Volumes/atlas_poc/default/data/dev/sachi/reports/report_{env.run_id}.pdf"

    write_report(env.run_id, "pptx")
    assert f"reports/report_{env.run_id}.pptx" in uploads


def test_phase1_style_envelope_without_phase2_fields(env):
    """An envelope from before Phase 2 (no stories, no saved settings, no region/event/product) still
    builds, and the report says default settings were used instead of inventing a window."""
    plain_items = [i.model_copy(update={"region": None, "event_type": None, "product": None, "story_id": None,
                                        "via_fallback": False, "fallback_for": None}) for i in env.items]
    plain_sources = [s.model_copy(update={"kind": "registered", "fallback_for": None}) for s in env.sources]
    old = env.model_copy(update={"items": plain_items, "sources": plain_sources, "stories": [],
                                 "settings_used": None, "candidates_considered": 0})
    data = compute(old)
    assert "Settings: default settings (no saved settings in this run)" in data.scope_lines
    assert data.n_multi_source_stories == 0 and data.switching == []
    slides = pptx_text(build_report(old, "pptx"))
    assert "No story was seen in two or more independent sources in this run." in slides[6]
    assert "No switching was needed in this run." in slides[7]
    assert build_report(old, "pdf").startswith(b"%PDF")


def test_real_run_wording(env):
    """From the 15 Nov live run: a switching row is not a source, "other" is not a type of news, and a
    switch that found nothing is reported, not hidden."""
    fb = [s for s in env.sources if s.kind == "fallback"][0]
    tried = fb.model_copy(update={"items_passed": 0})
    sources = [tried if s.kind == "fallback" else s for s in env.sources]
    items = [i.model_copy(update={"via_fallback": False, "fallback_for": None,
                                  "event_type": "other" if n < 9 else i.event_type}) for n, i in enumerate(env.items)]
    data = compute(env.model_copy(update={"sources": sources, "items": items}))
    assert data.n_sources == len(env.sources) - 1
    general = sum(1 for i in items if i.event_type == "other")
    assert any(s.startswith(f"Apart from {general} general articles, the most common type of news is")
               for s in data.summary_sentences)
    slides = "\n".join(pptx_text(build_report(env.model_copy(update={"sources": sources, "items": items}), "pptx")))
    assert "Switching was tried for Delta Compressors Newsroom: no items about it were found" in slides
    assert "No switching was needed in this run." not in slides
