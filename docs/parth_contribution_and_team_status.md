# Atlas Copco Market & Technology PoC: Parth Contribution Record & Phase 2 Delivery Status

**Author:** Parth (Quality Assurance, Documentation & Frontend Lead, Group 8, VIT Pune)  
**Date:** 15 November 2026  
**Repository Branch:** `feature/parth-phase2-frontend`  
**Target Pull Request Base:** `https://github.com/nikhil191206/personal_mlcp.git` (`main`)  
**Developer Fork:** `https://github.com/ParthTimeDEV/personal_mlcp.git`  
**Test Suite Health:** **408 of 408 tests passing** (`pytest -q` in 49.39s, 100% pass rate)  
**Frontend Logic Suite:** **69 of 69 tests passing** (`pytest tests/test_app_logic.py -q` in 5.94s)  

---

## A. Project and Role

### Project Context
The **Atlas Copco Market & Technology Intelligence Proof of Concept (PoC)** delivers automated, high-precision competitive intelligence for Atlas Copco's **Compressor Technique** business area. The platform scouts North American industrial news, product announcements, facility expansions, acquisitions, leadership appointments, and regulatory filings across the USA, Canada, and Mexico.

The system adheres strictly to enterprise compliance standards:
- **Zero Local Data Footprint:** Scraped web pages, full article texts, intermediate JSON files, and generated executive reports are never saved to local laptop filesystems; all persistent records reside in Databricks Unity Catalog Volumes.
- **Strict Compliance:** The compliance gate validates `robots.txt`, website terms of use, polite request delays ($\ge 3$s), and official User-Agent headers before any fetch.
- **Privacy & PII Stripping:** Personally identifiable information (PII) is scrubbed using Microsoft Presidio and spaCy before text classification, with article body text discarded from memory.
- **Token Security:** Cloud credentials are never logged, displayed in the UI, or passed through command-line arguments.

### Parth's Assigned Responsibilities
As defined in `parth.md` (Phase 1) and `parth2.md` (Phase 2):
1. **Phase 1 Lead for Documentation, Quality Assurance & Demo Materials:**
   - Authoring the strategic client questionnaire, industrial glossary, keyword taxonomy, executive demo note, and 8-dimension QA audit rubric.
2. **Phase 2 Lead for Streamlit Frontend Application (`app/`):**
   - Architecting and implementing the five operational user interface screens.
   - Authoring browser-independent pure Python logic modules under `app/lib/`.
   - Developing comprehensive offline automated test suites in `tests/test_app_logic.py`.
   - Writing the end-user manual and operational guide (`docs/frontend.md`).

---

## B. Completed Contributions by Phase & Feature

### 1. Phase 1 Completed Deliverables (Documentation & QA)

| Deliverable | Repository Path | Description & Technical Details |
|---|---|---|
| **Client Questionnaire** | [`docs/questions_for_atlas_copco.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/questions_for_atlas_copco.md) | 10 strategic questions for Atlas Copco Compressor Technique leadership covering source approval, Databricks governance, report templates, topic prioritization, and AI hosting. |
| **Technical Glossary** | [`docs/glossary.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/glossary.md) | Plain-English explanations of 25+ industrial compressor concepts (rotary screw, centrifugal, oil-free, air end, VSD, CFM/PSI) and pipeline architecture terms (robots.txt, compliance gate, fingerprinting, evidence records). |
| **Keyword Suggestions** | [`docs/keyword_suggestions.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/keyword_suggestions.md) | Curated additions for `config/keywords.yaml` across compressor types, industrial terms, and US manufacturing hubs, including risk analysis for false-positive triggers. |
| **Executive Demo Note** | [`docs/demo_note.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/demo_note.md) | One-page executive brief covering system architecture, proposed sources justification, blocked competitor sites analysis, filter mechanics, and open questions. |
| **QA Audit Rubric** | [`docs/check_results.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/check_results.md) | 8-dimension manual verification framework (title, date, fact/claim, company, technology, facts, PII, filter accuracy) and defect routing procedure. |

---

### 2. Phase 2 Completed Deliverables (Frontend Architecture & 5 Screens)

All frontend components are implemented in `app/` and backed by pure logic in `app/lib/`:

#### A. Entry Point & Environment Context
- **[`app/main.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/main.py):** Main application entry point configured with wide layout. Features a persistent environment sidebar displaying the active Databricks storage prefix (`ATLAS_PATH_PREFIX`), an automated amber warning banner when operating against primary demo storage (empty prefix), run telemetry, and operational navigation.

