"""PPTX report builder (python-pptx), 16:9, one plain layout (sachi2.md S7, S8).

Owner: Sachi. Builds the deck in memory from `ReportData` and returns bytes. No Atlas Copco logo or
branding. Long text is wrapped and cut with an ellipsis so it never runs out of its box; links in the
appendix keep their full text. Speaker notes on slides 2 to 8 say where each number comes from.
"""
from __future__ import annotations

from io import BytesIO
from math import ceil
from typing import Optional, Sequence, Union

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from atlas.report import charts
from atlas.report.build import (
    APPENDIX_ROWS_PER_SLIDE, DISCOVERED_NOTE, HOW_TO_READ, METHOD_LINES, PREPARED_FOR, SECTION_TITLES,
    TOP_COMPANIES, ReportData, compliance_lines, item_line, note_text, truncate,
)

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.5)
BODY_TOP = Inches(1.25)
BODY_W = SLIDE_W - 2 * MARGIN
BODY_H = Inches(5.55)
SOURCE_ROWS_PER_SLIDE = 12

DARK = RGBColor(0x22, 0x22, 0x22)
GREY = RGBColor(0x66, 0x66, 0x66)
ACCENT = RGBColor(0x00, 0x72, 0xB2)
HEADER_FILL = RGBColor(0xE8, 0xE8, 0xE8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

Cell = Union[str, tuple[str, Optional[str]]]  # text, or (text, url)


# ---------- low-level helpers ----------

def _new_slide(prs, title: str, number: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    box = slide.shapes.add_textbox(MARGIN, Inches(0.35), BODY_W, Inches(0.75))
    tf = box.text_frame
    tf.word_wrap = True
    run = tf.paragraphs[0].add_run()
    run.text = truncate(title, 70)
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = DARK
    line = slide.shapes.add_shape(1, MARGIN, Inches(1.08), Inches(1.2), Emu(38100))  # 1 = rectangle
    line.fill.solid()
    line.fill.fore_color.rgb = ACCENT
    line.line.fill.background()
    footer = slide.shapes.add_textbox(MARGIN, Inches(7.0), BODY_W, Inches(0.35))
    ftf = footer.text_frame
    ftf.word_wrap = True
    p = ftf.paragraphs[0]
    r = p.add_run()
    r.text = f"{PREPARED_FOR}    {number}"
    r.font.size = Pt(9)
    r.font.color.rgb = GREY
    return slide


def _paragraphs(slide, left, top, width, height, lines: Sequence[Union[str, tuple]], size: int = 16,
                bullets: bool = False, max_chars: int = 400) -> None:
    """Lines are text, or (text, url) for a link, or ('', None) for a blank line."""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    first = True
    for line in lines:
        text, url = (line if isinstance(line, tuple) else (line, None))
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = (("• " if bullets and text else "") + truncate(text, max_chars))
        run.font.size = Pt(size)
        run.font.color.rgb = DARK
        if url:
            run.hyperlink.address = url
            run.font.color.rgb = ACCENT


def _table(slide, left, top, col_widths: Sequence[float], header: Sequence[str], rows: Sequence[Sequence[Cell]],
           limits: Sequence[int], size: int = 10, row_h: float = 0.36) -> None:
    n_rows = len(rows) + 1
    shape = slide.shapes.add_table(n_rows, len(header), left, top, Inches(sum(col_widths)), Inches(row_h * n_rows))
    table = shape.table
    for i, w in enumerate(col_widths):
        table.columns[i].width = Inches(w)
    for r in range(n_rows):
        table.rows[r].height = Inches(row_h)
    for c, text in enumerate(header):
        _cell(table.cell(0, c), text, None, size, bold=True, fill=HEADER_FILL)
    for r, row in enumerate(rows, start=1):
        for c, value in enumerate(row):
            text, url = (value if isinstance(value, tuple) else (value, None))
            limit = limits[c]
            _cell(table.cell(r, c), text if limit <= 0 else truncate(text, limit), url, size, fill=WHITE)


def _cell(cell, text: str, url: Optional[str], size: int, bold: bool = False, fill: RGBColor = WHITE) -> None:
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.margin_left = cell.margin_right = Inches(0.05)
    cell.margin_top = cell.margin_bottom = Inches(0.02)
    tf = cell.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = ACCENT if url else DARK
    if url:
        run.hyperlink.address = url


def _picture_or_sentence(slide, png: Optional[bytes], sentence: str, left, top, width, height) -> None:
    if png:
        slide.shapes.add_picture(BytesIO(png), left, top, width=width)
    else:
        _paragraphs(slide, left, top, width, height, [sentence], size=14)


def _notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def _kind_text(kind: str) -> str:
    return DISCOVERED_NOTE if kind == "discovered" else kind


# ---------- slide count ----------

def appendix_slides(n_items: int) -> int:
    return max(1, ceil(n_items / APPENDIX_ROWS_PER_SLIDE))


def source_slides(n_sources: int) -> int:
    return max(1, ceil(n_sources / SOURCE_ROWS_PER_SLIDE))


def expected_slide_count(data: ReportData) -> int:
    """9 fixed slides (sources may continue on more slides) plus the appendix."""
    return 8 + source_slides(len(data.sources)) + appendix_slides(len(data.all_items))


# ---------- the deck ----------

def build_pptx(data: ReportData) -> bytes:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    n = 0

    def slide(title: str):
        nonlocal n
        n += 1
        return _new_slide(prs, title, n)

    # 1. title
    s = slide(SECTION_TITLES["title"])
    _paragraphs(s, MARGIN, Inches(2.2), BODY_W, Inches(3.5), [
        "Run report",
        f"Run id: {data.run_id}",
        f"Run date: {data.run_date}",
        "",
        PREPARED_FOR,
    ], size=22)

    # 2. executive summary
    s = slide(SECTION_TITLES["summary"])
    _paragraphs(s, MARGIN, BODY_TOP, BODY_W, Inches(2.7), data.summary_sentences, size=16, bullets=True)
    if data.headline_items:
        lines: list = ["Headline items:"]
        for row in data.headline_items:
            lines.append((truncate(row.title, 110), row.url))
            lines.append(truncate(item_line(row), 150))
        _paragraphs(s, MARGIN, Inches(4.05), BODY_W, Inches(2.8), lines, size=13)
    _notes(s, data.notes["summary"])

    # 3. scope and method
    s = slide(SECTION_TITLES["scope"])
    _paragraphs(s, MARGIN, BODY_TOP, BODY_W, Inches(3.2), data.scope_lines, size=16, bullets=True)
    _paragraphs(s, MARGIN, Inches(4.6), BODY_W, Inches(2.2), METHOD_LINES, size=14, bullets=True)
    _notes(s, data.notes["scope"])

    # 4. what we found
    s = slide(SECTION_TITLES["found"])
    if data.top_items:
        rows = [
            [str(i), (r.title, r.url), r.company, r.event_type, r.date_text, r.label, r.marker or "-"]
            for i, r in enumerate(data.top_items, start=1)
        ]
        _table(s, MARGIN, BODY_TOP, [0.4, 4.9, 1.9, 1.7, 1.3, 0.8, 1.33],
               ["#", "Item (link)", "Company", "Event type", "Date", "Label", "Flags"], rows,
               limits=[3, 85, 28, 24, 16, 6, 40], size=10, row_h=0.55)
    else:
        _paragraphs(s, MARGIN, BODY_TOP, BODY_W, BODY_H, ["No items passed the filter in this run."], size=18)
    _notes(s, data.notes["found"])

    # 5. by company
    s = slide(SECTION_TITLES["company"])
    top = data.by_company[:TOP_COMPANIES]
    _picture_or_sentence(s, charts.bar_chart(top, "Items per company (top 10)", "blue", 7.0, 4.6),
                         charts.fallback_sentence("company", top), MARGIN, BODY_TOP, Inches(7.0), Inches(4.6))
    lines = [f"{c}: {', '.join(data.company_events.get(c, []))}" for c, _ in top]
    _paragraphs(s, Inches(7.8), BODY_TOP, Inches(5.0), BODY_H, ["Event types per company:"] + lines,
                size=11, max_chars=110)
    _notes(s, data.notes["company"])

    # 6. by technology and event type
    s = slide(SECTION_TITLES["tech_event"])
    _picture_or_sentence(s, charts.bar_chart(data.by_technology[:10], "Items per technology", "green", 6.0, 4.4),
                         charts.fallback_sentence("technology", data.by_technology), MARGIN, BODY_TOP,
                         Inches(6.0), Inches(4.4))
    _picture_or_sentence(s, charts.bar_chart(data.by_event_type, "Items per event type", "orange", 6.0, 4.4),
                         charts.fallback_sentence("event type", data.by_event_type), Inches(6.8), BODY_TOP,
                         Inches(6.0), Inches(4.4))
    labels = ", ".join(f"{k}: {v}" for k, v in data.by_label) or "none"
    regions = ", ".join(f"{k}: {v}" for k, v in data.by_region) or "none"
    _paragraphs(s, MARGIN, Inches(5.95), BODY_W, Inches(0.9), [f"Labels: {labels}.   Regions: {regions}."],
                size=12)
    _notes(s, data.notes["tech_event"])

    # 7. seen in several sources
    s = slide(SECTION_TITLES["stories"])
    if data.stories:
        rows = [
            [r.title, r.company, r.event_type, ", ".join(r.source_names), str(r.item_count),
             f"{r.fallback_items} via switching" if r.fallback_items else "-"]
            for r in data.stories[:10]
        ]
        _table(s, MARGIN, BODY_TOP, [4.2, 1.9, 1.7, 3.0, 0.7, 0.83],
               ["Story", "Company", "Event type", "Sources", "Items", "Switching"], rows,
               limits=[75, 28, 24, 70, 4, 18], size=10, row_h=0.5)
        if len(data.stories) > 10:
            _paragraphs(s, MARGIN, Inches(6.55), BODY_W, Inches(0.4),
                        [f"{len(data.stories) - 10} more stories are listed in the appendix items."], size=11)
    else:
        _paragraphs(s, MARGIN, BODY_TOP, BODY_W, BODY_H,
                    ["No story was seen in two or more independent sources in this run."], size=18)
    _notes(s, data.notes["stories"])

    # 8. sources and compliance (continues on more slides if needed)
    chunks = [data.sources[i:i + SOURCE_ROWS_PER_SLIDE]
              for i in range(0, len(data.sources), SOURCE_ROWS_PER_SLIDE)] or [[]]
    for idx, chunk in enumerate(chunks):
        title = SECTION_TITLES["sources"] + ("" if idx == 0 else " (continued)")
        s = slide(title)
        if chunk:
            rows = [[r.name, _kind_text(r.kind), r.status, str(r.collected), str(r.passed), note_text(r)]
                    for r in chunk]
            _table(s, MARGIN, BODY_TOP, [3.0, 2.5, 1.5, 0.95, 0.85, 3.53],
                   ["Source", "Kind", "Status", "Collected", "Passed", "Note / reason"], rows,
                   limits=[45, 40, 18, 5, 5, 100], size=9, row_h=0.34)
        else:
            _paragraphs(s, MARGIN, BODY_TOP, BODY_W, Inches(1), ["No sources were recorded in this run."], size=16)
        if idx == len(chunks) - 1:
            _paragraphs(s, MARGIN, Inches(5.95), BODY_W, Inches(1.0), compliance_lines(data), size=11,
                        max_chars=200)
        _notes(s, data.notes["sources"])

    # 9. how to read
    s = slide(SECTION_TITLES["howto"])
    _paragraphs(s, MARGIN, BODY_TOP, BODY_W, BODY_H, HOW_TO_READ, size=14, bullets=True)

    # 10+. appendix
    items = data.all_items
    pages = appendix_slides(len(items))
    for page in range(pages):
        chunk = items[page * APPENDIX_ROWS_PER_SLIDE:(page + 1) * APPENDIX_ROWS_PER_SLIDE]
        title = SECTION_TITLES["appendix"] + (f" ({page + 1} of {pages})" if pages > 1 else "")
        s = slide(title)
        if chunk:
            rows = [[r.date_text, r.company, r.title, r.event_type, r.region, r.label, r.marker or "-", (r.url, r.url)]
                    for r in chunk]
            _table(s, MARGIN, BODY_TOP, [1.0, 1.4, 3.1, 1.3, 0.6, 0.6, 1.3, 3.03],
                   ["Date", "Company", "Title", "Event type", "Region", "Label", "Flags", "Link"], rows,
                   limits=[16, 22, 60, 22, 14, 6, 36, 0], size=8, row_h=0.44)
        else:
            _paragraphs(s, MARGIN, BODY_TOP, BODY_W, BODY_H, ["No items passed the filter in this run."], size=18)

    buf = BytesIO()
    prs.save(buf)
    return buf.getvalue()
