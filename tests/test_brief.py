"""The brief: facts, sources, why it matters. No Atlas Copco's own news. Synthetic data, nothing on disk."""
import json
from io import BytesIO
from pathlib import Path

import pytest
from pptx import Presentation

from atlas.models import OutputEnvelope
from atlas.report import brief as br

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output.json"


def env() -> OutputEnvelope:
    return OutputEnvelope.model_validate(json.loads(SAMPLE.read_text(encoding="utf-8")))


def test_builds_one_slide_and_a_pdf():
    e = env()
    assert len(Presentation(BytesIO(br.build_brief(e, "pptx"))).slides) == 1
    assert br.build_brief(e, "pdf").startswith(b"%PDF")


def test_atlas_copco_own_news_is_never_in_the_brief():
    e = env()
    own = e.items[0].model_copy(update={"company": "Atlas Copco", "id": "own000000001"})
    e = e.model_copy(update={"items": [own, *e.items]})
    assert "Atlas Copco" not in {r.company for r in br.compute(e).rows}


def test_each_row_has_fact_source_link_and_why():
    rows = br.compute(env()).rows
    assert rows
    for r in rows:
        assert r.fact and r.source and r.url.startswith("http") and r.why


def test_denied_facts_are_dropped_and_approved_come_first():
    e = env()
    base = br.compute(e).rows
    victim, favourite = base[0], base[-1]
    ids = {i.source_url: i.id for i in e.items}
    d = {ids[victim.url]: "denied", ids[favourite.url]: "approved"}
    rows = br.compute(e, d).rows
    assert victim.url not in {r.url for r in rows}
    assert rows[0].url == favourite.url and rows[0].approved


def test_confirmed_and_unconfirmed_sources_are_marked():
    e = env()
    first = next(s for s in e.sources if s.items_passed > 0 and s.kind != "fallback")
    text = " ".join(br.compute(e, None, {first.source_id: "confirmed"}).sources)
    assert f"{first.name}: {first.items_passed} item(s) (confirmed)" in text and "not yet confirmed" in text


def test_why_it_matters_is_a_fixed_sentence_per_event_type():
    assert set(br.WHY) >= {"acquisition", "partnership", "investment_expansion", "regulation_standard", "product_launch"}
    rows = br.compute(env()).rows
    assert all(any(r.why.startswith(t) for t in [*br.WHY.values(), br.WHY_OTHER]) for r in rows)


def test_empty_run_is_valid_and_honest():
    e = env().model_copy(update={"items": [], "stories": []})
    assert br.compute(e).rows == []
    assert len(Presentation(BytesIO(br.build_brief(e, "pptx"))).slides) == 1
    assert br.build_brief(e, "pdf").startswith(b"%PDF")


def test_unknown_format_and_write_uploads_from_memory(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from atlas import review, settings as settings_module, storage
    with pytest.raises(ValueError):
        br.build_brief(env(), "docx")
    monkeypatch.setattr(settings_module, "get_settings", lambda: SimpleNamespace(volume_root="/Volumes/x"))
    monkeypatch.setattr(storage, "read_json", lambda p: json.loads(SAMPLE.read_text(encoding="utf-8")))
    monkeypatch.setattr(review, "load_fact_decisions", lambda: {})
    monkeypatch.setattr(review, "load_source_confirmations", lambda: {})
    up = {}
    monkeypatch.setattr(storage, "write_bytes", lambda p, b: up.__setitem__(p, b))
    monkeypatch.chdir(tmp_path)
    assert br.write_brief("RID", "pdf").endswith("reports/brief_RID.pdf")
    assert up["reports/brief_RID.pdf"].startswith(b"%PDF") and list(tmp_path.iterdir()) == []
