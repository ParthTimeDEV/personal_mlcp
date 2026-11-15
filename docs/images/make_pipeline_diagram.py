"""Draws docs/images/pipeline.png and pipeline.svg for prepare.md.

Documentation only: needs matplotlib, which is not part of requirements.txt.
    pip install matplotlib
    python docs/images/make_pipeline_diagram.py
"""
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent

INK = "#1f2937"
MUTED = "#6b7280"
LINE = "#cbd5e1"
BG = "#ffffff"
PANEL = "#f8fafc"
BLUE, BLUE_BG = "#1d4ed8", "#e0e7ff"
TEAL, TEAL_BG = "#0f766e", "#ccfbf1"
AMBER, AMBER_BG = "#b45309", "#fef3c7"
RED, RED_BG = "#b91c1c", "#fee2e2"
GREY_BG = "#f1f5f9"

fig, ax = plt.subplots(figsize=(18, 10.8), dpi=200)
ax.set_xlim(0, 100)
ax.set_ylim(0, 60)
ax.axis("off")
fig.patch.set_facecolor(BG)


def box(x, y, w, h, fc, ec=LINE, lw=1.2, r=0.9, z=1):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=z)
    ax.add_patch(p)
    return p


def text(x, y, s, size=9, color=INK, weight="normal", ha="left", va="top", family=None, z=5, linespacing=1.2):
    ax.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha, va=va, family=family, zorder=z,
            linespacing=linespacing)


def arrow(x1, y1, x2, y2, color=MUTED, style="-|>", ls="-", lw=1.8, rad=0.0):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16, color=color, lw=lw, ls=ls,
        connectionstyle=f"arc3,rad={rad}", zorder=3,
    ))


# ---- title ----
text(1, 59.4, "Atlas Copco Market & Technology PoC: how the pipeline works", size=19, weight="bold")
text(1, 56.7, "Input  →  Engine  →  Output.  Public USA sources on industrial compressor technology, filtered by transparent rules, "
     "stored as JSON in Databricks.", size=10.5, color=MUTED)

# ---- sources ----
box(1, 21, 13, 26, PANEL)
text(2, 46.2, "INPUT", size=8.5, color=MUTED, weight="bold")
text(2, 44.3, "5 proposed sources", size=10.5, weight="bold")
sources = [
    "Compressed Air\nBest Practices", "Quincy Compressor", "Sullair US", "Pumps & Systems", "US DOE newsroom",
]
yy = 41.6
for s in sources:
    box(2, yy - 2.9, 11, 3.0, BG, ec=LINE, lw=1, r=0.5)
    text(7.5, yy - 1.4, s, size=8.2, ha="center", va="center")
    yy -= 3.5
text(7.5, 21.6, "config/sources.yaml", size=7.4, color=MUTED, family="monospace", va="bottom", ha="center")

# ---- stages ----
stages = [
    ("1", "Compliance Gate", "Can we use it?", "RULES", BLUE, BLUE_BG, "compliance.py", [
        "Source vetted as working", "No ban on automation in its terms", "robots.txt checked every run and URL",
        "Waits 3 s or more between requests"]),
    ("2", "Collector", "Get the pages", "AUTO", TEAL, TEAL_BG, "collect.py", [
        "RSS feed first, web list second", "Every redirect re-checked", "Stops at HTTP 429 / 503",
        "Pages held in memory only"]),
    ("3", "Extractor", "Pull out the facts", "AUTO", TEAL, TEAL_BG, "extract.py", [
        "Main text (trafilatura)", "Personal data removed (Presidio)",
        "Title, date, company, technology, key facts", "Text dropped, fingerprint kept"]),
    ("4", "Cleaner", "Tidy up", "RULES", BLUE, BLUE_BG, "clean.py", [
        "Duplicates removed (URL, fingerprint)", "Dates in ISO format", "Company names matched (alias table, RapidFuzz)"]),
    ("5", "Relevance Filter", "What matters?", "RULES", BLUE, BLUE_BG, "filter.py", [
        "1  Compressor-related", "2  North America", "3  Credible source", "4  Recent (12 months)",
        "Passes only if all four are yes; reasons stored"]),
    ("6", "Output", "Show the result", "AUTO", TEAL, TEAL_BG, "run.py", [
        "Validated with Pydantic", "Final JSON file with the passed items", "Run log: refused sources and errors",
        "Summary and local-data check"]),
]
x0, w, gap, y0, h = 16, 12, 2.2, 21, 26
centres = []
for i, (num, name, sub, tag, col, bg, fname, bullets) in enumerate(stages):
    x = x0 + i * (w + gap)
    centres.append(x + w / 2)
    box(x, y0, w, h, BG, ec=col, lw=1.6)
    box(x, y0 + h - 5.6, w, 5.6, bg, ec=col, lw=1.6)
    ax.add_patch(plt.Circle((x + 1.5, y0 + h - 2.8), 1.0, color=col, zorder=4))
    text(x + 1.5, y0 + h - 2.85, num, size=10, color="white", weight="bold", ha="center", va="center")
    text(x + 3.0, y0 + h - 1.6, name, size=10.8, weight="bold")
    text(x + 3.0, y0 + h - 3.8, sub, size=8.6, color=MUTED)
    ty = y0 + h - 6.9
    for b in bullets:
        wrapped = textwrap.fill(b, 20, break_long_words=False)
        text(x + 0.8, ty, "•  " + wrapped.replace("\n", "\n    "), size=8.2, linespacing=1.25)
        ty -= 1.4 * (wrapped.count("\n") + 1) + 0.65
    box(x + 0.9, y0 + 1.2, 4.0, 1.7, bg, ec=col, lw=1, r=0.6)
    text(x + 2.9, y0 + 2.05, tag, size=8, color=col, weight="bold", ha="center", va="center")
    text(x + w - 0.8, y0 + 2.05, fname, size=8, color=MUTED, family="monospace", ha="right", va="center")
    text(x + 0.9, y0 + 1.6, "", size=1)

