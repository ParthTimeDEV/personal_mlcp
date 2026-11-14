"""PDF report builder (reportlab platypus), A4 (sachi2.md S7, S8).

Owner: Sachi. Same sections and numbers as the PPTX (both read `ReportData`). Header and footer with
page numbers on every page, tables that split across pages with the header row repeated, clickable
links. Built in memory; returns bytes.
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional, Sequence
from xml.sax.saxutils import escape, quoteattr

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from atlas.report import charts
from atlas.report.build import (
    DISCOVERED_NOTE, HOW_TO_READ, METHOD_LINES, PREPARED_FOR, SECTION_TITLES, TOP_COMPANIES, ReportData,
    compliance_lines, item_line, note_text, truncate,
)

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm
FRAME_W = PAGE_W - 2 * MARGIN
ACCENT = colors.HexColor("#0072B2")
GREY = colors.HexColor("#666666")
HEADER_FILL = colors.HexColor("#E8E8E8")
GRID = colors.HexColor("#BBBBBB")

_base = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_base["Heading1"], fontSize=18, leading=22, spaceAfter=10,
                    textColor=colors.HexColor("#222222"))
BODY = ParagraphStyle("Body", parent=_base["BodyText"], fontSize=10, leading=13.5, alignment=TA_LEFT)
BULLET = ParagraphStyle("Bullet", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=4)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8, leading=10)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=7.5, leading=9.2)
CELL_HEAD = ParagraphStyle("CellHead", parent=CELL, fontName="Helvetica-Bold")
TITLE = ParagraphStyle("Title", parent=H1, fontSize=26, leading=32, spaceAfter=18)


def _p(text: str, style=BODY) -> Paragraph:
    return Paragraph(escape(text), style)


def _link(text: str, url: Optional[str], style=CELL) -> Paragraph:
    if not url:
        return _p(text, style)
    return Paragraph(f'<a href={quoteattr(url)} color="#0072B2">{escape(text)}</a>', style)


def _bullets(lines: Sequence[str]) -> list:
    return [Paragraph(escape(line), BULLET, bulletText="•") for line in lines]


def _table(header: Sequence[str], rows: Sequence[Sequence], widths_cm: Sequence[float]) -> Table:
    data = [[_p(h, CELL_HEAD) for h in header]]
    for row in rows:
        data.append([c if isinstance(c, Paragraph) else _p(str(c), CELL) for c in row])
    total = sum(widths_cm)
    widths = [FRAME_W * w / total for w in widths_cm]
    t = Table(data, colWidths=widths, repeatRows=1, splitByRow=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _chart(png: Optional[bytes], sentence: str, width: float) -> object:
    if not png:
        return _p(sentence)
    img = Image(BytesIO(png))
    ratio = img.imageHeight / float(img.imageWidth)
    img.drawWidth, img.drawHeight = width, width * ratio
    return img


def _kind_text(kind: str) -> str:
    return DISCOVERED_NOTE if kind == "discovered" else kind


def build_pdf(data: ReportData) -> bytes:
    buf = BytesIO()

    def decorate(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawString(MARGIN, PAGE_H - 1.1 * cm, f"{SECTION_TITLES['title']}  |  run {data.run_id}")
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(0.8)
        canvas.line(MARGIN, PAGE_H - 1.25 * cm, PAGE_W - MARGIN, PAGE_H - 1.25 * cm)
        canvas.drawString(MARGIN, 1.0 * cm, PREPARED_FOR)
        canvas.drawRightString(PAGE_W - MARGIN, 1.0 * cm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"{SECTION_TITLES['title']} - run {data.run_id}", author="Group 8, VIT Pune",
        invariant=1, pageCompression=0,
    )
    story: list = []

    # 1. title
    story += [Spacer(1, 4 * cm), Paragraph(escape(SECTION_TITLES["title"]), TITLE), _p("Run report"),
              _p(f"Run id: {data.run_id}"), _p(f"Run date: {data.run_date}"), Spacer(1, 1 * cm),
              _p(PREPARED_FOR), PageBreak()]

    # 2. executive summary
    story += [_p(SECTION_TITLES["summary"], H1), *_bullets(data.summary_sentences)]
    if data.headline_items:
        story += [Spacer(1, 8), _p("Headline items:")]
        for row in data.headline_items:
            story += [_link(row.title, row.url, BODY), _p(item_line(row), SMALL), Spacer(1, 4)]
    story.append(PageBreak())

    # 3. scope and method
    story += [_p(SECTION_TITLES["scope"], H1), *_bullets(data.scope_lines), Spacer(1, 8),
              *_bullets(METHOD_LINES), PageBreak()]

    # 4. what we found
    story.append(_p(SECTION_TITLES["found"], H1))
    if data.top_items:
        rows = [[str(i), _link(r.title, r.url), r.company, r.event_type, r.date_text, r.label, r.marker or "-"]
                for i, r in enumerate(data.top_items, start=1)]
        story.append(_table(["#", "Item (link)", "Company", "Event type", "Date", "Label", "Flags"], rows,
                            [0.6, 6.0, 2.6, 2.3, 1.9, 1.1, 2.5]))
    else:
        story.append(_p("No items passed the filter in this run."))
    story.append(PageBreak())

    # 5. by company
    top = data.by_company[:TOP_COMPANIES]
    story += [_p(SECTION_TITLES["company"], H1),
              _chart(charts.bar_chart(top, "Items per company (top 10)", "blue"),
                     charts.fallback_sentence("company", top), FRAME_W),
              Spacer(1, 8), _p("Event types per company:")]
    story += _bullets([f"{c}: {', '.join(data.company_events.get(c, []))}" for c, _ in top])
    story.append(PageBreak())

    # 6. by technology and event type
    story += [_p(SECTION_TITLES["tech_event"], H1),
              _chart(charts.bar_chart(data.by_technology[:10], "Items per technology", "green", 6.4, 3.2),
                     charts.fallback_sentence("technology", data.by_technology), FRAME_W * 0.9),
              Spacer(1, 6),
              _chart(charts.bar_chart(data.by_event_type, "Items per event type", "orange", 6.4, 3.2),
                     charts.fallback_sentence("event type", data.by_event_type), FRAME_W * 0.9),
              Spacer(1, 6),
              _p("Labels: " + (", ".join(f"{k}: {v}" for k, v in data.by_label) or "none") + ".   Regions: "
                 + (", ".join(f"{k}: {v}" for k, v in data.by_region) or "none") + "."),
              PageBreak()]

    # 7. seen in several sources
    story.append(_p(SECTION_TITLES["stories"], H1))
    if data.stories:
        rows = [[r.title, r.company, r.event_type, ", ".join(r.source_names), str(r.item_count),
                 f"{r.fallback_items} via switching" if r.fallback_items else "-"] for r in data.stories]
        story.append(_table(["Story", "Company", "Event type", "Sources", "Items", "Switching"], rows,
                            [5.5, 2.5, 2.3, 4.0, 1.0, 1.7]))
    else:
        story.append(_p("No story was seen in two or more independent sources in this run."))
    story.append(PageBreak())

    # 8. sources and compliance
    story.append(_p(SECTION_TITLES["sources"], H1))
    if data.sources:
        rows = [[r.name, _kind_text(r.kind), r.status, str(r.collected), str(r.passed), note_text(r)]
                for r in data.sources]
        story.append(_table(["Source", "Kind", "Status", "Collected", "Passed", "Note / reason"], rows,
                            [4.0, 3.2, 2.2, 1.5, 1.3, 5.0]))
    else:
        story.append(_p("No sources were recorded in this run."))
    story += [Spacer(1, 8), KeepTogether(_bullets(compliance_lines(data))), PageBreak()]

    # 9. how to read
    story += [_p(SECTION_TITLES["howto"], H1), *_bullets(HOW_TO_READ), PageBreak()]

    # 10. appendix (paginates on its own)
    story.append(_p(SECTION_TITLES["appendix"], H1))
    if data.all_items:
        rows = [[r.date_text, r.company, truncate(r.title, 140), r.event_type, r.region, r.label,
                 r.marker or "-", _link(r.url, r.url)] for r in data.all_items]
        story.append(_table(["Date", "Company", "Title", "Event type", "Region", "Label", "Flags", "Link"], rows,
                            [1.8, 2.2, 4.2, 2.0, 1.4, 1.0, 2.0, 4.5]))
    else:
        story.append(_p("No items passed the filter in this run."))

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
