"""One-page summary (PPTX or PDF): facts, sources, difference from Atlas Copco, what to look at.

Owner: Nikhil. Deliberately simple: one slide or one page, four boxes, every line computed from the run's
`OutputEnvelope` (no invented numbers or text, no AI). The full multi-page report stays in
`atlas.report.build`; this is the glance version.

  Box 1  Look at first      the 3 highest-priority events by other companies (acquisition, partnership,
                            expansion, regulation, product launch), one per company, with source links
  Box 2  Other facts        the 4 newest remaining facts, with source
  Box 3  Difference from Atlas Copco   its own news vs everyone else's, and topics others cover where
                            Atlas Copco has no item in this run
  Box 4  Sources            how many were read, how many refused, which are not yet approved

"Atlas Copco's own news" = items whose company is Atlas Copco. Facts come from `Item.key_facts`; a fact or
title containing a removed-name placeholder such as <PERSON> is never shown. Nothing is written to disk.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from typing import Literal, Optional
from xml.sax.saxutils import escape, quoteattr

from atlas.models import Item, OutputEnvelope
from atlas.report.build import EVENT_LABELS, PREPARED_FOR, check_personal_data, truncate

ATLAS_COPCO = "atlas copco"
LOOK_AT_COUNT = 3
FACT_COUNT = 3
FACT_CHARS = 140
PRIORITY = ["acquisition", "partnership", "investment_expansion", "regulation_standard", "product_launch"]
MIN_FACT_CHARS = 25


@dataclass
class Entry:
    company: str
    event: str
    date: str
    fact: str
    label: str
    source: str
    url: str


@dataclass
class OnePager:
    run_id: str
    run_date: str
    scope: str
    look_at: list[Entry] = field(default_factory=list)
    facts: list[Entry] = field(default_factory=list)
    difference: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    footer: str = PREPARED_FOR


def _is_own(item: Item) -> bool:
    return (item.company or "").casefold().startswith(ATLAS_COPCO)


def _clean(text: Optional[str]) -> bool:
    return bool(text) and "<" not in text and ">" not in text


# A fact needs something concrete: a number, or a verb that says something happened.
CONCRETE = re.compile(
    r"\d|\b(acquir\w*|launch\w*|announc\w*|introduc\w*|unveil\w*|open\w*|expand\w*|invest(?:s|ed|ing|ment|ments)|"
    r"partner\w*|appoint\w*|name[sd]|won|wins|award\w*|release\w*|complet\w*|begin\w*|start\w*|"
    r"deliver\w*|signed|agree\w*)\b", re.IGNORECASE)
# Blog teasers and marketing lead-ins are not facts.
TEASER = re.compile(
    r"\b(in this article|this article|we will|we'll|you will|you'll|learn how|find out|discover|explore|"
    r"our customer|read on|in this context|take a look|closer look|how the)\b", re.IGNORECASE)


def _fact(item: Item) -> Optional[str]:
    for fact in item.key_facts:
        if (_clean(fact) and len(fact.strip()) >= MIN_FACT_CHARS and CONCRETE.search(fact)
                and not TEASER.search(fact)):
            return truncate(fact, FACT_CHARS)
    return None


def _entry(item: Item) -> Optional[Entry]:
    fact = _fact(item)
    if not (item.company and fact and _clean(item.title) and _clean(item.company)):
        return None
    return Entry(
        company=item.company, event=EVENT_LABELS.get(item.event_type or "", "news"),
        date=item.published_at or "date not stated", fact=fact, label=item.label, source=item.source_name, url=item.source_url,
    )


def _newest_first(items: list[Item]) -> list[Item]:
    return sorted(items, key=lambda i: i.published_at or "", reverse=True)


def _plural(n: int, one: str, many: Optional[str] = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def compute(envelope: OutputEnvelope) -> OnePager:
    """Everything the page says, computed from the envelope. Both formats render this and nothing else."""
    check_personal_data(envelope)
    own = [i for i in envelope.items if _is_own(i)]
    others = [i for i in envelope.items if not _is_own(i)]

    used: set[str] = set()
    look_at: list[Entry] = []
    for event in PRIORITY:
        for item in _newest_first([i for i in others if i.event_type == event]):
            entry = _entry(item)
            if entry and item.company not in used:
                used.add(item.company)
                look_at.append(entry)
            if len(look_at) == LOOK_AT_COUNT:
                break
        if len(look_at) == LOOK_AT_COUNT:
            break

    facts: list[Entry] = []
    for item in _newest_first([i for i in others if i.event_type != "other"] +
                              [i for i in others if i.event_type == "other"]):
        entry = _entry(item)
        if entry and item.company not in used:
            used.add(item.company)
            facts.append(entry)
        if len(facts) == FACT_COUNT:
            break

    own_tech = {i.technology for i in own if i.technology}
    gaps = Counter(i.technology for i in others if i.technology and i.technology not in own_tech)
    events = Counter(i.event_type for i in others if i.event_type and i.event_type != "other")
    difference = [
        f"Atlas Copco's own news in this run: {_plural(len(own), 'item')}.",
        f"News about other companies: {_plural(len(others), 'item')}.",
    ]
    if gaps:
        difference.append("Topics others cover where Atlas Copco has no item: " +
                          ", ".join(f"{t} ({n})" for t, n in gaps.most_common(3)) + ".")
    else:
        difference.append("No topic is covered by others that Atlas Copco has no item on.")
    if events:
        difference.append("Most common events at other companies: " +
                          ", ".join(f"{EVENT_LABELS.get(e, e)} ({n})" for e, n in events.most_common(3)) + ".")

    real = [s for s in envelope.sources if s.kind != "fallback"]
    read = [s for s in real if s.items_collected > 0]
    refused = [s for s in real if s.items_collected == 0 and s.status != "working" or
               (s.note or "").startswith("refused")]
    scout_found = [s for s in read if s.kind == "discovered"]
    sources = [
        f"Read: {_plural(len(read), 'source')} ({len(read) - len(scout_found)} from our list, "
        f"{len(scout_found)} found by the scout).",
        f"Refused: {_plural(len(refused), 'site')} blocked or forbade automated reading. We did not read them.",
    ]
    if read:
        sources.append("Names: " + truncate(", ".join(s.name for s in read), 150))
    if scout_found:
        sources.append("Scout-found sources are not yet approved by Atlas Copco.")
    else:
        sources.append("The source list is proposed, pending approval by Atlas Copco.")

    return OnePager(
        run_id=envelope.run_id, run_date=envelope.generated_at[:10],
        scope=f"{envelope.scope.technology}, {envelope.scope.region}",
        look_at=look_at, facts=facts, difference=difference, sources=sources,
    )


# ---------- PPTX ----------

def _pptx(page: OnePager) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Inches, Pt

    dark, grey, accent = RGBColor(0x22, 0x22, 0x22), RGBColor(0x66, 0x66, 0x66), RGBColor(0x00, 0x72, 0xB2)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    def box(left, top, width, height):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.TOP
        return tf

    def para(tf, first, text, size, bold=False, color=dark, space=3):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        p.space_after = Pt(space)
        run = p.add_run()
        run.text, run.font.size, run.font.bold, run.font.color.rgb = text, Pt(size), bold, color
        return p

    tf = box(0.5, 0.3, 12.3, 1.0)
    para(tf, True, "Compressor market: what to look at", 28, True)
    para(tf, False, f"Run {page.run_id} · {page.run_date} · {page.scope}", 12, color=grey)

    def entries(tf, rows, empty):
        if not rows:
            para(tf, False, empty, 12, color=grey)
        for e in rows:
            p = para(tf, False, f"{e.company} · {e.event} · {e.date} · {e.label}", 12, True, space=0)
            r = p.add_run()
            r.text, r.font.size, r.font.color.rgb = " · ", Pt(11), grey
            r = p.add_run()
            r.text, r.font.size, r.font.color.rgb, r.font.underline = e.source, Pt(11), accent, True
            r.hyperlink.address = e.url
            para(tf, False, e.fact, 11, space=7)

    def lines(tf, rows):
        for row in rows:
            para(tf, False, "• " + row, 12, space=6)

    boxes = [
        (0.5, 1.45, "1  Look at first", lambda t: entries(t, page.look_at, "No acquisition, partnership, expansion, regulation or launch found.")),
        (6.9, 1.45, "2  Other facts", lambda t: entries(t, page.facts, "No further facts passed the filter.")),
        (0.5, 4.3, "3  Difference from Atlas Copco", lambda t: lines(t, page.difference)),
        (6.9, 4.3, "4  Sources", lambda t: lines(t, page.sources)),
    ]
    for left, top, header, fill in boxes:
        frame = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(5.95), Inches(2.7))
        frame.fill.background()
        frame.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
        tf = box(left + 0.12, top + 0.05, 5.7, 2.6)
        para(tf, True, header, 14, True, accent, space=5)
        fill(tf)

    tf = box(0.5, 7.07, 12.3, 0.3)
    para(tf, True, page.footer, 9, color=grey)
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


# ---------- PDF ----------

def _pdf(page: OnePager) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    accent = colors.HexColor("#0072B2")
    base = ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=11.5, spaceAfter=3)
    head = ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=11, textColor=accent, spaceAfter=5)
    bold = ParagraphStyle("bo", parent=base, fontName="Helvetica-Bold", spaceAfter=0)
    title = ParagraphStyle("t", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=2)
    small = ParagraphStyle("s", parent=base, fontSize=8, textColor=colors.HexColor("#666666"))

    def entries(rows, empty):
        out = [Paragraph(escape(empty), base)] if not rows else []
        for e in rows:
            out.append(Paragraph(
                f"{escape(e.company)} · {escape(e.event)} · {escape(e.date)} · {escape(e.label)} · "
                f"<link href={quoteattr(e.url)} color=\"#0072B2\"><u>{escape(e.source)}</u></link>", bold))
            out.append(Paragraph(escape(e.fact), base))
        return out

    def lines(rows):
        return [Paragraph("• " + escape(r), base) for r in rows]

    def cell(header, content):
        return [Paragraph(header, head), *content]

    grid = Table([
        [cell("1  Look at first", entries(page.look_at, "No acquisition, partnership, expansion, regulation or launch found.")),
         cell("2  Other facts", entries(page.facts, "No further facts passed the filter."))],
        [cell("3  Difference from Atlas Copco", lines(page.difference)), cell("4  Sources", lines(page.sources))],
    ], colWidths=[13.4 * cm, 13.4 * cm], rowHeights=[8.3 * cm, 6.2 * cm])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    out = BytesIO()
    SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                      topMargin=1.1 * cm, bottomMargin=1.0 * cm, title="Compressor market: what to look at").build([
        Paragraph("Compressor market: what to look at", title),
        Paragraph(escape(f"Run {page.run_id} · {page.run_date} · {page.scope}"), small),
        Spacer(1, 6), grid, Spacer(1, 4), Paragraph(escape(page.footer), small),
    ])
    return out.getvalue()


# ---------- entry points ----------

def build_onepager(envelope: OutputEnvelope, fmt: Literal["pptx", "pdf"]) -> bytes:
    if fmt not in ("pptx", "pdf"):
        raise ValueError(f"unknown format: {fmt!r} (use 'pptx' or 'pdf')")
    page = compute(envelope)
    return _pptx(page) if fmt == "pptx" else _pdf(page)


def onepager_path(run_id: str, fmt: str) -> str:
    return f"reports/onepager_{run_id}.{fmt}"


def write_onepager(run_id: str, fmt: Literal["pptx", "pdf"]) -> str:
    """Read output/poc_<run_id>.json, build the one-pager, upload it to reports/, return the Volume path."""
    from atlas import storage
    from atlas.settings import get_settings

    envelope = OutputEnvelope.model_validate(storage.read_json(f"output/poc_{run_id}.json"))
    relative = onepager_path(run_id, fmt)
    storage.write_bytes(relative, build_onepager(envelope, fmt))
    return f"{get_settings().volume_root}/{relative}"
