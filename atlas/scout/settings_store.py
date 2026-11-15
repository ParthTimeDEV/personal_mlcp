"""Saved scout settings, discovered candidates and the team's decisions on them (all in the Volume).

Owner: Nikhil. Paths (relative to the Volume prefix):
    settings/scout_settings.json   the saved ScoutSettings
    scout/candidates.json          list[Candidate]
    scout/decisions.json           list[CandidateDecision]

Nothing here is written to local disk. A saved file that no longer validates raises an error that names
the file: defaults are never substituted silently.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from pydantic import ValidationError

from atlas import storage
from atlas.compliance import same_site
from atlas.models import Candidate, CandidateDecision, ScoutSettings, Source

ROOT = Path(__file__).resolve().parent.parent.parent
SETTINGS_PATH = "settings/scout_settings.json"
CANDIDATES_PATH = "scout/candidates.json"
DECISIONS_PATH = "scout/decisions.json"


class StoredFileError(RuntimeError):
    """A file in the Volume exists but is not valid. Names the file and the problem."""


def default_settings(path: str = "config/scout_settings.yaml") -> ScoutSettings:
    """The defaults from the repo (these reproduce the phase 1 behaviour)."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    with open(p, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    try:
        return ScoutSettings.model_validate(data)
    except ValidationError as exc:
        raise StoredFileError(f"{path} is not a valid ScoutSettings: {exc}") from exc


def load_settings() -> ScoutSettings:
    """Saved settings if present, otherwise the defaults."""
    raw = storage.read_json_or_none(SETTINGS_PATH)
    if raw is None:
        return default_settings()
    try:
        return ScoutSettings.model_validate(raw)
    except ValidationError as exc:
        raise StoredFileError(f"{SETTINGS_PATH} in the Volume is not a valid ScoutSettings: {exc}") from exc


def save_settings(settings: ScoutSettings) -> None:
    # Re-validate so a model modified after construction cannot save invalid values.
    checked = ScoutSettings.model_validate(settings.model_dump(mode="json"))
    storage.write_json(SETTINGS_PATH, checked.model_dump(mode="json"))


def _load_list(path: str, model) -> list:
    raw = storage.read_json_or_none(path)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise StoredFileError(f"{path} in the Volume must hold a JSON list")
    try:
        return [model.model_validate(entry) for entry in raw]
    except ValidationError as exc:
        raise StoredFileError(f"{path} in the Volume is not valid: {exc}") from exc


def load_candidates() -> list[Candidate]:
    return _load_list(CANDIDATES_PATH, Candidate)


def save_candidates(candidates: list[Candidate]) -> None:
    storage.write_json(CANDIDATES_PATH, [c.model_dump(mode="json") for c in candidates])


def load_decisions() -> list[CandidateDecision]:
    return _load_list(DECISIONS_PATH, CandidateDecision)


def save_decision(decision: CandidateDecision) -> None:
    """Store a decision; it replaces an earlier decision for the same candidate."""
    kept = [d for d in load_decisions() if d.candidate_id != decision.candidate_id]
    kept.append(decision)
    storage.write_json(DECISIONS_PATH, [d.model_dump(mode="json") for d in kept])


def discovered_source_id(candidate: Candidate) -> str:
    return f"disc_{candidate.candidate_id}"


def usable_sources(settings: ScoutSettings, candidates: list[Candidate],
                   decisions: list[CandidateDecision],
                   register: list[Source] | None = None) -> list[Source]:
    """Candidates that may be used in a run, as Sources (origin="discovered", status="proposed").

    A candidate is included only if ALL of these hold: settings.use_discovered_sources; candidate.usable;
    trust_score >= settings.min_trust_score; its type is in settings.source_types; no "rejected" decision;
    and (when `register` is given) its site is not already in the register. An "accepted" decision does not
    override anything: it can never make an unusable candidate usable. Nothing here approves a source for
    Atlas Copco: status stays "proposed".
    """
    if not settings.use_discovered_sources:
        return []
    rejected = {d.candidate_id for d in decisions if d.decision == "rejected"}
    out: list[Source] = []
    seen_ids: set[str] = set()
    for c in candidates:
        if (not c.usable or c.trust_score < settings.min_trust_score
                or c.type_guess not in settings.source_types
                or c.candidate_id in rejected or c.candidate_id in seen_ids):
            continue
        if register and any(same_site(c.url, s.url) for s in register):
            continue
        seen_ids.add(c.candidate_id)
        out.append(Source(
            source_id=discovered_source_id(c), name=c.name, url=c.url, type=c.type_guess,
            access_method=c.access_method, feed_url=c.feed_url, item_url_pattern=c.item_url_pattern,
            robots_status=c.robots_status, terms_status=c.terms_status, vetting_status="working",
            status="proposed", review_date=date.today(), region=c.region, origin="discovered",
            trust_score=c.trust_score,
            notes=(f"Found by the scout engine ({c.discovered_via}); trust score {c.trust_score}. "
                   "Not approved by Atlas Copco."),
        ))
    return out
