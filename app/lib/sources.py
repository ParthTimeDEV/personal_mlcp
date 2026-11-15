"""Pure business and presentation logic for the Sources screen.

This module is browser-independent and 100% unit-testable offline.
Handles source register formatting, candidate filtering, decision construction,
usability validation, and evidence presentation.
"""

from __future__ import annotations

from typing import Any
from pydantic import ValidationError

from atlas.models import Candidate, CandidateDecision, Source


DISCLAIMER_TEXT = (
    "Discovered sources are not approved by Atlas Copco. "
    "Accepting here only makes them available to our own runs."
)


def can_accept_candidate(candidate: Candidate) -> tuple[bool, str]:
    """Determine whether a candidate source can be accepted for use.

    Core safety rule (parent2.md / parth2.md):
    Acceptance is strictly disabled when `usable` is False.
    Automatic safety rules (robots.txt, terms of use, public access, trust score)
    cannot be overridden by human acceptance.
    """
    if not candidate.usable:
        reasons = []
        if candidate.robots_status != "allowed":
            reasons.append(f"robots.txt status is '{candidate.robots_status}'")
        if candidate.terms_status != "ok":
            reasons.append(f"terms status is '{candidate.terms_status}' (must be positively 'ok')")
        if candidate.public_ok is False:
            reasons.append("site is not confirmed public and logged-out")
        if candidate.trust_score < 70:
            reasons.append(f"trust score ({candidate.trust_score}) is below standard threshold (70)")
        
        detail = "; ".join(reasons) if reasons else "candidate does not satisfy automated vetting criteria"
        return False, f"Acceptance disabled: {detail}."

    return True, "Candidate satisfies automated vetting criteria and may be accepted for our runs."


def build_candidate_decision(
    candidate: Candidate,
    decision_type: str,
    decided_by: str,
    note: str = "",
) -> tuple[CandidateDecision | None, str]:
    """Construct and validate a CandidateDecision model instance.

    Enforces that:
    1. Operator name (decided_by) is provided.
    2. Decision type is either 'accepted' or 'rejected'.
    3. An unusable candidate can NEVER be accepted.
    """
    operator = decided_by.strip()
    if not operator:
        return None, "Operator name is required to record a decision."

    decision_norm = decision_type.strip().lower()
    if decision_norm not in ("accepted", "rejected"):
        return None, f"Invalid decision '{decision_type}'. Must be 'accepted' or 'rejected'."

    if decision_norm == "accepted":
        allowed, reason = can_accept_candidate(candidate)
        if not allowed:
            return None, reason

    try:
        decision = CandidateDecision(
            candidate_id=candidate.candidate_id,
            decision=decision_norm,  # type: ignore[arg-type]
            decided_by=operator,
            note=note.strip(),
        )
        return decision, ""
    except ValidationError as err:
        return None, f"Validation error constructing CandidateDecision: {err}"


def filter_candidates(
    candidates: list[Candidate],
    usable_only: bool = False,
    status_filter: str | None = None,
    min_trust_score: int = 0,
    query: str | None = None,
) -> list[Candidate]:
    """Filter a list of Candidate models by usability, vetting status, score, and search query.

    Pure function: returns a new list without mutating input.
    """
    filtered: list[Candidate] = []
    q_clean = query.strip().casefold() if query else None

    for c in candidates:
        if usable_only and not c.usable:
            continue

        if status_filter and status_filter != "all" and c.status != status_filter:
            continue

        if c.trust_score < min_trust_score:
            continue

        if q_clean:
            searchable = f"{c.name} {c.domain} {c.region} {c.type_guess} {c.notes}".casefold()
            if q_clean not in searchable:
                continue

        filtered.append(c)

    return filtered


def prepare_register_rows(sources: list[Source]) -> list[dict[str, Any]]:
    """Format Source models from config/sources.yaml into clean tabular records."""
    rows: list[dict[str, Any]] = []
    for s in sources:
        is_blocked = s.vetting_status in ("blocked", "unreachable") or s.status == "blocked"
        status_icon = "🔴" if is_blocked else ("🟢" if s.vetting_status == "working" else "🟡")
        
        rows.append({
            "Source ID": s.source_id,
            "Name": s.name,
            "Type": s.type,
            "Status": s.status,
            "Vetting": f"{status_icon} {s.vetting_status}",
            "Robots": s.robots_status,
            "Terms": s.terms_status,
            "Region": s.region,
            "Access": s.access_method,
            "URL": s.url,
            "Notes": s.notes,
        })
    return rows


def prepare_candidate_rows(
    candidates: list[Candidate],
    decisions_by_id: dict[str, CandidateDecision] | None = None,
) -> list[dict[str, Any]]:
    """Format Candidate models into clean tabular records with current decision state."""
    decisions = decisions_by_id or {}
    rows: list[dict[str, Any]] = []

    for c in candidates:
        decision_obj = decisions.get(c.candidate_id)
        decision_label = decision_obj.decision.upper() if decision_obj else "NONE"
        decided_by = decision_obj.decided_by if decision_obj else "-"
        
        usable_icon = "✅ Yes" if c.usable else "❌ No"

        rows.append({
            "Candidate ID": c.candidate_id,
            "Name": c.name,
            "Domain": c.domain,
            "Type Guess": c.type_guess,
            "Region": c.region,
            "Trust Score": c.trust_score,
            "Usable": usable_icon,
            "Status": c.status,
            "Current Decision": decision_label,
            "Decided By": decided_by,
            "Discovered Via": c.discovered_via,
            "Terms Status": c.terms_status,
            "Robots Status": c.robots_status,
            "Newest Date": c.newest_item_date or "-",
        })
    return rows
