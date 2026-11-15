"""Data access layer for the Atlas Copco Market Scout frontend.

Interfaces strictly with Databricks Volumes through atlas.storage.
Never writes data to local disk, never caches scraped text, and never hides errors.
"""

from __future__ import annotations

import re
from typing import Any
import streamlit as st
from pydantic import ValidationError

from atlas.models import Item, OutputEnvelope, RunLog
from atlas import storage


class StorageAccessError(Exception):
    """Raised when cloud storage access fails or returns unparseable content."""


def get_active_prefix() -> str:
    """Return the active ATLAS_PATH_PREFIX from environment settings."""
    try:
        return storage.get_settings().atlas_path_prefix.strip("/")
    except Exception:
        return ""


def is_demo_prefix() -> bool:
    """Return True if the active prefix is empty (meaning live demo/production Volume)."""
    return get_active_prefix() == ""


@st.cache_data(ttl=60)
def list_run_ids() -> list[str]:
    """List all available run IDs in descending chronological order (newest first).

    Finds files matching `output/poc_<run_id>.json`.
    Returns an empty list if the folder does not exist or has no runs yet.
    """
    try:
        entries = storage.list_dir("output")
    except Exception as exc:
        # If folder doesn't exist yet, return empty list gracefully
        if "NotFound" in type(exc).__name__ or "not exist" in str(exc).lower():
            return []
        raise StorageAccessError(f"Failed to access output folder in Volume: {exc}") from exc

    run_ids: list[str] = []
    pattern = re.compile(r"^poc_([0-9]{8}T[0-9]{6}Z)\.json$")
    for name in entries:
        filename = name.rstrip("/")
        match = pattern.match(filename)
        if match:
            run_ids.append(match.group(1))

    # Sort descending (ISO timestamps sort chronologically)
    return sorted(run_ids, reverse=True)


def latest_run_id() -> str | None:
    """Return the newest run_id by timestamp, or None if no runs exist."""
    runs = list_run_ids()
    return runs[0] if runs else None


@st.cache_data(ttl=60)
def load_envelope(run_id: str) -> OutputEnvelope:
    """Read and validate the OutputEnvelope for a given run_id.

    Raises StorageAccessError or ValueError with the exact file path if
    loading or validation fails. Never silently returns fake data.
    """
    path = f"output/poc_{run_id}.json"
    try:
        raw = storage.read_json(path)
    except Exception as exc:
        raise StorageAccessError(f"Could not read envelope from {path}: {exc}") from exc

    try:
        return OutputEnvelope.model_validate(raw)
    except ValidationError as err:
        raise ValueError(f"Schema validation failed for {path}: {err}") from err


@st.cache_data(ttl=60)
def load_log(run_id: str) -> RunLog | None:
    """Read and validate the RunLog for a given run_id, or None if absent."""
    path = f"logs/{run_id}.json"
    try:
        raw = storage.read_json_or_none(path)
        if raw is None:
            return None
        return RunLog.model_validate(raw)
    except Exception as exc:
        raise StorageAccessError(f"Could not read log from {path}: {exc}") from exc


@st.cache_data(ttl=60)
def load_clean_items(run_id: str) -> list[Item]:
    """Read all clean items across all sources for a given run_id.

    This includes items that failed the relevance filter, complete with their
    filter verdicts and reason codes.
    """
    try:
        source_dirs = storage.list_dir("clean")
    except Exception as exc:
        if "NotFound" in type(exc).__name__ or "not exist" in str(exc).lower():
            return []
        raise StorageAccessError(f"Failed to access clean folder in Volume: {exc}") from exc

    items: list[Item] = []
    for entry in source_dirs:
        source_id = entry.rstrip("/")
        item_path = f"clean/{source_id}/{run_id}.json"
        raw = storage.read_json_or_none(item_path)
        if raw and isinstance(raw, list):
            for raw_item in raw:
                try:
                    items.append(Item.model_validate(raw_item))
                except ValidationError as err:
                    raise ValueError(f"Schema validation failed for item in {item_path}: {err}") from err

    return items


def clear_data_cache() -> None:
    """Clear all cached data functions."""
    list_run_ids.clear()
    load_envelope.clear()
    load_log.clear()
    load_clean_items.clear()