# arrows: sources -> 1, between stages
arrow(14.2, 34.5, 15.8, 34.5)
for i in range(5):
    arrow(x0 + i * (w + gap) + w + 0.1, y0 + h / 2, x0 + (i + 1) * (w + gap) - 0.1, y0 + h / 2)

# refused branch
box(30.2, 48.8, 28.0, 5.6, RED_BG, ec=RED, lw=1.3, r=0.7)
text(31.2, 53.6, "Refused at the gate: 6 sources", size=8.8, color=RED, weight="bold")
text(31.2, 51.9, "3 blocked by their own terms, 3 refuse our agent (HTTP 403 / 429).", size=8, color=RED)
text(31.2, 50.3, "Logged with the reason. Never bypassed.", size=8, color=RED)
arrow(22, 47.2, 30.0, 50.6, color=RED, ls="--", lw=1.5, rad=-0.25)

# ---- Databricks ----
box(1, 2.2, 98, 15.6, PANEL)
text(2, 3.7, "DATABRICKS VOLUME  /Volumes/atlas_poc/default/data/", size=10, weight="bold", va="center")
text(98, 3.7, "Everything goes straight from memory to the cloud. Nothing is stored on the laptop.",
     size=9, color=MUTED, ha="right", va="center")

chips = [
    ("source_register/", "register copy", 7.5, GREY_BG, MUTED, None),
    ("logs/", "what ran, what was refused", None, AMBER_BG, AMBER, 0),
    ("raw/", "what was collected (no text)", None, AMBER_BG, AMBER, 1),
    ("(no folder)", "page text is dropped", None, GREY_BG, MUTED, 2),
    ("clean/", "all items + filter results", None, AMBER_BG, AMBER, 3),
    ("facts/", "items that passed", None, AMBER_BG, AMBER, 4),
    ("output/", "final JSON for the demo", None, AMBER_BG, AMBER, 5),
]
for name, desc, cx, bg, col, idx in chips:
    if idx is None:
        cx_ = 7.5
    else:
        cx_ = centres[idx]
    box(cx_ - 5.7, 5.4, 11.4, 8.4, bg, ec=col, lw=1.3, r=0.6)
    text(cx_, 11.9, name, size=9.6, weight="bold", ha="center", va="center", family="monospace", color=INK)
    text(cx_, 8.3, textwrap.fill(desc, 22), size=8.2, color=MUTED, ha="center", va="center")
    if idx is not None and name != "(no folder)":
        arrow(cx_, y0 - 0.1, cx_, 14.0, color=col, ls="--", lw=1.4)
# the register is copied to the Volume when a run starts
arrow(7.5, 20.9, 7.5, 14.0, color=MUTED, ls="--", lw=1.4)
# clean/ also receives the filter's results (all items); facts/ and output/ get only passed items
arrow(centres[4] - 1.5, y0 - 0.1, centres[3] + 2.5, 14.0, color=AMBER, ls="--", lw=1.2, rad=0.25)

# ---- legend ----
lx = 1
box(lx, 0.1, 98, 1.9, BG, ec=BG)
for label, col, bg, desc, px in [
    ("RULES", BLUE, BLUE_BG, "transparent rules, anyone can read them", 1),
    ("AUTO", TEAL, TEAL_BG, "automated step, no AI", 32),
]:
    box(px, 0.35, 4.0, 1.4, bg, ec=col, lw=1, r=0.5)
    text(px + 2.0, 1.05, label, size=7.8, color=col, weight="bold", ha="center", va="center")
    text(px + 4.8, 1.05, desc, size=8.4, color=MUTED, va="center")
text(62, 1.05, "No AI or language model is used in Friday's pipeline.", size=8.6, weight="bold", va="center")

fig.savefig(OUT / "pipeline.png", dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(OUT / "pipeline.svg", bbox_inches="tight", facecolor=BG)
print("wrote", OUT / "pipeline.png", "and", OUT / "pipeline.svg")

