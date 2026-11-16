"""Human review decisions kept in the Volume: which facts are approved or denied, which sources are confirmed.

settings/fact_decisions.json       {item_id: "approved" | "denied"}
settings/source_confirmations.json {source_id: "confirmed"}

A denied fact is left out of the next run's output and of every report. An approved fact is marked important.
Confirming a source records the team's decision only; it is not an Atlas Copco approval. Nothing is written to disk.
"""
from __future__ import annotations

from atlas import storage

FACT_DECISIONS = "settings/fact_decisions.json"
SOURCE_CONFIRMATIONS = "settings/source_confirmations.json"
FACT_VALUES = {"approved", "denied"}


def _load(path: str) -> dict[str, str]:
    raw = storage.read_json_or_none(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path} in the Volume must hold a JSON object")
    return {str(k): str(v) for k, v in raw.items()}


def load_fact_decisions() -> dict[str, str]:
    return _load(FACT_DECISIONS)


def save_fact_decisions(decisions: dict[str, str]) -> None:
    bad = {v for v in decisions.values() if v not in FACT_VALUES}
    if bad:
        raise ValueError(f"fact decisions must be 'approved' or 'denied', got {sorted(bad)}")
    storage.write_json(FACT_DECISIONS, decisions)


def load_source_confirmations() -> dict[str, str]:
    return _load(SOURCE_CONFIRMATIONS)


def save_source_confirmations(confirmations: dict[str, str]) -> None:
    storage.write_json(SOURCE_CONFIRMATIONS, {k: "confirmed" for k, v in confirmations.items() if v == "confirmed"})


def without_denied(items: list, decisions: dict[str, str]) -> list:
    """The items that were not denied. Approved and undecided items stay."""
    return [i for i in items if decisions.get(i.id) != "denied"]