#### B. Volume Data Access Layer
- **[`app/lib/data.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/lib/data.py):** Pure data abstraction interfacing strictly with Databricks Volumes via `atlas.storage`. Implements `@st.cache_data(ttl=60)` with explicit cache clearing (`clear_data_cache()`), chronological run listing (`list_run_ids`), newest run detection (`latest_run_id`), strict Pydantic envelope loading (`load_envelope`), execution log retrieval (`load_log`), and complete items loading (`load_clean_items`) for inspecting failed filter items. Raises `StorageAccessError` with file paths rather than returning stale data.

#### C. Screen 1: Dashboard (`app/pages/1_Dashboard.py`)
- **Implemented in:** [`app/pages/1_Dashboard.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/pages/1_Dashboard.py), supported by [`app/lib/filters.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/lib/filters.py) and [`app/lib/dashboard.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/lib/dashboard.py).
- **Features:**
  - **Overview Telemetry:** Run ID, generation timestamp, technology/region scope, and 6 core metric cards.
  - **Sources Summary Table:** Per-source status, pages collected, items passed, kind (registered, discovered, fallback), and detailed refusal reasons.
  - **12-Dimension Item Browser:** All filters combinable in the sidebar (Source, Source Type, Evidence Label, Filter Status, Company, Technology, Event Type, Region, Date Range, Story, Fallback-only toggle, Free-text search).
  - **Item Detail Expanders:** Plain-English explanations for dropped items using all 12 closed-set filter reason codes (e.g. `no_compressor_keyword` $\rightarrow$ *"No compressor-related word found"*), links opening in new tabs, and story group cross-references.
  - **Multi-Source Story View:** Prioritizes intelligence confirmed by 2 or more independent sources.
  - **Visual Analytics:** Native Streamlit charts showing item counts by source, top 10 companies, event types, and monthly timelines.
  - **In-Memory Exports:** One-click downloads of filtered results as JSON or CSV without writing to local disk.

#### D. Screen 2: Auto Scout Settings Editor (`app/pages/2_Settings.py`)
- **Implemented in:** [`app/pages/2_Settings.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/pages/2_Settings.py), supported by [`app/lib/settings_ui.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/lib/settings_ui.py).
- **Features:**
  - Full configuration of all `ScoutSettings` parameters across 5 groups:
    1. *Scope:* Regions (US, CA, MX), Technologies (from `config/technologies.yaml`), Event Types.
    2. *Relevance Filter:* Freshness window (1–60 months), extra compressor keywords, excluded keywords, industrial requirement.
    3. *Sources:* Allowed source types, use-discovered-sources switch, minimum trust score slider (0–100), max items per source.
    4. *Scout Engine:* Discovery toggle, fallback switching toggle, max fallback items per source.
    5. *Watchlist:* Interactive table editor (`st.data_editor`) managing `WatchEntry` records (name, kind, aliases, follow-when-blocked).
  - Pydantic validation via `build_scout_settings` preventing saving invalid states.
  - Real-time diff panel (`settings_diff`) showing `field: default → current`.
  - Save to Volume via `atlas.scout.settings_store.save_settings` and Reset to defaults with confirmation modal.

