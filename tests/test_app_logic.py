"""Offline unit tests for frontend logic (app/lib/).

Tests run completely offline using mocks and synthetic fixture data.
Zero Databricks network calls; zero local data file writes.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from atlas.models import (
    Candidate,
    CandidateDecision,
    Item,
    OutputEnvelope,
    ScoutSettings,
    Source,
    WatchEntry,
)
from app.lib.sources import (
    DISCLAIMER_TEXT,
    build_candidate_decision,
    can_accept_candidate,
    filter_candidates,
    prepare_candidate_rows,
    prepare_register_rows,
)
from app.lib.report import (
    FORMAT_LABELS,
    FORMAT_MIME_TYPES,
    extract_report_preview_metrics,
    find_existing_reports,
    generate_report_bytes,
    get_report_filename,
    get_report_mime_type,
    get_report_relative_path,
    validate_report_format,
)
from app.lib.dashboard import (
    compute_run_metrics,
    get_other_story_items,
    prepare_chart_data,
    prepare_items_csv,
    prepare_sources_summary,
    prepare_stories_view,
)
from app.lib.data import (
    StorageAccessError,
    clear_data_cache,
    get_active_prefix,
    is_demo_prefix,
    latest_run_id,
    list_run_ids,
    load_clean_items,
    load_envelope,
    load_log,
)
from app.lib.filters import (
    REASON_LABELS,
    ItemFilters,
    explain_reasons,
    filter_items,
    parse_reason_label,
)
from app.lib.runner import (
    RunProgressTracker,
    build_run_args,
    extract_errors_from_output,
    extract_run_id_from_output,
    parse_progress_line,
    sanitize_output_line,
    start_run,
    terminate_process,
)
from app.lib.settings_ui import (
    SETTING_EXPLANATIONS,
    build_scout_settings,
    format_diff_summary,
    format_watchlist_for_editor,
    load_technology_labels,
    parse_watchlist_from_editor,
    settings_diff,
)
from atlas.scout import settings_store

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_output.json"


@pytest.fixture
def sample_envelope() -> OutputEnvelope:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return OutputEnvelope.model_validate(data)


@pytest.fixture
def sample_items_dict(sample_envelope: OutputEnvelope) -> list[dict]:
    return [item.model_dump(mode="json") for item in sample_envelope.items]


@pytest.fixture(autouse=True)
def reset_streamlit_cache():
    """Ensure every test runs with an isolated, clean Streamlit cache state."""
    clear_data_cache()
    yield
    clear_data_cache()


# ==============================================================================
# 1. Data Layer Tests (Mocks, No Cloud Access)
# ==============================================================================

def test_get_active_prefix_and_is_demo():
    with patch("atlas.storage.get_settings") as mock_settings:
        mock_settings.return_value.atlas_path_prefix = "dev/parth"
        assert get_active_prefix() == "dev/parth"
        assert not is_demo_prefix()

        mock_settings.return_value.atlas_path_prefix = ""
        assert get_active_prefix() == ""
        assert is_demo_prefix()


def test_list_run_ids_sorted_and_latest():
    with patch("atlas.storage.list_dir") as mock_list:
        mock_list.return_value = [
            "poc_20261114T100000Z.json",
            "poc_20261115T045141Z.json",
            "other_file.txt",
            "poc_20261115T020000Z.json",
        ]
        runs = list_run_ids()
        assert runs == ["20261115T045141Z", "20261115T020000Z", "20261114T100000Z"]
        assert latest_run_id() == "20261115T045141Z"


def test_list_run_ids_empty_or_not_found():
    with patch("atlas.storage.list_dir") as mock_list:
        mock_list.return_value = []
        assert list_run_ids() == []
        assert latest_run_id() is None

        class MockNotFound(Exception):
            pass

        clear_data_cache()
        mock_list.side_effect = MockNotFound("Folder not found")
        assert list_run_ids() == []
        assert latest_run_id() is None


def test_list_run_ids_storage_error_surfaced():
    with patch("atlas.storage.list_dir") as mock_list:
        mock_list.side_effect = RuntimeError("Databricks connection refused")
        with pytest.raises(StorageAccessError, match="Failed to access output folder"):
            list_run_ids()


def test_load_envelope_success(sample_envelope: OutputEnvelope):
    with patch("atlas.storage.read_json") as mock_read:
        mock_read.return_value = sample_envelope.model_dump(mode="json")
        loaded = load_envelope("20261115T045141Z")
        assert loaded.run_id == sample_envelope.run_id
        assert len(loaded.items) == len(sample_envelope.items)


def test_load_envelope_validation_failure():
    with patch("atlas.storage.read_json") as mock_read:
        mock_read.return_value = {"invalid": "schema"}
        with pytest.raises(ValueError, match="output/poc_test_run.json"):
            load_envelope("test_run")


def test_load_log_none_and_present():
    with patch("atlas.storage.read_json_or_none") as mock_read:
        mock_read.return_value = None
        assert load_log("test_run") is None

        clear_data_cache()
        mock_read.return_value = {
            "run_id": "test_run",
            "started_at": "2026-11-15T00:00:00Z",
            "errors": [],
            "notes": ["Phase 2 discovery started"],
        }
        log = load_log("test_run")
        assert log is not None
        assert log.run_id == "test_run"
        assert "Phase 2 discovery started" in log.notes


def test_load_clean_items():
    with patch("atlas.storage.list_dir") as mock_list, patch("atlas.storage.read_json_or_none") as mock_read:
        mock_list.return_value = ["airbestpractices_news/", "quincy_compressor_blog/"]
        
        item_data = {
            "id": "abc123456789",
            "source_id": "airbestpractices_news",
            "source_name": "Air Best Practices",
            "source_type": "trade_news",
            "source_url": "https://example.com/item1",
            "licence_note": "Public web page; facts and links only",
            "collected_at": "2026-11-15T04:00:00Z",
            "page_fingerprint": "abc123def4567890abc123def4567890abc123def4567890abc123def4567890",
            "title": "New Industrial Compressor",
            "key_facts": ["Fact 1", "Fact 2"],
            "label": "fact",
            "filter": {
                "compressor_related": True,
                "north_america": True,
                "credible_source": True,
                "recent": False,
                "passed": False,
                "reasons": ["too_old"],
            },
        }

        mock_read.side_effect = lambda path: [item_data] if "airbestpractices" in path else []

        items = load_clean_items("20261115T045141Z")
        assert len(items) == 1
        assert items[0].id == "abc123456789"
        assert items[0].source_name == "Air Best Practices"
        assert items[0].filter is not None
        assert items[0].filter.passed is False
        assert "too_old" in items[0].filter.reasons


# ==============================================================================
# 2. Item Filtering & Sorting Tests (Pure Logic)
# ==============================================================================

def test_filter_by_source_id(sample_items_dict: list[dict]):
    src = sample_items_dict[0]["source_id"]
    res = filter_items(sample_items_dict, ItemFilters(source_id=src))
    assert all(i["source_id"] == src for i in res)
    assert len(res) > 0


def test_filter_by_source_type(sample_items_dict: list[dict]):
    res = filter_items(sample_items_dict, ItemFilters(source_type="competitor"))
    assert all(i["source_type"] == "competitor" for i in res)


def test_filter_by_label(sample_items_dict: list[dict]):
    facts = filter_items(sample_items_dict, ItemFilters(label="fact"))
    assert all(i["label"] == "fact" for i in facts)

    claims = filter_items(sample_items_dict, ItemFilters(label="claim"))
    assert all(i["label"] == "claim" for i in claims)


def test_filter_by_passed_status(sample_items_dict: list[dict]):
    # In sample_output envelope, all items have filter.passed = True
    passed_items = filter_items(sample_items_dict, ItemFilters(passed=True))
    assert len(passed_items) == len(sample_items_dict)

    failed_items = filter_items(sample_items_dict, ItemFilters(passed=False))
    assert len(failed_items) == 0


def test_filter_by_company(sample_items_dict: list[dict]):
    res = filter_items(sample_items_dict, ItemFilters(company="Kaeser"))
    assert all("kaeser" in (i.get("company") or "").lower() for i in res)


def test_filter_by_technology(sample_items_dict: list[dict]):
    sample_tech = next(i.get("technology") for i in sample_items_dict if i.get("technology"))
    res = filter_items(sample_items_dict, ItemFilters(technology=sample_tech))
    assert all(i.get("technology", "").lower() == sample_tech.lower() for i in res)


def test_filter_by_event_type(sample_items_dict: list[dict]):
    res = filter_items(sample_items_dict, ItemFilters(event_type="product_launch"))
    assert all(i.get("event_type") == "product_launch" for i in res)


def test_filter_by_region(sample_items_dict: list[dict]):
    res = filter_items(sample_items_dict, ItemFilters(region="US"))
    assert all(i.get("region") == "US" for i in res)


def test_filter_by_date_range(sample_items_dict: list[dict]):
    res = filter_items(sample_items_dict, ItemFilters(date_from="2026-01-01", date_to="2026-12-31"))
    assert all("2026-01-01" <= (i.get("published_at") or "")[:10] <= "2026-12-31" for i in res)


def test_filter_by_fallback_only(sample_items_dict: list[dict]):
    fallback_items = filter_items(sample_items_dict, ItemFilters(via_fallback_only=True))
    assert all(i.get("via_fallback") is True for i in fallback_items)
    assert len(fallback_items) >= 1


def test_filter_free_text_query(sample_items_dict: list[dict]):
    query = "compressor"
    res = filter_items(sample_items_dict, ItemFilters(query=query))
    assert len(res) > 0
    for i in res:
        title = (i.get("title") or "").lower()
        facts = " ".join([kf if isinstance(kf, str) else kf.get("text", "") for kf in i.get("key_facts", [])]).lower()
        assert query in title or query in facts


def test_filter_combinations_and_empty(sample_items_dict: list[dict]):
    res = filter_items(
        sample_items_dict,
        ItemFilters(
            region="US",
            label="claim",
            query="nonexistent_xyz_keyword_12345",
        ),
    )
    assert len(res) == 0


def test_sorting(sample_items_dict: list[dict]):
    by_comp = filter_items(sample_items_dict, ItemFilters(sort_by="company", sort_desc=False))
    companies = [(i.get("company") or "").lower() for i in by_comp]
    assert companies == sorted(companies)


def test_all_filter_reason_codes_have_labels():
    expected_codes = [
        "no_compressor_keyword",
        "not_north_america",
        "source_not_credible",
        "date_missing",
        "date_in_future",
        "too_old",
        "region_not_selected",
        "technology_not_selected",
        "event_type_not_selected",
        "excluded_keyword",
        "not_industrial",
        "source_type_not_selected",
        "fallback_forbidden_route",
    ]
    for code in expected_codes:
        assert code in REASON_LABELS
        label = parse_reason_label(code)
        assert len(label) > 10
        assert not label.startswith("Failed check:")

    # Batch explanation test
    explained = explain_reasons(["no_compressor_keyword", "too_old"])
    assert len(explained) == 2
    assert "No compressor-related keyword" in explained[0]
    assert "Published outside" in explained[1]


# ==============================================================================
# 3. Settings UI Logic Tests
# ==============================================================================

def test_settings_diff_identical():
    s1 = ScoutSettings()
    s2 = ScoutSettings()
    diffs = settings_diff(s1, s2)
    assert diffs == []


def test_settings_diff_scalars_and_lists():
    defaults = ScoutSettings()
    modified = ScoutSettings(
        recent_months=24,
        require_industrial=True,
        regions=["US", "CA"],
        extra_compressor_keywords=["screw blower"],
    )
    diffs = settings_diff(modified, defaults)
    diff_keys = [d[0] for d in diffs]
    assert "recent_months" in diff_keys
    assert "require_industrial" in diff_keys
    assert "regions" in diff_keys
    assert "extra_compressor_keywords" in diff_keys


def test_settings_diff_watchlist():
    defaults = ScoutSettings(
        watchlist=[WatchEntry(name="Kaeser", kind="company", aliases=["Kaeser Compressors"])]
    )
    modified = ScoutSettings(
        watchlist=[
            WatchEntry(name="Kaeser", kind="company", aliases=["Kaeser Compressors"]),
            WatchEntry(name="Sullair", kind="company", aliases=[]),
        ]
    )
    diffs = settings_diff(modified, defaults)
    diff_keys = [d[0] for d in diffs]
    assert "watchlist" in diff_keys


def test_build_scout_settings_valid():
    form_data = {
        "regions": ["US", "CA"],
        "recent_months": 18,
        "require_industrial": True,
        "extra_compressor_keywords": "screw air\ndesiccant dryer\n",
        "min_trust_score": 80,
    }
    settings, errors = build_scout_settings(form_data)
    assert errors == {}
    assert settings is not None
    assert settings.regions == ["US", "CA"]
    assert settings.recent_months == 18
    assert settings.require_industrial is True
    assert settings.extra_compressor_keywords == ["screw air", "desiccant dryer"]
    assert settings.min_trust_score == 80


def test_build_scout_settings_invalid():
    form_data = {
        "recent_months": 120,  # Invalid: ge=1, le=60
        "min_trust_score": -10,  # Invalid: ge=0, le=100
    }
    settings, errors = build_scout_settings(form_data)
    assert settings is None
    assert "recent_months" in errors
    assert "min_trust_score" in errors


def test_load_technology_labels():
    labels = load_technology_labels()
    assert isinstance(labels, list)
    assert len(labels) >= 10
    assert "hydrogen compression" in labels
    assert "rotary screw compressor" in labels


def test_watchlist_editor_formatting_and_parsing():
    entries = [
        WatchEntry(name="Kaeser", kind="company", aliases=["Kaeser Compressors"], follow_when_blocked=True),
        WatchEntry(name="Sullair", kind="company", aliases=["Hitachi"], follow_when_blocked=False),
    ]
    # Format for UI
    rows = format_watchlist_for_editor(entries)
    assert len(rows) == 2
    assert rows[0]["name"] == "Kaeser"
    assert rows[0]["aliases"] == "Kaeser Compressors"
    assert rows[1]["follow_when_blocked"] is False

    # Simulate user adding a row and editing
    rows.append({
        "name": "Gardner Denver",
        "kind": "company",
        "aliases": "GD, Gardner",
        "follow_when_blocked": True,
    })
    rows[1]["aliases"] = "Hitachi, Hitachi Global"

    parsed, errors = parse_watchlist_from_editor(rows)
    assert errors == []
    assert len(parsed) == 3
    assert parsed[2].name == "Gardner Denver"
    assert parsed[1].aliases == ["Hitachi", "Hitachi Global"]

    # Simulate deletion of row 0
    del rows[0]
    parsed_after_delete, _ = parse_watchlist_from_editor(rows)
    assert len(parsed_after_delete) == 2
    assert parsed_after_delete[0].name == "Sullair"


def test_parse_watchlist_invalid_rows():
    bad_rows = [
        {"name": "", "kind": "company", "aliases": ""},  # Empty name
        {"name": "Valid Name", "kind": "unsupported_kind", "aliases": ""},  # Invalid kind
    ]
    parsed, errors = parse_watchlist_from_editor(bad_rows)
    assert len(errors) == 2
    assert "Name cannot be empty" in errors[0]
    assert "Invalid kind" in errors[1]


def test_format_diff_summary():
    defaults = ScoutSettings()
    modified = ScoutSettings(
        recent_months=24,
        regions=["US", "CA"],
        require_industrial=True,
    )
    diffs = settings_diff(modified, defaults)
    summary = format_diff_summary(diffs)
    assert len(summary) == 3
    fields = [s["field"] for s in summary]
    assert "recent_months" in fields
    assert "regions" in fields
    assert "require_industrial" in fields
    for s in summary:
        assert "display" in s
        assert "→" in s["display"]


def test_load_settings_saved_vs_defaults():
    # 1. When storage returns None -> returns defaults
    with patch("atlas.storage.read_json_or_none") as mock_read:
        mock_read.return_value = None
        s = settings_store.load_settings()
        assert s.recent_months == 12
        assert s.regions == settings_store.default_settings().regions

    # 2. When storage returns saved settings
    with patch("atlas.storage.read_json_or_none") as mock_read:
        mock_read.return_value = {
            "regions": ["US", "CA"],
            "recent_months": 36,
            "require_industrial": True,
        }
        s = settings_store.load_settings()
        assert s.recent_months == 36
        assert s.regions == ["US", "CA"]
        assert s.require_industrial is True


def test_save_settings_store_mock():
    s = ScoutSettings(recent_months=18, require_industrial=True)
    with patch("atlas.storage.write_json") as mock_write:
        settings_store.save_settings(s)
        assert mock_write.called
        path, payload = mock_write.call_args[0]
        assert path == "settings/scout_settings.json"
        assert payload["recent_months"] == 18
        assert payload["require_industrial"] is True


def test_reset_confirmation_logic():
    # Verify default_settings loads correctly from config file
    defaults = settings_store.default_settings()
    assert isinstance(defaults, ScoutSettings)
    assert defaults.recent_months == 12
    assert len(defaults.watchlist) >= 5



# ==============================================================================
# 4. Runner & Security Tests
# ==============================================================================

def test_start_run_command_construction():
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        proc = start_run(["--max-items", "5", "--no-discovery"])
        assert mock_popen.called
        call_args = mock_popen.call_args[0][0]
        assert "-u" in call_args
        assert "-m" in call_args
        assert "atlas.run" in call_args
        assert "--max-items" in call_args
        assert "5" in call_args


def test_start_run_security_blocks_token_in_arguments():
    with pytest.raises(ValueError, match="Security violation: suspicious argument blocked"):
        start_run(["--token=dapi123456789"])


def test_parse_progress_line():
    # Source start
    p1 = parse_progress_line("[2/5] quincy_compressor_blog")
    assert p1 is not None
    assert p1["type"] == "source_start"
    assert p1["current"] == 2
    assert p1["total"] == 5
    assert p1["source_id"] == "quincy_compressor_blog"
    assert p1["progress_percent"] == 0.4

    # Refusal
    p2 = parse_progress_line("  refused by the compliance gate: terms_forbid_automation")
    assert p2 is not None
    assert p2["type"] == "source_refused"
    assert "terms_forbid_automation" in p2["reasons"]

    # Collection
    p3 = parse_progress_line("  collected 7 page(s) of 10 listed")
    assert p3 is not None
    assert p3["type"] == "collection"
    assert p3["pages_collected"] == 7

    # Done filter
    p4 = parse_progress_line("  done: 4 of 7 item(s) passed the filter")
    assert p4 is not None
    assert p4["type"] == "source_done"
    assert p4["passed"] == 4
    assert p4["total"] == 7

    # Run ID announcement
    p5 = parse_progress_line("Run 20261115T045141Z starting. Connecting to Databricks...")
    assert p5 is not None
    assert p5["type"] == "run_id"
    assert p5["run_id"] == "20261115T045141Z"


def test_extract_run_id_from_output():
    text = "Starting session...\nRun 20261115T045141Z starting.\nDone."
    assert extract_run_id_from_output(text) == "20261115T045141Z"
    assert extract_run_id_from_output("no run id here") is None

    # Test explicit summary run_id line
    text_summary = "=== Run 20261115T045141Z ===\noutput validated: PASS\nrun_id: 20261115T045141Z"
    assert extract_run_id_from_output(text_summary) == "20261115T045141Z"


def test_build_run_args():
    # Defaults
    assert build_run_args() == []
    assert build_run_args(only_source="All Sources") == []
    assert build_run_args(only_source="all") == []
    assert build_run_args(only_source="") == []

    # Specific source
    assert build_run_args(only_source="quincy_blog") == ["--only", "quincy_blog"]

    # Max items
    assert build_run_args(max_items=15) == ["--max-items", "15"]

    # Flags
    assert build_run_args(use_default_settings=True) == ["--use-default-settings"]
    assert build_run_args(no_discovery=True) == ["--no-discovery"]
    assert build_run_args(no_fallback=True) == ["--no-fallback"]

    # Combined
    combined = build_run_args(
        only_source="kaeser_news",
        max_items=10,
        use_default_settings=True,
        no_discovery=True,
        no_fallback=True,
    )
    assert combined == [
        "--only", "kaeser_news",
        "--max-items", "10",
        "--use-default-settings",
        "--no-discovery",
        "--no-fallback",
    ]


def test_build_run_args_validation():
    with pytest.raises(ValueError, match="max_items must be a positive integer"):
        build_run_args(max_items=0)

    with pytest.raises(ValueError, match="max_items must be a positive integer"):
        build_run_args(max_items=-5)

    with pytest.raises(ValueError, match="Invalid characters in source_id"):
        build_run_args(only_source="source; rm -rf /")

    with pytest.raises(ValueError, match="Suspicious source identifier"):
        build_run_args(only_source="source_token_dapi")


def test_terminate_process():
    # Already terminated process
    proc_done = MagicMock()
    proc_done.poll.return_value = 0
    assert terminate_process(proc_done) is True
    assert not proc_done.terminate.called

    # Running process terminates cleanly
    proc_running = MagicMock()
    proc_running.poll.return_value = None
    proc_running.wait.return_value = 0
    assert terminate_process(proc_running) is True
    assert proc_running.terminate.called

    # Process times out on terminate and gets killed
    proc_hang = MagicMock()
    proc_hang.poll.return_value = None
    import subprocess
    proc_hang.wait.side_effect = [subprocess.TimeoutExpired(cmd="test", timeout=1), 0]
    assert terminate_process(proc_hang) is True
    assert proc_hang.terminate.called
    assert proc_hang.kill.called

    # ProcessLookupError handled cleanly
    proc_vanished = MagicMock()
    proc_vanished.poll.return_value = None
    proc_vanished.terminate.side_effect = ProcessLookupError()
    assert terminate_process(proc_vanished) is True


def test_sanitize_output_line():
    assert sanitize_output_line("Regular output line") == "Regular output line"
    assert sanitize_output_line("") == ""
    # Token in assignment
    redacted1 = sanitize_output_line("Connecting with token: secret12345 to volume")
    assert "[REDACTED]" in redacted1
    assert "secret12345" not in redacted1
    # DAPI token pattern
    redacted2 = sanitize_output_line("Using dapi1234567890abcdef12345678 for access")
    assert "[REDACTED_TOKEN]" in redacted2
    assert "dapi1234567890abcdef12345678" not in redacted2


def test_parse_progress_line_extended():
    assert parse_progress_line("") is None
    assert parse_progress_line("   ") is None
    assert parse_progress_line("unrecognized random line") is None

    # Source allowed
    p_allowed = parse_progress_line("  allowed; fetching up to 20 pages (3 s between requests)...")
    assert p_allowed is not None
    assert p_allowed["type"] == "source_allowed"

    # Explicit run_id:
    p_run = parse_progress_line("run_id: 20261115T120000Z")
    assert p_run is not None
    assert p_run["type"] == "run_id"
    assert p_run["run_id"] == "20261115T120000Z"

    # Stage lines
    p_disc = parse_progress_line("Discovery: looking for new candidate sources (public pages)...")
    assert p_disc is not None
    assert p_disc["stage"] == "discovery"

    p_disc_sum = parse_progress_line("  discovery: 4 candidate(s) found, 3 vetted, 2 usable")
    assert p_disc_sum is not None
    assert p_disc_sum["found"] == 4
    assert p_disc_sum["vetted"] == 3
    assert p_disc_sum["usable"] == 2

    p_switch = parse_progress_line("Switching: 2 source(s) gave no usable coverage...")
    assert p_switch is not None
    assert p_switch["stage"] == "switching"

    p_switched = parse_progress_line("  Switched: refused_src -> 3 item(s) from 2 other source(s)")
    assert p_switched is not None
    assert p_switched["type"] == "switched"

    # Validation & local data check
    p_val = parse_progress_line("output validated: PASS")
    assert p_val is not None
    assert p_val["status"] == "PASS"

    p_local = parse_progress_line("local data check: PASS")
    assert p_local is not None
    assert p_local["status"] == "PASS"

    # Errors
    p_err1 = parse_progress_line("Cannot start: settings could not be loaded: file missing")
    assert p_err1 is not None
    assert p_err1["type"] == "error"

    p_err2 = parse_progress_line("  discovery ERROR: ConnectionReset: remote host closed connection")
    assert p_err2 is not None
    assert p_err2["type"] == "error"


def test_extract_errors_from_output():
    text = (
        "Run 20261115T120000Z starting...\n"
        "Errors:\n"
        "  - source_a: TimeoutError: request timed out\n"
        "  - source_b: HTTP 500: Server Error\n"
        "Written to Databricks:\n"
        "  output/poc_20261115T120000Z.json\n"
    )
    errors = extract_errors_from_output(text)
    assert len(errors) == 2
    assert "source_a: TimeoutError: request timed out" in errors
    assert "source_b: HTTP 500: Server Error" in errors

    fatal_text = "Cannot start: ComplianceGate initialization failed\n"
    assert "Cannot start: ComplianceGate initialization failed" in extract_errors_from_output(fatal_text)


def test_run_progress_tracker_lifecycle():
    tracker = RunProgressTracker()
    assert tracker.stage == "Initializing"
    assert tracker.progress_percent == 0.0

    # Process run starting
    tracker.process_line("Run 20261115T140000Z starting. Connecting to Databricks...")
    assert tracker.run_id == "20261115T140000Z"

    # Discovery stage
    tracker.process_line("Discovery: looking for new candidate sources...")
    assert tracker.stage == "Source Discovery"

    # Source 1 start
    tracker.process_line("[1/2] source_alpha")
    assert tracker.stage == "Collection & Extraction"
    assert tracker.current_source == "source_alpha"
    assert tracker.source_index == 1
    assert tracker.total_sources == 2
    assert tracker.progress_percent == 0.5
    assert tracker.sources_status["source_alpha"]["status"] == "processing"

    # Source 1 collection and filter
    tracker.process_line("  collected 5 page(s) of 10 listed")
    assert tracker.sources_status["source_alpha"]["collected"] == 5
    tracker.process_line("  done: 3 of 5 item(s) passed the filter")
    assert tracker.sources_status["source_alpha"]["passed"] == 3
    assert tracker.sources_status["source_alpha"]["status"] == "passed"

    # Source 2 refused
    tracker.process_line("[2/2] source_beta")
    tracker.process_line("  refused by the compliance gate: robots disallow")
    assert tracker.sources_status["source_beta"]["status"] == "refused"
    assert "robots disallow" in tracker.sources_status["source_beta"]["note"]

    # Switching stage
    tracker.process_line("Switching: 1 source(s) gave no usable coverage...")
    assert tracker.stage == "Fallback Switching"

    # Validation
    tracker.process_line("output validated: PASS")
    assert tracker.output_validated is True
    assert tracker.stage == "Finalizing"

    tracker.process_line("local data check: PASS")
    assert tracker.local_data_check is True

    # Check that lines are preserved and sanitized
    assert len(tracker.lines) >= 8


# ==============================================================================
# 5. Dashboard Logic & Data Preparation Tests
# ==============================================================================

def test_compute_run_metrics(sample_envelope: OutputEnvelope):
    metrics = compute_run_metrics(sample_envelope)
    assert metrics["run_id"] == "20261029T101500Z"
    assert metrics["scope_tech"] == "industrial compressors"
    assert metrics["scope_region"] == "US+CA"
    assert metrics["collected_count"] == 28
    assert metrics["passed_count"] == 11
    assert metrics["dropped_count"] == 17
    assert metrics["stories_count"] == len(sample_envelope.stories)
    assert metrics["refused_sources_count"] == 1  # demo_summit_news
    assert metrics["fallback_items_count"] == 1  # 1 via_fallback item
    assert metrics["candidates_considered"] == 4


def test_compute_run_metrics_with_clean_items(sample_envelope: OutputEnvelope, sample_items_dict: list[dict]):
    clean_sample = list(sample_items_dict)
    # Add one failed item to clean items
    failed_item = dict(sample_items_dict[0])
    failed_item["id"] = "failed_123"
    failed_item["filter"] = {
        "compressor_related": False,
        "north_america": True,
        "credible_source": True,
        "recent": True,
        "passed": False,
        "reasons": ["no_compressor_keyword"],
    }
    clean_sample.append(failed_item)

    metrics = compute_run_metrics(sample_envelope, clean_items=clean_sample)
    assert metrics["collected_count"] == len(clean_sample)
    assert metrics["passed_count"] == len(sample_items_dict)
    assert metrics["dropped_count"] == 1


def test_compute_run_metrics_empty():
    empty_env = OutputEnvelope(
        run_id="20261115T000000Z",
        generated_at="2026-11-15T00:00:00Z",
        sources=[],
        items=[],
        stories=[],
    )
    metrics = compute_run_metrics(empty_env)
    assert metrics["collected_count"] == 0
    assert metrics["passed_count"] == 0
    assert metrics["dropped_count"] == 0
    assert metrics["stories_count"] == 0
    assert metrics["refused_sources_count"] == 0
    assert metrics["fallback_items_count"] == 0


def test_prepare_sources_summary(sample_envelope: OutputEnvelope):
    summary = prepare_sources_summary(sample_envelope.sources)
    assert len(summary) == len(sample_envelope.sources)

    # Discovered source badging
    disc_row = next(r for r in summary if r["source_id"] == "disc_0a1b2c3d4e5f")
    assert disc_row["kind_label"] == "Discovered (Not Approved)"
    assert disc_row["kind"] == "discovered"

    # Fallback source classification
    fallback_row = next(r for r in summary if r["kind"] == "fallback")
    assert "Fallback" in fallback_row["kind_label"]
    assert fallback_row["fallback_for"] == "demo_summit_news"

    # Refused source highlighting
    refused_row = next(r for r in summary if r["source_id"] == "demo_summit_news")
    assert refused_row["is_refused"] is True
    assert "refused" in refused_row["note"].lower()

    # Normal working source
    normal_row = next(r for r in summary if r["source_id"] == "demo_trade_news")
    assert normal_row["is_refused"] is False
    assert normal_row["kind_label"] == "Registered"


def test_prepare_stories_view(sample_envelope: OutputEnvelope, sample_items_dict: list[dict]):
    items_by_id = {i["id"]: i for i in sample_items_dict}
    stories = prepare_stories_view(sample_envelope.stories, items_by_id)
    assert len(stories) == len(sample_envelope.stories)

    # Multi-source story must be prioritized first
    assert stories[0]["is_multi_source"] is True
    assert stories[0]["source_count"] >= 2
    assert len(stories[0]["source_ids"]) >= 2
    assert len(stories[0]["items"]) > 0


def test_prepare_stories_view_empty():
    stories = prepare_stories_view([], {})
    assert stories == []


def test_prepare_chart_data(sample_items_dict: list[dict]):
    charts = prepare_chart_data(sample_items_dict)
    assert "items_per_source" in charts
    assert "top_companies" in charts
    assert "items_per_event_type" in charts
    assert "items_per_month" in charts

    # Check aggregation correctness
    assert sum(charts["items_per_source"].values()) == len(sample_items_dict)
    assert len(charts["top_companies"]) <= 10
    assert "2026-10" in charts["items_per_month"]


def test_prepare_chart_data_empty():
    charts = prepare_chart_data([])
    assert charts["items_per_source"] == {}
    assert charts["top_companies"] == {}
    assert charts["items_per_event_type"] == {}
    assert charts["items_per_month"] == {}


def test_prepare_items_csv(sample_items_dict: list[dict]):
    csv_str = prepare_items_csv(sample_items_dict)
    assert isinstance(csv_str, str)
    lines = csv_str.strip().splitlines()
    assert len(lines) == len(sample_items_dict) + 1  # Header + data rows
    header = lines[0]
    assert "id" in header
    assert "company" in header
    assert "technology" in header
    assert "passed" in header
    assert "reasons" in header


def test_prepare_items_csv_empty():
    csv_str = prepare_items_csv([])
    lines = csv_str.strip().splitlines()
    assert len(lines) == 1  # Only header


def test_get_other_story_items(sample_items_dict: list[dict]):
    story_item = next(i for i in sample_items_dict if i.get("story_id") == "49e51a42311b")
    peers = get_other_story_items(story_item, sample_items_dict)
    # The story 49e51a42311b has 2 items in sample_output
    assert len(peers) == 1
    assert peers[0]["id"] != story_item["id"]
    assert peers[0]["story_id"] == "49e51a42311b"

    # Item with no story_id
    no_story_item = {"id": "x1", "story_id": None}
    assert get_other_story_items(no_story_item, sample_items_dict) == []


def test_failed_item_explanations_integration():
    sample_failed_item = {
        "id": "item_fail_01",
        "title": "Unrelated consumer gadget",
        "filter": {
            "compressor_related": False,
            "north_america": False,
            "credible_source": True,
            "recent": False,
            "passed": False,
            "reasons": ["no_compressor_keyword", "not_north_america", "too_old"],
        },
    }
    reasons = sample_failed_item["filter"]["reasons"]
    explanations = explain_reasons(reasons)
    assert len(explanations) == 3
    assert "No compressor-related keyword" in explanations[0]
    assert "Not confirmed as North American" in explanations[1]
    assert "Published outside" in explanations[2]


# ==============================================================================
# 6. Sources & Candidates Logic Tests (Task P4)
# ==============================================================================

def test_sources_disclaimer_text():
    assert "Discovered sources are not approved by Atlas Copco" in DISCLAIMER_TEXT
    assert "Accepting here only makes them available to our own runs" in DISCLAIMER_TEXT


def test_can_accept_candidate_usable_vs_unusable():
    usable_candidate = Candidate(
        candidate_id="c1234567890a",
        name="Reliable Industrial News",
        url="https://reliable.example/news",
        domain="reliable.example",
        type_guess="trade_news",
        region="US",
        discovered_via="seed",
        robots_status="allowed",
        terms_status="ok",
        public_ok=True,
        trust_score=85,
        status="auto_vetted",
        usable=True,
    )
    can_acc, msg = can_accept_candidate(usable_candidate)
    assert can_acc is True
    assert "satisfies automated vetting" in msg

    unusable_candidate = Candidate(
        candidate_id="c1234567890b",
        name="Blocked Scraper News",
        url="https://blocked.example/news",
        domain="blocked.example",
        type_guess="competitor",
        region="US",
        discovered_via="outbound_link",
        robots_status="disallowed",
        terms_status="forbids_automation",
        public_ok=False,
        trust_score=40,
        status="rejected_by_rules",
        usable=False,
    )
    can_acc_b, msg_b = can_accept_candidate(unusable_candidate)
    assert can_acc_b is False
    assert "Acceptance disabled" in msg_b
    assert "robots.txt" in msg_b
    assert "terms status" in msg_b


def test_build_candidate_decision_valid_and_invalid():
    usable_candidate = Candidate(
        candidate_id="c_valid_01",
        name="Blower Digest",
        url="https://blower.example",
        domain="blower.example",
        type_guess="trade_news",
        region="US",
        discovered_via="seed",
        robots_status="allowed",
        terms_status="ok",
        trust_score=80,
        usable=True,
    )

    # 1. Valid Accept
    dec, err = build_candidate_decision(usable_candidate, "accepted", "Parth", "Vetted trade news")
    assert err == ""
    assert dec is not None
    assert dec.decision == "accepted"
    assert dec.decided_by == "Parth"
    assert dec.note == "Vetted trade news"

    # 2. Valid Reject
    dec_rej, err_rej = build_candidate_decision(usable_candidate, "rejected", "Parth", "Not relevant")
    assert err_rej == ""
    assert dec_rej is not None
    assert dec_rej.decision == "rejected"

    # 3. Missing operator name -> error
    dec_no_op, err_no_op = build_candidate_decision(usable_candidate, "accepted", "   ")
    assert dec_no_op is None
    assert "Operator name is required" in err_no_op

    # 4. Invalid decision string -> error
    dec_bad, err_bad = build_candidate_decision(usable_candidate, "maybe", "Parth")
    assert dec_bad is None
    assert "Invalid decision" in err_bad

    # 5. Cannot accept an unusable candidate -> error
    unusable_candidate = Candidate(
        candidate_id="c_invalid_02",
        name="Forbidden Portal",
        url="https://forbidden.example",
        domain="forbidden.example",
        type_guess="competitor",
        region="US",
        discovered_via="seed",
        robots_status="disallowed",
        terms_status="forbids_automation",
        trust_score=30,
        usable=False,
    )
    dec_blocked, err_blocked = build_candidate_decision(unusable_candidate, "accepted", "Parth")
    assert dec_blocked is None
    assert "Acceptance disabled" in err_blocked

    # 6. Rejecting an unusable candidate is allowed
    dec_rej_unusable, err_rej_u = build_candidate_decision(unusable_candidate, "rejected", "Parth", "Confirmed blocked")
    assert err_rej_u == ""
    assert dec_rej_unusable is not None
    assert dec_rej_unusable.decision == "rejected"


def test_filter_candidates_logic():
    c1 = Candidate(
        candidate_id="c1",
        name="Alpha Compressors",
        url="https://alpha.com",
        domain="alpha.com",
        type_guess="competitor",
        region="US",
        discovered_via="seed",
        trust_score=90,
        status="auto_vetted",
        usable=True,
    )
    c2 = Candidate(
        candidate_id="c2",
        name="Beta Trade Weekly",
        url="https://beta.org",
        domain="beta.org",
        type_guess="trade_news",
        region="CA",
        discovered_via="outbound_link",
        trust_score=60,
        status="needs_review",
        usable=False,
    )
    c3 = Candidate(
        candidate_id="c3",
        name="Gamma Gas Digest",
        url="https://gamma.com",
        domain="gamma.com",
        type_guess="trade_news",
        region="US",
        discovered_via="seed",
        trust_score=75,
        status="auto_vetted",
        usable=True,
    )
    all_c = [c1, c2, c3]

    # Filter usable only
    assert len(filter_candidates(all_c, usable_only=True)) == 2

    # Filter by status
    assert len(filter_candidates(all_c, status_filter="needs_review")) == 1

    # Filter by min trust score
    assert len(filter_candidates(all_c, min_trust_score=80)) == 1

    # Filter by search query
    assert len(filter_candidates(all_c, query="gamma")) == 1
    assert len(filter_candidates(all_c, query="nonexistent")) == 0


def test_prepare_register_rows():
    source = Source(
        source_id="test_src_01",
        name="Test Trade Journal",
        url="https://test.example/feed",
        type="trade_news",
        access_method="rss",
        robots_status="allowed",
        terms_status="ok",
        vetting_status="working",
        status="proposed",
        review_date="2026-10-29",
        licence_note="Public",
        region="US",
        notes="Active RSS",
    )
    rows = prepare_register_rows([source])
    assert len(rows) == 1
    assert rows[0]["Source ID"] == "test_src_01"
    assert rows[0]["Name"] == "Test Trade Journal"
    assert "🟢" in rows[0]["Vetting"]

    # Blocked source
    blocked_source = Source(
        source_id="blocked_src_02",
        name="Blocked Journal",
        url="https://blocked.example",
        type="competitor",
        access_method="html",
        robots_status="disallowed",
        terms_status="forbids_automation",
        vetting_status="blocked",
        status="blocked",
        review_date="2026-10-29",
        licence_note="Public",
        region="US",
        notes="Terms forbid",
    )
    blocked_rows = prepare_register_rows([blocked_source])
    assert "🔴" in blocked_rows[0]["Vetting"]


def test_prepare_candidate_rows():
    c = Candidate(
        candidate_id="cand_12345678",
        name="Demo Candidate",
        url="https://cand.example",
        domain="cand.example",
        type_guess="trade_news",
        region="US",
        discovered_via="seed",
        trust_score=82,
        status="auto_vetted",
        usable=True,
    )
    decision = CandidateDecision(
        candidate_id="cand_12345678",
        decision="accepted",
        decided_by="Parth",
        note="Approved for runs",
    )
    rows = prepare_candidate_rows([c], {"cand_12345678": decision})
    assert len(rows) == 1
    assert rows[0]["Candidate ID"] == "cand_12345678"
    assert rows[0]["Current Decision"] == "ACCEPTED"
    assert rows[0]["Decided By"] == "Parth"
    assert rows[0]["Usable"] == "✅ Yes"


# ==============================================================================
# 7. Report Generation & Preview Tests (Mocks, Zero Local Disk Writes)
# ==============================================================================

def test_validate_report_format():
    assert validate_report_format("pptx") == "pptx"
    assert validate_report_format("PPTX") == "pptx"
    assert validate_report_format("pdf") == "pdf"
    assert validate_report_format("PDF") == "pdf"
    with pytest.raises(ValueError, match="Unsupported report format"):
        validate_report_format("docx")
    with pytest.raises(ValueError, match="Unsupported report format"):
        validate_report_format("html")


def test_get_report_paths_and_mime():
    run_id = "20261029T101500Z"
    assert get_report_relative_path(run_id, "pptx") == "reports/report_20261029T101500Z.pptx"
    assert get_report_relative_path(run_id, "pdf") == "reports/report_20261029T101500Z.pdf"
    assert get_report_filename(run_id, "pptx") == "report_20261029T101500Z.pptx"
    assert get_report_filename(run_id, "pdf") == "report_20261029T101500Z.pdf"
    assert "presentation" in get_report_mime_type("pptx")
    assert get_report_mime_type("pdf") == "application/pdf"


def test_extract_report_preview_metrics(sample_envelope: OutputEnvelope):
    metrics = extract_report_preview_metrics(sample_envelope)
    assert metrics["run_id"] == "20261029T101500Z"
    assert metrics["scope_tech"] == "industrial compressors"
    assert metrics["scope_region"] == "US+CA"
    assert metrics["sources_count"] == len(sample_envelope.sources)
    assert metrics["items_count"] == len(sample_envelope.items)
    assert metrics["stories_count"] == len(sample_envelope.stories)
    assert metrics["candidates_considered"] == sample_envelope.candidates_considered
    assert metrics["date_range"] == "2026-09-30 to 2026-10-22"
    assert len(metrics["top_companies"]) > 0
    assert metrics["fallback_items_count"] == 1


def test_find_existing_reports():
    run_id = "20261029T101500Z"
    entries = [
        "report_20261029T101500Z.pptx",
        "report_20261029T101500Z.pdf",
        "report_20261101T080000Z.pptx",
        "random_file.txt",
    ]
    matches = find_existing_reports(run_id, entries)
    assert len(matches) == 2
    fmts = [m["fmt"] for m in matches]
    assert "pptx" in fmts
    assert "pdf" in fmts
    assert matches[0]["relative_path"] == "reports/report_20261029T101500Z.pptx"

    # Test with no matching entries
    assert find_existing_reports("nonexistent_run", entries) == []
    assert find_existing_reports(run_id, []) == []


def test_generate_report_bytes_success():
    run_id = "20261029T101500Z"
    mock_bytes = b"MOCK_REPORT_BINARY_CONTENT"

    with patch("atlas.report.build.write_report") as mock_write, \
         patch("atlas.storage.read_bytes") as mock_read:
        mock_write.return_value = f"/Volumes/test/reports/report_{run_id}.pptx"
        mock_read.return_value = mock_bytes

        data, err = generate_report_bytes(run_id, "pptx")
        assert err is None
        assert data == mock_bytes
        assert mock_write.called
        assert mock_write.call_args[0] == (run_id, "pptx")
        assert mock_read.called
        assert mock_read.call_args[0][0] == f"reports/report_{run_id}.pptx"


def test_generate_report_bytes_failures():
    run_id = "20261029T101500Z"

    # Invalid format
    data, err = generate_report_bytes(run_id, "invalid_fmt")
    assert data is None
    assert "Unsupported report format" in err

    # write_report raises exception
    with patch("atlas.report.build.write_report", side_effect=RuntimeError("Storage connection failed")):
        data, err = generate_report_bytes(run_id, "pptx")
        assert data is None
        assert "RuntimeError" in err
        assert "Storage connection failed" in err

    # read_bytes returns empty
    with patch("atlas.report.build.write_report", return_value="path"), \
         patch("atlas.storage.read_bytes", return_value=b""):
        data, err = generate_report_bytes(run_id, "pdf")
        assert data is None
        assert "empty" in err.lower()





# ---- one-page summary on the Report screen ----

def test_onepager_paths_and_filenames():
    run_id = "20261029T101500Z"
    assert get_report_relative_path(run_id, "pdf", "onepager") == "reports/onepager_20261029T101500Z.pdf"
    assert get_report_filename(run_id, "pptx", "onepager") == "onepager_20261029T101500Z.pptx"
    assert get_report_relative_path(run_id, "pdf") == "reports/report_20261029T101500Z.pdf"  # default unchanged


def test_find_existing_reports_lists_onepager_and_full_report_separately():
    run_id = "20261029T101500Z"
    entries = [f"report_{run_id}.pdf", f"report_{run_id}.pptx", f"onepager_{run_id}.pdf", f"onepager_{run_id}.pptx"]
    matches = find_existing_reports(run_id, entries)
    assert [(m["kind"], m["fmt"]) for m in matches] == [
        ("onepager", "pptx"), ("onepager", "pdf"), ("report", "pptx"), ("report", "pdf")]
    assert matches[0]["relative_path"] == f"reports/onepager_{run_id}.pptx"
    assert "One-page" in matches[0]["label"]


def test_generate_onepager_bytes_uses_write_onepager():
    run_id = "20261029T101500Z"
    with patch("atlas.report.onepager.write_onepager") as mock_write, \
         patch("atlas.report.build.write_report") as mock_full, \
         patch("atlas.storage.read_bytes") as mock_read:
        mock_write.return_value = f"/Volumes/test/reports/onepager_{run_id}.pdf"
        mock_read.return_value = b"ONEPAGER"
        data, err = generate_report_bytes(run_id, "pdf", "onepager")
        assert err is None and data == b"ONEPAGER"
        assert mock_write.call_args[0] == (run_id, "pdf") and not mock_full.called
        assert mock_read.call_args[0][0] == f"reports/onepager_{run_id}.pdf"
