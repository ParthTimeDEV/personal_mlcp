"""Charts for the report, drawn with matplotlib into memory (sachi2.md S8).

Owner: Sachi. PNG bytes only (BytesIO); nothing is written to disk. Agg backend, so no display is needed.
A chart with fewer than 2 data points is not drawn: the builders show a sentence instead.
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Okabe-Ito palette: distinguishable with the common forms of colour blindness.
PALETTE = {
    "blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "vermillion": "#D55E00",
    "sky": "#56B4E9", "purple": "#CC79A7", "yellow": "#F0E442", "black": "#000000",
}
TEXT_COLOUR = "#222222"
GRID_COLOUR = "#DDDDDD"
LABEL_CHARS = 30
MIN_POINTS = 2


def too_few(pairs: list[tuple[str, int]]) -> bool:
    return len(pairs) < MIN_POINTS


def fallback_sentence(what: str, pairs: list[tuple[str, int]]) -> str:
    """Text shown instead of a chart with fewer than 2 data points."""
    if not pairs:
        return f"No {what} to chart: no items passed the filter."
    label, count = pairs[0]
    return f"Only one {what} in this run: {label} ({count} item{'s' if count != 1 else ''}). No chart is drawn."


def _short(label: str) -> str:
    return label if len(label) <= LABEL_CHARS else label[: LABEL_CHARS - 1] + "…"


def bar_chart(pairs: list[tuple[str, int]], title: str, colour: str = "blue",
              width_in: float = 6.4, height_in: float = 3.6) -> Optional[bytes]:
    """Horizontal bar chart, largest at the top, value printed on each bar. None if < 2 points."""
    if too_few(pairs):
        return None
    labels = [_short(k) for k, _ in pairs][::-1]
    values = [v for _, v in pairs][::-1]
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=150)
    try:
        bars = ax.barh(labels, values, color=PALETTE.get(colour, colour), height=0.6)
        ax.set_title(title, fontsize=11, color=TEXT_COLOUR, loc="left")
        ax.set_xlabel("items", fontsize=9, color=TEXT_COLOUR)
        ax.tick_params(axis="both", labelsize=8, colors=TEXT_COLOUR)
        ax.xaxis.grid(True, color=GRID_COLOUR, linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.xaxis.get_major_locator().set_params(integer=True)
        top = max(values)
        ax.set_xlim(0, top * 1.15 + 0.5)
        for bar, value in zip(bars, values):
            ax.text(bar.get_width() + top * 0.02 + 0.05, bar.get_y() + bar.get_height() / 2, str(value),
                    va="center", fontsize=8, color=TEXT_COLOUR)
        fig.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format="png")
        return buf.getvalue()
    finally:
        plt.close(fig)