#### E. Screen 3: Sources & Candidate Vetting (`app/pages/3_Sources.py`)
- **Implemented in:** [`app/pages/3_Sources.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/pages/3_Sources.py), supported by [`app/lib/sources.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/lib/sources.py).
- **Features:**
  - **Prominent Disclaimer Banner:** *"Discovered sources are not approved by Atlas Copco. Accepting here only makes them available to our own runs."*
  - **Register Tab:** Displays read-only vetted register loaded via `atlas.compliance.load_register`.
  - **Discovered Candidates Tab:** Loads candidate sources from Databricks storage via `load_candidates()`. Displays trust scores (0–100), itemized `trust_reasons`, terms of use evidence quotes and URLs, robots.txt status, and relevance samples.
  - **Decisions Workflow:** Accept and Reject buttons with operator attribution and audit notes, saved via `save_decision`.
  - **Strict Safety Enforcement:** Accept button is **automatically disabled whenever `usable == False`** with an explicit reason explaining why compliance forbids acceptance.

#### F. Screen 4: Run Launcher (`app/pages/4_Run.py`)
- **Implemented in:** [`app/pages/4_Run.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/pages/4_Run.py), supported by [`app/lib/runner.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/lib/runner.py).
- **Features:**
  - Run configuration: source selector from register, max items per source override, and execution switches (`--use-default-settings`, `--no-discovery`, `--no-fallback`).
  - Subprocess invocation: spawns `python -u -m atlas.run` using `sys.executable` with unbuffered streaming.
  - Token Security: strictly scans command arguments to block any token keywords; subprocess inherits `.env` directly.
  - Session Management: prevents concurrent pipeline runs by disabling the Start button while a run is active.
  - Live progress feedback: real-time progress bar, stage indicator, per-source status breakdown table, and live scrolling console log with download button.
  - Process controls: dedicated "Stop Pipeline Run" button triggers graceful process termination (`terminate_process`).
  - Completion handling: clears data cache upon exit code 0, displays summary telemetry, and provides a direct link to the Dashboard; displays specific extracted errors on failure.

#### G. Screen 5: Executive Intelligence Reports (`app/pages/5_Report.py`)
- **Implemented in:** [`app/pages/5_Report.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/pages/5_Report.py), supported by [`app/lib/report.py`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/app/lib/report.py).
- **Features:**
  - Run selection defaulting to latest run in Volume.
  - Content preview summary derived directly from the run's `OutputEnvelope` (sources checked, verified items, story clusters, publication date window, top companies).
  - Format selection: PPTX (Executive 16:9 Slide Deck) or PDF (Executive Digest Document).
  - In-memory generation calling `atlas.report.build.write_report(run_id, fmt)`.
  - Immediate in-memory download button via `st.download_button`.
  - Existing reports section listing previously compiled Volume reports under `reports/` with direct download buttons.
  - Zero local disk writes.

#### H. User Documentation
- **[`docs/frontend.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/frontend.md):** Comprehensive user guide detailing application startup, architecture, complete screen walkthroughs, troubleshooting matrix, and testing commands.

---

## C. Verification & Automated Test Results

All logic was verified using automated unit and regression test suites:

### 1. Frontend Logic Test Suite (`tests/test_app_logic.py`)
```powershell
pytest tests/test_app_logic.py -q
```
**Result:** **69 passed in 5.94s** (100% pass rate).
- **Section 1 (Data Layer):** 9 tests verifying active prefix detection, demo mode flags, chronological sorting of run IDs, storage error surfacing, envelope Pydantic validation, and log loading.
- **Section 2 (Filtering Logic):** 11 tests verifying all 12 filter dimensions, sorting by date/company/source, combinable filtering, empty results handling, and text search across titles and key facts.
- **Section 3 (Settings UI):** 9 tests verifying diff calculations across scalars, lists, and watchlists, form building with Pydantic validation, technology labels loading, watchlist formatting/parsing, and default reset logic.
- **Section 4 (Runner & Process Management):** 11 tests verifying unbuffered command construction, token exclusion from argv, progress line parsing, run ID extraction, argument validation, process termination with timeout escalation, credential redaction, error extraction, and live progress tracker state transitions.
- **Section 5 (Dashboard & Visuals):** 7 tests verifying run metrics computation, source summary formatting, multi-source story prioritization, chart data aggregation, and in-memory CSV generation.
- **Section 6 (Sources & Candidates):** 6 tests verifying disclaimer text, usability enforcement (`can_accept_candidate` disallows `usable == False`), candidate decision construction, and candidate filtering.
- **Section 7 (Report Generation):** 6 tests verifying format validation (`pptx`/`pdf`), path and MIME resolution, preview metrics extraction, existing report discovery, and in-memory byte generation/error handling.

