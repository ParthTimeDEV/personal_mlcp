# parth2.md: The frontend

**Person:** Parth. Read `parent2.md` first, fully. This file is your task spec and the prompt kit for your AI.

## Using this file with your AI
Give your AI, in order: (1) all of `parent2.md`, (2) this file, (3) `atlas/models.py`, `atlas/storage.py`, `config/scout_settings.yaml`, (4) `tests/fixtures/sample_output.json` (Nikhil pushes it on D0), (5) the kickoff prompt below. Demand the output format from `parent2.md` section 12.

### Kickoff prompt (paste as-is)
> You are helping me build the frontend of a market-scouting pipeline, in Streamlit. I have pasted the Phase 2 master brief, my task file, and the shared code. Implement the app in `app/` and the tests in `tests/test_app_logic.py` exactly as specified in my task file. The app reads and writes Databricks only through `atlas.storage` and the helpers in `atlas.scout.settings_store`; it starts the pipeline only by running `python -m atlas.run` as a subprocess. It must never show, log or store the Databricks token, never write data files to local disk, and never contact any website itself. Put all logic that does not need a browser in `app/lib/` so it can be unit-tested. Use the models in `atlas/models.py` (import them, never redefine). Return each file in full under a heading with its repo path. Tests run offline with `pytest`. List every assumption at the end. If a requirement is ambiguous, ask me instead of choosing.

## Your files
| File | What |
|---|---|
| `app/main.py` | entry point, navigation, sidebar (prefix, latest run) |
| `app/pages/1_Dashboard.py`, `2_Settings.py`, `3_Sources.py`, `4_Run.py`, `5_Report.py` | the five screens |
| `app/lib/data.py`, `filters.py`, `settings_ui.py`, `runner.py` | logic, unit-tested |
| `tests/test_app_logic.py` | tests |
| `docs/frontend.md` | user guide with one screenshot per screen |

## Task P0: Setup
`parent.md` section 12 setup; `pip install streamlit`, then append `streamlit` to `requirements.txt` and tell Nikhil. `storage_check` PASS with `ATLAS_PATH_PREFIX=dev/parth`. Start the skeleton with `streamlit run app/main.py` and confirm it opens at `http://localhost:8501`. Until real runs exist, build against `tests/fixtures/sample_output.json` (synthetic).

## Task P1: Data layer (`app/lib/data.py`)
- `latest_run_id() -> str | None`: newest `output/poc_<run_id>.json` by name (run ids sort by time).
- `list_run_ids() -> list[str]`.
- `load_envelope(run_id) -> OutputEnvelope` via `storage.read_json` and Pydantic validation; a validation error is shown in the UI with the file name, never hidden.
- `load_log(run_id) -> RunLog | None`, `load_clean_items(run_id) -> list[Item]` (all items from `clean/<source>/<run_id>.json`, so failed items can be browsed with their reasons).
- Cache reads with `st.cache_data(ttl=60)`; add a "Refresh" button. Prefix shown in the sidebar from `ATLAS_PATH_PREFIX`; a warning banner when it is empty ("you are looking at the real demo folders").
- If Databricks is unreachable, show the real error message and stop the page; do not show stale or fake data.

