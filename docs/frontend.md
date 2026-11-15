# Atlas Copco Market Scout — Frontend User Guide

**Document:** `docs/frontend.md`  
**Author:** Parth (Quality Assurance, Documentation & Frontend Lead, Group 8, VIT Pune)  
**Target Audience:** Atlas Copco Stakeholders, Machine Learning Engineers, and System Operators  
**Application Path:** `app/main.py`  

---

## 1. Overview & Architecture

The **Atlas Copco Market & Technology Scout** frontend is an enterprise Streamlit application providing competitive market intelligence for Atlas Copco's **Compressor Technique** business area.

### Core Architectural Principles
1. **Zero Local Data Footprint:** No scraped web pages, HTML, JSON data files, or generated reports are ever saved to the local filesystem. All operational state resides strictly within cloud storage (Databricks Unity Catalog Volumes). All client downloads stream in-memory through the browser.
2. **Strict Compliance & Ethics:** The frontend never initiates web scraping requests or contacts external competitor websites. It reads exclusively from Databricks storage via `atlas.storage` and `atlas.scout.settings_store`.
3. **Token Security:** Databricks access tokens are never displayed on screen, logged to console, or passed in command-line arguments. Subprocesses inherit environment variables securely from `.env`.
4. **Decoupled Business Logic:** All data processing, filtering, diffing, and subprocess tracking logic is implemented in pure Python modules under `app/lib/` and verified with offline automated tests (`tests/test_app_logic.py`).

---

## 2. Getting Started

### Prerequisites
- Python 3.12+ virtual environment (`.venv`)
- Installed dependencies: `pip install -r requirements.txt`
- Configured `.env` file with Databricks credentials and sandbox prefix:
  ```bash
  DATABRICKS_HOST=https://<your-workspace>.cloud.databricks.com
  DATABRICKS_TOKEN=dapi...
  ATLAS_PATH_PREFIX=dev/parth
  ```

### Starting the Application
From the repository root directory, execute:
```powershell
streamlit run app/main.py
```
The application will open automatically in your browser at `http://localhost:8501`.

---

## 3. Screen Walkthrough & Operational Guide

The application consists of an entry point and five dedicated operational screens accessible via the left sidebar.

### Screen 0: Entry Point & Environment Sidebar (`app/main.py`)
- **Storage Prefix Notice:** Displays the active Databricks storage prefix (`ATLAS_PATH_PREFIX`). If empty, displays a prominent amber warning indicating that the application is operating in live production/demo mode.
- **Run Telemetry:** Displays the newest available `run_id` and total run count detected in the cloud Volume.
- **Navigation Overview:** Provides a high-level orientation for operators.

---

### Screen 1: Intelligence Dashboard (`app/pages/1_Dashboard.py`)
*Caption: Browse verified competitive intelligence, filter market events, explore multi-source stories, and export findings.*

- **Overview Telemetry:** Displays Run ID, timestamp, scope (technology and region), and metric cards for items collected, items passed, items dropped, stories formed, refused sources, and fallback items.
- **Source Compliance Summary:** Comprehensive table listing all sources in the run, vetting status, pages collected, items passed, and refusal/error notes. Refused competitor sources are badged and explained.
- **12-Dimension Filter Sidebar:**
  1. Source ID dropdown
  2. Source Type (Competitor, Trade News, Government)
  3. Evidence Label (Fact vs Claim)
  4. Filter Status (Passed Filter vs Dropped / Clean Items)
  5. Target Company (Top competitors + custom search)
  6. Technology Category
  7. Industrial Event Type
  8. Geographic Region (US, CA, MX)
  9. Publication Date Range
  10. Story Cluster selection
  11. Fallback Switching Only toggle
  12. Free-text search across Title and Key Facts
- **Sorting:** Sort visible items by Publication Date (newest first), Company name, or Source ID.
- **Item Detail Expanders:**
  - Displays full metadata, source link (opens in new tab), publication date, and extracted key facts.
  - Shows the 4 relevance filter checks (Compressor Keyword, North America, Credibility, Freshness) with their closed-set reason codes.
  - For dropped items, displays a plain-English explanation of why the item failed (e.g. *No compressor-related keyword found in article*).
  - Lists related articles in the same multi-source story cluster.
- **Stories View:** Prioritizes stories covered by 2 or more independent sources to highlight high-confidence industry developments.
- **Visual Analytics:** Native charts showing item distribution per source, top 10 companies, event types, and monthly trends.
- **In-Memory Exports:** One-click downloads of filtered results as JSON or CSV directly from memory (`st.download_button`).

---

### Screen 2: Auto Scout Settings (`app/pages/2_Settings.py`)
*Caption: Adjust the automated scout engine scope, relevance filter thresholds, source vetting rules, and followed competitor watchlists.*

Organized into five logical configuration groups:
1. **Scope:** Regions (US, CA, MX), Technologies (multi-select from `config/technologies.yaml`), and Event Types.
2. **Relevance Filter:** Recent months freshness window (slider 1–60 months), extra compressor keywords, excluded keywords, and industrial requirement toggle.
3. **Sources:** Allowed source types, use-discovered-sources checkbox, minimum trust score threshold (0–100), and max items per source.
4. **Scout Engine:** Discovery toggle, fallback switching toggle, and max fallback items per source.
5. **Followed Watchlist Table:** Dynamic interactive table editor (`st.data_editor`) managing `WatchEntry` records (name, kind, aliases, and follow-when-blocked switch).
- **Validation & Persistence:** Validates all fields against the Pydantic `ScoutSettings` schema. Prevents saving invalid inputs. Saves to `settings/scout_settings.json` in the Volume via `atlas.scout.settings_store.save_settings`.
- **Diff Panel:** Shows real-time difference against defaults (`field: default → current`).
- **Reset to Defaults:** Loads `config/scout_settings.yaml` defaults with a safety confirmation dialog.

