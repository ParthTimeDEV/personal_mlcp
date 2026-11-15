"""Pure settings diffing and validation logic for the Settings screen.

This module is browser-independent and unit-tested offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml
from pydantic import ValidationError

from atlas.models import ScoutSettings, WatchEntry


SETTING_EXPLANATIONS: dict[str, str] = {
    "regions": "Geographic regions allowed to pass. Items outside these regions are dropped.",
    "technologies": "Compressor technologies allowed. Empty selection permits all technology types.",
    "event_types": "Corporate and industry event types permitted. Empty selection permits all events.",
    "recent_months": "Items older than this many months are dropped by the 'recent' check.",
    "extra_compressor_keywords": "Additional terms that count as compressor keyword matches.",
    "excluded_keywords": "Articles containing any of these keywords in title or facts are dropped.",
    "require_industrial": "When enabled, items without clear industrial context are dropped.",
    "source_types": "Allowed publisher types (competitor newsroom, trade publication, government).",
    "use_discovered_sources": "Include eligible automatically vetted discovered sources in the run.",
    "min_trust_score": "Minimum automated vetting score (0-100) required for discovered sources.",
    "max_items_per_source": "Maximum pages/items to collect per source in a normal run.",
    "discovery_enabled": "Automatically scout for new source candidates during the run.",
    "fallback_enabled": "When a source is blocked, collect news about it from other allowed sources.",
    "fallback_max_items_per_source": "Maximum items to collect per source during fallback switching.",
    "watchlist": "Companies and products to follow through secondary sources when primary is refused.",
}


def settings_diff(current: ScoutSettings, defaults: ScoutSettings) -> list[tuple[str, object, object]]:
    """Compare two ScoutSettings objects and return a list of differences.

    Each difference is represented as a tuple: (field_name, default_value, current_value).
    Pure function: handles scalars, list collections, and nested WatchEntry objects.
    """
    diffs: list[tuple[str, object, object]] = []

    for field_name in ScoutSettings.model_fields.keys():
        curr_val = getattr(current, field_name)
        def_val = getattr(defaults, field_name)

        if field_name == "watchlist":
            curr_list = [w.model_dump() if isinstance(w, WatchEntry) else w for w in curr_val]
            def_list = [w.model_dump() if isinstance(w, WatchEntry) else w for w in def_val]
            if curr_list != def_list:
                diffs.append((field_name, def_val, curr_val))
        elif isinstance(curr_val, list):
            # Order-preserving list comparison
            if curr_val != def_val:
                diffs.append((field_name, def_val, curr_val))
        else:
            if curr_val != def_val:
                diffs.append((field_name, def_val, curr_val))

    return diffs


def build_scout_settings(form_data: dict[str, Any]) -> tuple[ScoutSettings | None, dict[str, str]]:
    """Construct and validate a ScoutSettings instance from form inputs.

    Returns:
        (settings, {}) if validation succeeds.
        (None, field_errors) where field_errors maps field names to readable error strings.
    """
    cleaned_data: dict[str, Any] = dict(form_data)

    # Clean string lists (e.g. tag inputs)
    for list_field in ["extra_compressor_keywords", "excluded_keywords"]:
        val = cleaned_data.get(list_field)
        if isinstance(val, str):
            cleaned_data[list_field] = [line.strip() for line in val.splitlines() if line.strip()]
        elif isinstance(val, list):
            cleaned_data[list_field] = [str(x).strip() for x in val if str(x).strip()]

    try:
        settings = ScoutSettings.model_validate(cleaned_data)
        return settings, {}
    except ValidationError as exc:
        field_errors: dict[str, str] = {}
        for err in exc.errors():
            loc = err["loc"]
            field_key = str(loc[0]) if loc else "general"
            msg = err["msg"]
            field_errors[field_key] = msg
        return None, field_errors


def load_technology_labels(path: str = "config/technologies.yaml") -> list[str]:
    """Read config/technologies.yaml and return unique technology labels in order."""
    p = Path(path)
    if not p.is_absolute():
        root = Path(__file__).resolve().parent.parent.parent
        p = root / p

    if not p.exists():
        return []

    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or []
        labels: list[str] = []
        for entry in data:
            if isinstance(entry, dict) and "label" in entry:
                label = str(entry["label"]).strip()
                if label and label not in labels:
                    labels.append(label)
        return labels
    except Exception:
        return []


def format_watchlist_for_editor(watchlist: list[WatchEntry | dict]) -> list[dict[str, Any]]:
    """Format WatchEntry items into list of dicts suitable for st.data_editor."""
    rows: list[dict[str, Any]] = []
    for entry in watchlist:
        if isinstance(entry, WatchEntry):
            name = entry.name
            kind = entry.kind
            aliases = ", ".join(entry.aliases)
            follow = entry.follow_when_blocked
        elif isinstance(entry, dict):
            name = entry.get("name", "")
            kind = entry.get("kind", "company")
            raw_aliases = entry.get("aliases", [])
            aliases = ", ".join(raw_aliases) if isinstance(raw_aliases, list) else str(raw_aliases)
            follow = entry.get("follow_when_blocked", True)
        else:
            continue
        rows.append({
            "name": name,
            "kind": kind,
            "aliases": aliases,
            "follow_when_blocked": follow,
        })
    return rows


def parse_watchlist_from_editor(rows: list[dict[str, Any]]) -> tuple[list[WatchEntry], list[str]]:
    """Parse edited rows back into validated WatchEntry items and error messages."""
    entries: list[WatchEntry] = []
    errors: list[str] = []

    for idx, row in enumerate(rows):
        name = str(row.get("name") or "").strip()
        if not name:
            errors.append(f"Row {idx + 1}: Name cannot be empty.")
            continue

        kind = str(row.get("kind") or "company").strip()
        if kind not in ("company", "product", "technology"):
            errors.append(f"Row {idx + 1} ({name}): Invalid kind '{kind}'. Must be 'company', 'product', or 'technology'.")
            continue

        raw_aliases = row.get("aliases", "")
        if isinstance(raw_aliases, str):
            aliases = [a.strip() for a in raw_aliases.split(",") if a.strip()]
        elif isinstance(raw_aliases, list):
            aliases = [str(a).strip() for a in raw_aliases if str(a).strip()]
        else:
            aliases = []

        follow = bool(row.get("follow_when_blocked", True))

        try:
            entry = WatchEntry(name=name, kind=kind, aliases=aliases, follow_when_blocked=follow)
            entries.append(entry)
        except ValidationError as err:
            errors.append(f"Row {idx + 1} ({name}): {err}")

    return entries, errors


def format_diff_summary(diffs: list[tuple[str, object, object]]) -> list[dict[str, str]]:
    """Format settings differences for display as 'field: default -> current'."""
    formatted: list[dict[str, str]] = []
    for field_name, def_val, curr_val in diffs:
        if field_name == "watchlist":
            def_count = len(def_val) if isinstance(def_val, list) else 0
            curr_count = len(curr_val) if isinstance(curr_val, list) else 0
            def_str = f"{def_count} entries"
            curr_str = f"{curr_count} entries"
        elif isinstance(def_val, list) or isinstance(curr_val, list):
            def_str = f"[{', '.join(str(x) for x in (def_val or []))}]"
            curr_str = f"[{', '.join(str(x) for x in (curr_val or []))}]"
        else:
            def_str = str(def_val)
            curr_str = str(curr_val)

        formatted.append({
            "field": field_name,
            "default": def_str,
            "current": curr_str,
            "display": f"**{field_name}**: `{def_str}` → `{curr_str}`",
        })
    return formatted

