"""The one-page summary: computed only from the envelope, simple, safe. Synthetic data, nothing on disk."""
import json
from io import BytesIO
from pathlib import Path

import pytest
from pptx import Presentation

from atlas.models import Item, OutputEnvelope
from atlas.report import onepager as op
from atlas.report.build import PersonalDataError

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output.json"


def envelope(**kw) -> OutputEnvelope:
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    data.update(kw)
    return OutputEnvelope.model_validate(data)


def item(n, company, event="acquisition", fact="Acme acquired Delta for 40 million dollars.", **kw) -> Item:
    base = dict(id=f"i{n:011d}", source_id="s", source_name="Src", source_type="trade_news",
                source_url=f"https://s.example/{n}", licence_note="x", collected_at="2026-10-29T10:00:00Z",
                published_at=f"2026-10-{n:02d}", title=f"{company} news", company=company, event_type=event,
                key_facts=[fact], page_fingerprint=str(n), technology="blowers")
    base.update(kw)
    return Item(**base)


def with_items(items) -> OutputEnvelope:
    e = envelope()
    return e.model_copy(update={"items": items, "stories": []})


def test_sample_builds_both_formats_on_one_page():
    e = envelope()
    pptx = op.build_onepager(e, "pptx")
    assert len(Presentation(BytesIO(pptx)).slides) == 1
    pdf = op.build_onepager(e, "pdf")
    assert pdf.startswith(b"%PDF") and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") >= 1
    assert pdf.count(b"/Type /Pages") >= 1


def test_every_line_comes_from_the_envelope():
    e = envelope()
    page = op.compute(e)
    own = [i for i in e.items if (i.company or "").lower().startswith("atlas copco")]
    assert f"{len(own)} item" in page.difference[0]
    assert f"{len(e.items) - len(own)} item" in page.difference[1]
    shown = {x.url for x in page.look_at + page.facts}
    assert shown <= {i.source_url for i in e.items}


def test_atlas_copco_own_news_is_separated_from_others():
    page = op.compute(with_items([item(1, "Atlas Copco", technology="compressed air"), item(2, "Borealis Air"), item(3, "Cedar Pumps", technology="vacuum pumps")]))
    names = {x.company for x in page.look_at + page.facts}
    assert "Atlas Copco" not in names and {"Borealis Air", "Cedar Pumps"} <= names
    assert "1 item" in page.difference[0] and "2 items" in page.difference[1]
    assert "vacuum pumps" in page.difference[2] and "blowers" in page.difference[2]  # others cover, Atlas Copco does not


def test_priority_order_and_one_entry_per_company():
    items = [item(1, "A", "product_launch"), item(2, "B", "acquisition"), item(3, "B", "acquisition"),
             item(4, "C", "regulation_standard"), item(5, "D", "partnership")]
    look = op.compute(with_items(items)).look_at
    assert [x.company for x in look] == ["B", "D", "C"]  # acquisition, partnership, regulation; B only once


def test_teasers_placeholders_and_vague_text_are_not_facts():
    bad = ["In this article we will discuss the new project for 2026.", "Contact <PERSON> about the 2026 launch.",
           "A very nice company with nice things to say here."]
    page = op.compute(with_items([item(i + 1, f"Co{i}", fact=f) for i, f in enumerate(bad)]))
    assert page.look_at == [] and page.facts == []


def test_title_with_removed_name_placeholder_is_skipped():
    page = op.compute(with_items([item(1, "A", title="A launches <PERSON> series")]))
    assert page.look_at == []


def test_refused_and_scout_sources_are_counted_honestly():
    page = op.compute(envelope())
    text = " ".join(page.sources)
    assert "Refused: 1 site" in text and "not yet approved" in text and "1 found by the scout" in text


def test_empty_run_gives_an_honest_valid_page():
    e = with_items([])
    page = op.compute(e)
    assert page.look_at == [] and page.facts == []
    assert op.build_onepager(e, "pdf").startswith(b"%PDF")
    assert len(Presentation(BytesIO(op.build_onepager(e, "pptx"))).slides) == 1


def test_personal_data_is_refused():
    with pytest.raises(PersonalDataError):
        op.compute(with_items([item(1, "A", fact="Email jo@acme.example about the 2026 launch.")]))


def test_unknown_format_and_label_shown():
    with pytest.raises(ValueError):
        op.build_onepager(envelope(), "docx")
    assert all(x.label in ("fact", "claim") for x in op.compute(envelope()).look_at)


def test_write_onepager_uploads_from_memory_only(monkeypatch, tmp_path):
    from atlas import settings as settings_module, storage
    from types import SimpleNamespace
    monkeypatch.setattr(settings_module, "get_settings", lambda: SimpleNamespace(volume_root="/Volumes/x"))
    monkeypatch.chdir(tmp_path)
    uploaded = {}
    monkeypatch.setattr(storage, "read_json", lambda p: json.loads(SAMPLE.read_text(encoding="utf-8")))
    monkeypatch.setattr(storage, "write_bytes", lambda p, b: uploaded.__setitem__(p, b))
    path = op.write_onepager("20261029T101500Z", "pdf")
    assert list(uploaded) == ["reports/onepager_20261029T101500Z.pdf"] and path.endswith(".pdf")
    assert uploaded["reports/onepager_20261029T101500Z.pdf"].startswith(b"%PDF")
    assert list(tmp_path.iterdir()) == []


def test_words_that_merely_start_like_an_event_verb_do_not_count():
    vague = "They share insights from root cause investigations into equipment reliability."
    assert op.compute(with_items([item(1, "A", fact=vague)])).look_at == []