---

### Screen 3: Sources & Candidate Vetting (`app/pages/3_Sources.py`)
*Caption: Inspect vetted source register compliance, review automatically discovered candidate sources, and manage acceptance decisions.*

- **Prominent Disclaimer Banner:** *"Discovered sources are not approved by Atlas Copco. Accepting here only makes them available to our own runs."*
- **Tab 1 — Vetted Source Register (Read-Only):**
  - Displays the 15 vetted sources from `config/sources.yaml` via `atlas.compliance.load_register`.
  - Filterable by region, source type, and vetting status (Active, Excluded, Blocked, Needs Permission, Unreachable).
  - Details expander showing access method (RSS/HTML), review date, robots.txt status, and license terms.
- **Tab 2 — Discovered Candidates:**
  - Loads newly discovered candidate websites from `scout/candidates.json`.
  - Filterable by usability, decision status (All, Pending, Accepted, Rejected), minimum trust score, and text query.
  - Candidate inspection cards showing:
    - Trust score indicator (0–100) and breakdown list (`trust_reasons`).
    - Terms of use status, evidence quote, and link to terms page.
    - Robots.txt status and newest item publication date.
    - Relevance sample score.
  - **Decisions Workflow:** Accept and Reject buttons with an operator note input.
  - **Strict Safety Rule:** The **Accept button is strictly disabled** whenever automated vetting rules mark `usable == False`. Operators cannot override compliance gates.

---

### Screen 4: Run Launcher (`app/pages/4_Run.py`)
*Caption: Initiate, monitor, and manage end-to-end competitive intelligence scouting runs.*

- **Run Configuration:**
  - Select target source: "All Sources" or single `source_id` from the register.
  - Max items override per source (0 = use saved settings value).
  - Execution switches: "Use Default Settings", "Skip Source Discovery", "Skip Fallback Switching".
- **Subprocess Execution:**
  - Spawns unbuffered subprocess `python -u -m atlas.run <args>`.
  - Token Security: Subprocess inherits `.env` securely; tokens are never passed on the command line.
  - Streamlit Session Management: Prevents concurrent runs by disabling the Start button while a run is active.
- **Live Progress Feedback:**
  - Progress bar updating per source `[n/m]`.
  - Current stage metric (Initializing, Source Discovery, Collection & Extraction, Fallback Switching, Finalizing).
  - Collapsible per-source status breakdown table.
  - Live scrolling console log with one-click log file download.
- **Process Controls:**
  - Dedicated **"Stop Pipeline Run"** button triggers graceful subprocess termination via `terminate()`.
- **Completion Telemetry:**
  - Exit code 0: Clears cache, shows summary metrics, and displays direct link to the Dashboard (`1_Dashboard.py`).
  - Non-zero exit code: Displays extracted error messages explaining why the run failed.

---

### Screen 5: Executive Intelligence Reports (`app/pages/5_Report.py`)
*Caption: Generate, preview, and export board-ready PowerPoint presentations and PDF digests.*

- **Run Selection:** Choose any completed run from cloud storage (defaults to newest).
- **Content Preview Card:** Displays verified counts derived from the run's `OutputEnvelope` (sources checked, verified items, story clusters, publication window, top companies).
- **What do you need?** *One-page summary* (default, recommended) or *Full report*. The one-page summary has four boxes: look at first, other facts, how the news differs from Atlas Copco's own, and the sources. It calls `atlas.report.onepager.write_onepager` and uploads to `reports/onepager_<run_id>.<fmt>`. The full report is the 10-slide version below.
- **Format Options:**
  - `pptx`: Executive 16:9 widescreen PowerPoint presentation slide deck.
  - `pdf`: Executive digest document.
- **In-Memory Generation:** Calls `atlas.report.build.write_report(run_id, fmt)`, uploads to `reports/report_<run_id>.<fmt>` in the Volume, and streams bytes directly to `st.download_button`.
- **Existing Reports Section:** Lists previously generated reports for the run with instant download buttons. Zero files are saved to the local laptop.

---

## 4. Troubleshooting & FAQ

| Issue | Cause | Solution |
|---|---|---|
| **"No runs found in storage yet"** | The Databricks Volume `output/` folder is empty or uninitialized. | Navigate to **Run Launcher (4_Run)** and execute a pipeline run, or verify `ATLAS_PATH_PREFIX` in `.env`. |
| **"StorageAccessError: Cloud storage access failed"** | Missing or invalid Databricks host/token, or network interruption. | Check your `.env` file credentials and ensure `python -m atlas.storage_check` passes. |
| **"Port 8501 is already in use"** | An existing Streamlit server instance is running. | Run `streamlit run app/main.py --server.port 8502` or terminate the existing process. |
| **"Accept button is disabled on Sources page"** | Automated compliance vetting marked `usable == False` (e.g. robots disallow or terms forbid automation). | By enterprise design, human operators cannot override compliance rules for unusable sites. |
| **Report generation fails with `PersonalDataError`** | An item was flagged by the last-line PII filter as containing an email or phone number. | Inspect the failed item in the Dashboard. The PII scrubber in `atlas/extract.py` should be updated with new redaction patterns. |

---

## 5. Offline Automated Verification

All frontend pure logic is thoroughly tested offline with `pytest`:
```powershell
pytest tests/test_app_logic.py -q
```
**Test Coverage:** 69 unit tests verifying data access caching, 12-dimension filtering, settings diffing, watchlist parsing, subprocess security, progress parsing, candidate usability safety enforcement, and in-memory report streaming.
