"""The brief: one slide or page with exactly three things: the facts, the sources, and why it matters for Atlas Copco.

Owner: Nikhil. Atlas Copco's own news is left out on purpose (they know it). Every line comes from the run's
data: facts are the stored key facts, sources are the sources the run read, and "why it matters" is a fixed sentence
per event type (rules, no AI, no invented numbers). Facts the team denied on the Facts screen are never shown;
approved facts come first. Built in memory, uploaded to reports/ in the Volume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Literal, Optional
from xml.sax.saxutils import escape, quoteattr

from atlas.models import Item, OutputEnvelope
from atlas.report.build import check_personal_data, truncate
from atlas.report.onepager import PRIORITY, _clean, _fact, _is_own

MAX_ROWS = 6
WHY = {
    "acquisition": "Ownership changes can change who competes for the same customers and how fast a rival grows.",
    "partnership": "A new partner can widen a competitor's reach, products or service coverage.",
    "investment_expansion": "New capacity or investment shows where a competitor expects demand to grow.",
    "regulation_standard": "A rule or standard can change which products customers may or want to buy.",
    "product_launch": "A launch shows where a competitor is putting its product effort.",
    "appointment": "Leadership changes can signal a change in a competitor's direction.",
    "award": "Awards shape how customers rate competing suppliers.",
    "event": "Events show where competitors present and meet customers.",
}
WHY_OTHER = "Background on what competitors say to customers and what customers are asking about."
EVENT_LABEL = {
    "acquisition": "Acquisition", "partnership": "Partnership", "investment_expansion": "Investment / expansion",
    "regulation_standard": "Regulation / standard", "product_launch": "Product launch", "appointment": "Appointment",
    "award": "Award", "event": "Event",
}


@dataclass
class Row:
    company: str
    label: str
    date: str
    fact: str
    why: str
    source: str
    url: str
    approved: bool = False


@dataclass
class Brief:
    run_id: str
    run_date: str
    rows: list[Row] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    note: str = ""


def _why(item: Item) -> str:
    text = WHY.get(item.event_type or "", WHY_OTHER)
    return f"{text} Technology: {item.technology}." if item.technology else text


def compute(envelope: OutputEnvelope, decisions: Optional[dict[str, str]] = None,
            confirmations: Optional[dict[str, str]] = None) -> Brief:
    check_personal_data(envelope)
    decisions, confirmations = decisions or {}, confirmations or {}
    pool = [i for i in envelope.items if not _is_own(i) and decisions.get(i.id) != "denied"]

    def rank(item: Item) -> tuple:
        event = PRIORITY.index(item.event_type) if item.event_type in PRIORITY else len(PRIORITY)
        return (decisions.get(item.id) != "approved", event, "".join(chr(255 - ord(c)) for c in item.published_at or ""))

    rows: list[Row] = []
    used: set[str] = set()
    for item in sorted(pool, key=rank):
        approved = decisions.get(item.id) == "approved"
        fact = _fact(item)
        if fact is None and approved:  # a person approved it: show a clean fact even if it has no number or verb
            fact = next((truncate(f, 140) for f in item.key_facts if _clean(f)), None)
        if not (item.company and _clean(item.company) and _clean(item.title) and fact) or item.company in used:
            continue
        used.add(item.company)
        rows.append(Row(
            company=item.company, label=EVENT_LABEL.get(item.event_type or "", "News"),
            date=item.published_at or "date not stated", fact=fact, why=_why(item),
            source=item.source_name, url=item.source_url, approved=approved))
        if len(rows) == MAX_ROWS:
            break

    real = [s for s in envelope.sources if s.kind != "fallback"]
    read = [s for s in real if s.items_collected > 0]
    refused = [s for s in real if s.items_collected == 0 and (s.status != "working" or (s.note or "").startswith("refused"))]
    sources = [
        f"{s.name}: {s.items_passed} item(s)"
        f"{' (confirmed)' if confirmations.get(s.source_id) == 'confirmed' else ' (not yet confirmed)'}"
        for s in read if s.items_passed > 0
    ]
    sources.append(f"{len(refused)} further site(s) blocked or forbade automated reading, so we did not read them.")
    note = "Facts are short, stored facts with links; most are company statements. Source list proposed, pending approval."
    return Brief(run_id=envelope.run_id, run_date=envelope.generated_at[:10], rows=rows, sources=sources, note=note)


# ---------- PPTX ----------

def _pptx(b: Brief) -> bytes:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    dark, grey, accent = RGBColor(0x22, 0x22, 0x22), RGBColor(0x66, 0x66, 0x66), RGBColor(0x00, 0x72, 0xB2)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    def text(left, top, width, height, size, bold=False, color=dark, value=""):
        tf = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height)).text_frame
        tf.word_wrap = True
        run = tf.paragraphs[0].add_run()
        run.text, run.font.size, run.font.bold, run.font.color.rgb = value, Pt(size), bold, color
        return tf

    text(0.5, 0.25, 12.3, 0.6, 26, True, value="Compressor market brief")
    text(0.5, 0.85, 12.3, 0.4, 12, color=grey, value=f"Run {b.run_id} · {b.run_date}")

    rows = max(1, len(b.rows)) + 1
    table = slide.shapes.add_table(rows, 3, Inches(0.5), Inches(1.35), Inches(12.3), Inches(0.4 * rows)).table
    for col, width in enumerate((5.4, 4.8, 2.1)):
        table.columns[col].width = Inches(width)

    def cell(r, c, value, bold=False, size=10, color=dark, link=None):
        tf = table.cell(r, c).text_frame
        tf.word_wrap = True
        run = tf.paragraphs[0].add_run()
        run.text, run.font.size, run.font.bold, run.font.color.rgb = value, Pt(size), bold, color
        if link:
            run.hyperlink.address = link
            run.font.underline = True

    for c, head in enumerate(("1  The facts", "3  Why it matters for Atlas Copco", "2  Source")):
        cell(0, c, head, True, 11, accent)
    if not b.rows:
        cell(1, 0, "No facts passed the filter in this run.")
    for r, row in enumerate(b.rows, 1):
        cell(r, 0, f"{row.company} · {row.label} · {row.date}{' · approved' if row.approved else ''}", True)
        table.cell(r, 0).text_frame.add_paragraph().add_run().text = row.fact
        table.cell(r, 0).text_frame.paragraphs[1].runs[0].font.size = Pt(10)
        cell(r, 1, row.why)
        cell(r, 2, row.source, size=10, color=accent, link=row.url)

    tf = text(0.5, 5.55, 12.3, 1.4, 11, value="")
    tf.paragraphs[0].runs[0].text = "2  Sources"
    tf.paragraphs[0].runs[0].font.bold = True
    tf.paragraphs[0].runs[0].font.color.rgb = accent
    for line in b.sources[:6]:
        run = tf.add_paragraph().add_run()
        run.text, run.font.size, run.font.color.rgb = "• " + truncate(line, 150), Pt(10), dark
    text(0.5, 7.05, 12.3, 0.3, 9, color=grey, value=b.note)
    out = BytesIO()
    prs.save(out)
    return out.getvalue()


# ---------- PDF ----------

def _pdf(b: Brief) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    accent = colors.HexColor("#0072B2")
    base = ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=11.5)
    bold = ParagraphStyle("bo", parent=base, fontName="Helvetica-Bold")
    head = ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=11, textColor=accent)
    title = ParagraphStyle("t", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=24)
    small = ParagraphStyle("s", parent=base, fontSize=8, textColor=colors.HexColor("#666666"))

    data = [[Paragraph("1  The facts", head), Paragraph("3  Why it matters for Atlas Copco", head),
             Paragraph("2  Source", head)]]
    if not b.rows:
        data.append([Paragraph("No facts passed the filter in this run.", base), "", ""])
    for row in b.rows:
        data.append([
            [Paragraph(escape(f"{row.company} · {row.label} · {row.date}{' · approved' if row.approved else ''}"), bold),
             Paragraph(escape(row.fact), base)],
            Paragraph(escape(row.why), base),
            Paragraph(f"<link href={quoteattr(row.url)} color=\"#0072B2\"><u>{escape(row.source)}</u></link>", base),
        ])
    table = Table(data, colWidths=[12.6 * cm, 9.6 * cm, 4.6 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")), ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story = [Paragraph("Compressor market brief", title), Paragraph(escape(f"Run {b.run_id} · {b.run_date}"), small),
             Spacer(1, 8), table, Spacer(1, 8), Paragraph("2  Sources", head)]
    story += [Paragraph("• " + escape(truncate(s, 150)), base) for s in b.sources[:6]]
    story += [Spacer(1, 6), Paragraph(escape(b.note), small)]
    out = BytesIO()
    SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.1 * cm,
                      bottomMargin=1.0 * cm, title="Compressor market brief").build(story)
    return out.getvalue()


# ---------- entry points ----------

def build_brief(envelope: OutputEnvelope, fmt: Literal["pptx", "pdf"], decisions: Optional[dict[str, str]] = None,
                confirmations: Optional[dict[str, str]] = None) -> bytes:
    if fmt not in ("pptx", "pdf"):
        raise ValueError(f"unknown format: {fmt!r} (use 'pptx' or 'pdf')")
    brief = compute(envelope, decisions, confirmations)
    return _pptx(brief) if fmt == "pptx" else _pdf(brief)


def brief_path(run_id: str, fmt: str) -> str:
    return f"reports/brief_{run_id}.{fmt}"


def write_brief(run_id: str, fmt: Literal["pptx", "pdf"]) -> str:
    """Build the brief from output/poc_<run_id>.json plus the team's current fact decisions and source
    confirmations, upload it to reports/, and return the Volume path."""
    from atlas import review, storage
    from atlas.settings import get_settings

    envelope = OutputEnvelope.model_validate(storage.read_json(f"output/poc_{run_id}.json"))
    relative = brief_path(run_id, fmt)
    storage.write_bytes(relative, build_brief(envelope, fmt, review.load_fact_decisions(),
                                              review.load_source_confirmations()))
    return f"{get_settings().volume_root}/{relative}"