## Task P2: Dashboard (`1_Dashboard.py`, `filters.py`)
- Header: run id, time, scope, counts (collected, passed, dropped, stories, refused sources, fallback items).
- **Sources table:** per source `SourceSummary` (status, collected, passed, kind, note). Refused sources highlighted with reasons; discovered sources badged "discovered, not approved"; fallback rows show which source they stand in for.
- **Item browser** with filters in the sidebar, all combinable: source, source type, label (fact or claim), passed or failed (needs the clean items), company, technology, event type, region, date range, story, via-fallback only, free-text search in title and key facts. Sort by date, company or source.
- **Item detail** (expander or side panel): every field, the four filter checks with their reason codes, the link (opens in a new tab), the story's other items, and a "why was this dropped?" explanation for failed items using the reason codes (plain-English labels in `filters.py`: `no_compressor_keyword` → "No compressor-related word found", and so on for all codes in `nikhil2.md` N2 and `parent.md`).
- **Stories view:** stories with 2 or more sources first, each listing its items and sources.
- Charts: items per source, per company (top 10), per event type, per month (use Streamlit's built-in charts; no extra library).
- Download the visible items as JSON or CSV **in memory** (`st.download_button`), never written to disk.

`filter_items(items: list[dict], f: ItemFilters) -> list[dict]` is a pure function: unit-test every filter and combinations.

## Task P3: Settings editor (`2_Settings.py`, `settings_ui.py`)
Edit every `ScoutSettings` field, grouped:
1. **Scope:** regions (multi-select), technologies (multi-select from the labels in `config/technologies.yaml`, empty = all), event types (multi-select, empty = all).
2. **Relevance filter:** recent months (slider 1 to 60), extra compressor keywords and excluded keywords (tag-style inputs, one per line), require "industrial" (checkbox).
3. **Sources:** source types (multi-select), use discovered sources (checkbox), minimum trust score (slider 0 to 100), max items per source.
4. **Scout engine:** discovery on or off, switching (fallback) on or off, max fallback items per source.
5. **Watchlist:** table editor for `WatchEntry` (name, kind, aliases, follow when blocked); add and remove rows.
Behaviour: inputs are validated by building a `ScoutSettings` (show Pydantic errors beside the fields, do not save invalid values); **Save** calls `save_settings`; **Reset to defaults** loads `default_settings()` (with a confirmation); a **diff panel** (`settings_diff`) lists every field that differs from the defaults as "field: default → current"; a plain-English one-line explanation under each control ("Items older than this many months are dropped by the 'recent' check"). A note: "Changes apply to the next run."
`settings_diff(current, defaults) -> list[tuple[str, object, object]]` is pure: unit-test it, including list fields and the watchlist.

## Task P4: Sources and candidates (`3_Sources.py`)
- **Register tab:** table from `config/sources.yaml` (read with `load_register`): status, vetting status, robots, terms, type, region, review date; blocked and unreachable ones with their notes. Read-only.
- **Discovered candidates tab:** from `load_candidates()`: name, domain, type guess, region, discovered how and from where, trust score with the `trust_reasons` list, terms status with the stored quote and a link to the terms page, robots status, newest item date, relevance sample, `usable`, status. Filter by usable, status, score.
- **Decisions:** for each candidate an **Accept for use** and a **Reject** button with a note (`CandidateDecision`, `decided_by` from a name field in the sidebar). Saved with `save_decision`. Show the current decision per candidate. **Accept is disabled with an explanation when `usable` is false** (terms unknown or forbidden, robots disallow, and so on): acceptance cannot override the automatic safety rules.
- A visible banner: "Discovered sources are not approved by Atlas Copco. Accepting here only makes them available to our own runs."

## Task P5: Run launcher (`4_Run.py`, `runner.py`)
- Controls: source (all or one, from the register), max items, checkboxes for "use default settings", "no discovery", "no fallback", prefix display (read-only; changed only in `.env`).
- `start_run(args) -> subprocess.Popen`: runs `python -m atlas.run <args>` with the same interpreter (`sys.executable`), `stdout=PIPE`, `stderr=STDOUT`, text mode, unbuffered (`-u`). The token is never passed on the command line; the child reads `.env` itself.
- Live progress: read lines as they arrive and show them in a scrolling box; parse the Phase 1 progress lines (`[n/m] source_id`, `allowed...`, `collected...`, `done...`) into a progress bar and per-source status (`parse_progress_line(line)` is pure and tested). Keep the raw output visible.
- A "Stop" button terminates the process.
- When the run ends: show the exit code, parse the `run_id:` line, load and show the summary, and link to the Dashboard for that run. Exit code 1 shows the errors from the log, not just "failed".
- Only one run at a time (store the process in `st.session_state`); disable the button while running.

## Task P6: Report screen (`5_Report.py`)
- Pick a run (default latest), pick PDF or PPTX, **Generate** calls `atlas.report.build.write_report(run_id, fmt)` (Sachi's function; until it exists, show "not available yet" and keep the screen working) and then offers the bytes through `st.download_button` using `storage.read_bytes`. List existing reports under `reports/` for the run with download buttons.
- Show a short summary of what the report will contain (counts from the envelope).
- No report is written to local disk.

## Task P7: Look and usability
- Plain, readable layout: wide mode, consistent labels, colour for status (green working, amber needs review, red refused), not colour alone (also an icon or word).
- Every screen has a one-line "what is this" caption.
- Errors are shown in plain English with the technical message beneath.
- Works with an empty Volume (first run): friendly empty states, no crashes.
- Accessibility basics: all controls labelled, no information only in a chart.

## Task P8: Tests and docs
`tests/test_app_logic.py` (pure logic only, no browser, synthetic data): `filter_items` (each filter, combinations, empty result, text search), `settings_diff`, building a `ScoutSettings` from form values (valid and invalid), `parse_progress_line`, `latest_run_id` with a mocked `storage.list_dir`, `start_run` builds the right command (mock `subprocess.Popen`; assert the token never appears in arguments), friendly reason-code labels cover every code, decisions cannot be saved for an unusable candidate. `docs/frontend.md`: how to start the app, what each screen does with a screenshot, the safety notes (local only, never public), and a troubleshooting list.

## Task P9: Integration check
After Nikhil's `run.py` and Ragini's discovery are pushed, run the whole loop yourself under `dev/parth`: change a setting (for example set recent months to 3 and require "industrial"), save it, run, and confirm the dashboard shows fewer items and the reason codes explain why; accept a discovered candidate and confirm it is used in the next run; generate a report. Record what worked and what failed in the team chat with the reporting format. Hand-check 10 items and 3 fallback items against their live pages and write the result in `docs/check_results_phase2.md`.

## Acceptance criteria
- [ ] `pytest tests/test_app_logic.py -q` passes offline.
- [ ] All five screens work against a real run and against the sample fixture.
- [ ] Changing a setting and saving it changes the next run's result.
- [ ] A candidate can be accepted or rejected; unusable candidates cannot be accepted.
- [ ] A run can be started and watched from the Run screen; a report can be generated and downloaded.
- [ ] The token never appears on screen, in logs, in command lines or in the repo; no data or report file is written to the laptop.
- [ ] `docs/frontend.md` has a screenshot per screen.

## Do not
- Do not call any website from the app; do not scrape anything.
- Do not show, log or pass the token. Do not host the app publicly.
- Do not change settings anywhere except through `save_settings`; do not edit `config/` files from the app.
- Do not edit other people's files; ask the owner.
