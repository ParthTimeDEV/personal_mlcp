"""Shared logic for the simple 4-page app: start a rerun after every save, show its progress, classify sources.

No Streamlit import at module level, so the logic is unit-testable. A rerun is `python -m atlas.run` in a
subprocess (the token is read by that process from .env, never passed on the command line).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from app.lib.runner import start_run
from atlas.models import Candidate, Source

MAX_LINES = 400


@dataclass
class RunWatcher:
    """A pipeline run started by the app, with its output collected by a background thread."""

    proc: object
    lines: list[str] = field(default_factory=list)
    reason: str = ""

    def __post_init__(self) -> None:
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        for line in iter(self.proc.stdout.readline, ""):
            self.lines.append(line.rstrip())
            del self.lines[:-MAX_LINES]

    @property
    def running(self) -> bool:
        return self.proc.poll() is None

    @property
    def exit_code(self) -> Optional[int]:
        return self.proc.poll()

    def progress(self) -> tuple[int, int]:
        """(source number, total) from the last '[n/m] source' line, or (0, 0)."""
        import re
        for line in reversed(self.lines):
            m = re.match(r"^\[(\d+)/(\d+)\]", line)
            if m:
                return int(m.group(1)), int(m.group(2))
        return 0, 0

    def last_line(self) -> str:
        return next((l for l in reversed(self.lines) if l.strip()), "Starting...")


def start_rerun(reason: str) -> RunWatcher:
    """Start a full run with the saved settings. The reason is shown to the user."""
    return RunWatcher(start_run([]), reason=reason)


def classify_sources(register: list[Source], candidates: list[Candidate], confirmations: dict[str, str],
                     rejected_ids: set[str] | None = None) -> dict[str, list[dict]]:
    """Group every known source for the Sources page.

    confirmed   working sources the team confirmed
    to_confirm  working sources and usable scout finds that nobody confirmed yet
    blocked     sources that are blocked, unreachable, forbid automation, or failed the scout's rules
    Each row: id, name, url, kind (registered/discovered), detail (why), score (discovered only).
    """
    rejected_ids = rejected_ids or set()
    out: dict[str, list[dict]] = {"confirmed": [], "to_confirm": [], "blocked": []}
    for s in register:
        row = {"id": s.source_id, "name": s.name, "url": s.url, "kind": "registered", "type": s.type,
               "detail": s.notes, "score": None}
        if s.vetting_status != "working" or s.status in ("blocked", "needs_permission"):
            row["detail"] = f"{s.vetting_status}: {s.notes}"
            out["blocked"].append(row)
        elif confirmations.get(s.source_id) == "confirmed":
            out["confirmed"].append(row)
        else:
            out["to_confirm"].append(row)
    for c in candidates:
        sid = f"disc_{c.candidate_id}"
        row = {"id": sid, "name": c.name, "url": c.url, "kind": "discovered", "type": c.type_guess,
               "detail": c.notes, "score": c.trust_score}
        if c.candidate_id in rejected_ids:
            continue
        if c.terms_status == "forbids_automation" or c.robots_status == "disallowed" or c.status == "rejected_by_rules":
            reason = c.terms_evidence or ("robots.txt disallows" if c.robots_status == "disallowed" else "failed the rules")
            row["detail"] = f"refused by the rules: {reason}"
            out["blocked"].append(row)
        elif c.usable and confirmations.get(sid) == "confirmed":
            out["confirmed"].append(row)
        elif c.usable:
            out["to_confirm"].append(row)
    return out