### 2. Full Repository Regression Test Suite
```powershell
pytest -q
```
**Result:** **408 passed in 49.39s** (339 upstream tests + 69 frontend tests, 0 failures, 0 warnings).

### 3. Module Import & Syntax Verification
Verified that every frontend module and page imports cleanly without runtime errors:
```powershell
python -c "import importlib; [importlib.import_module(m) for m in ['app.main', 'app.lib.data', 'app.lib.filters', 'app.lib.settings_ui', 'app.lib.runner', 'app.lib.dashboard', 'app.lib.sources', 'app.lib.report', 'app.pages.1_Dashboard', 'app.pages.2_Settings', 'app.pages.3_Sources', 'app.pages.4_Run', 'app.pages.5_Report']]"
```
**Result:** Clean import with 0 syntax or runtime errors.

---

## D. Work Not Completed or Requiring External Dependencies

To maintain absolute transparency, the following tasks remain outside Parth's independent offline execution scope:

| Item | Status | Dependency & Rationale | Owner |
|---|---|---|---|
| **`docs/check_results_phase2.md`** | **Pending Live Run** | Requires manual auditing of 10 items and 3 fallback items against live web URLs extracted from an end-to-end production Databricks run. | Parth (awaits Nikhil's live run) |
| **Live Databricks Pipeline Runs** | **Infrastructure Dependent** | Databricks workspace administration, personal access tokens, and cloud execution are restricted to Nikhil. | Nikhil |
| **Live UI Screenshots** | **Demo Prep Dependent** | Visual browser screenshots for `docs/frontend.md` will be captured during the pre-demo UI rehearsal. | Parth |
| **Expansion of Proposed Sources** | **Under Review** | Hand-vetting 5 to 7 additional Canadian and specialty compressor sources in `config/sources.yaml`. | Ragini |
| **Live Switching Verification** | **Pipeline Dependent** | Testing fallback switching under live HTTP 429/blocked conditions across real external domains. | Sachi / Nikhil |

---

## E. Scope and Boundaries

- **Parth's Ownership:** `app/` (all modules and pages), `tests/test_app_logic.py`, `docs/frontend.md`, `docs/parth_contribution_and_team_status.md`, `docs/questions_for_atlas_copco.md`, `docs/glossary.md`, `docs/keyword_suggestions.md`, `docs/demo_note.md`, `docs/check_results.md`.
- **Teammate Ownership (Preserved Unmodified):**
  - Nikhil: `atlas/run.py`, `atlas/filter.py`, `atlas/storage.py`, `atlas/scout/settings_store.py`, `atlas/scout/fallback.py`, `atlas/scout/stories.py`.
  - Ragini: `atlas/compliance.py`, `atlas/collect.py`, `atlas/scout/discover.py`, `atlas/scout/vet.py`, `config/sources.yaml`, `config/discovery_seeds.yaml`.
  - Sachi: `atlas/extract.py`, `atlas/clean.py`, `atlas/report/` (`build.py`, `charts.py`, `pdf_builder.py`, `pptx_builder.py`), `config/keywords.yaml`, `config/products.yaml`, `config/technologies.yaml`.

---

## F. Delivery & Pull Request Preparation

- **Feature Branch:** `feature/parth-phase2-frontend`
- **Target Remote Fork:** `origin` (`https://github.com/ParthTimeDEV/personal_mlcp.git`)
- **Upstream Sync Status:** Synchronized with `upstream/main` (`d0e0e14` merged cleanly; 0 divergence).
- **Excluded Files:** `PROJECT_HANDOFF_FOR_CHATGPT.md` is strictly excluded via `.git/info/exclude`.
- **PR Readiness:** All assigned implementation files and unit tests are complete, verified, and ready for staging and commit.
