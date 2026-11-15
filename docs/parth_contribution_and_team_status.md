# Atlas Copco Market & Technology PoC: Master Project Status & Team Handover

**Author:** Parth (Quality Assurance, Documentation & Frontend Lead)  
**Date:** 15 November 2026  
**Repository Branch:** `feature/parth-documentation-evidence`  
**Latest Integrated Upstream Commit:** `d0e0e14` (Phase 2 Progress Report & Live Verification)  
**Test Suite Health:** **339 of 339 tests passing** (`pytest -q` in 39.7s)

---

## A. Executive Summary

### What the Project Does
The Atlas Copco Market & Technology Proof of Concept (PoC) is an automated intelligence pipeline designed for Atlas Copco's Compressor Technique business area. Atlas Copco grows aggressively through acquisitions (29 announced in 2025) and requires proactive visibility into market developments, technological innovations, and competitor moves in North America.

To solve this without over-engineering or violating strict enterprise governance:
1. **Automated Scout Engine:** Evaluates public USA, Canadian, and Mexican industry sources against robots.txt and website terms of use.
2. **Transparent Fact Extraction:** Ingests articles, strips all personally identifiable information (PII) using Presidio and spaCy, classifies industrial events and equipment, and discards full page text in memory.
3. **Enterprise Relevance Filtering:** Evaluates extracted metadata against four transparent criteria (compressor relevance, North American geography, source credibility, and 12-month freshness).
4. **Resilient Switching & Story Clustering:** If a source is blocked, the engine switches to secondary allowed coverage without bypassing security. Related articles across sources are grouped into unified multi-source stories.
5. **Zero Local Storage Compliance:** All persistent states, logs, JSON envelopes, and generated executive reports (PDF and PPTX) reside strictly within cloud storage (Databricks Unity Catalog Volumes).

### Current Project State
* **Phase 1 (The Core PoC):** **100% Implemented and Verified.** The end-to-end backend pipeline (`atlas/compliance.py`, `collect.py`, `extract.py`, `clean.py`, `filter.py`, `run.py`, `storage.py`) operates reliably with zero local storage.
* **Phase 2 (Scout Engine & Scope Expansion):** **Advanced Implementation.** 
  - Discovery and automated vetting (`atlas/scout/discover.py`, `vet.py`) are built and tested (Ragini).
  - Settings store, switching logic, story clustering, and pipeline orchestration (`atlas/scout/settings_store.py`, `fallback.py`, `stories.py`, `run.py`) are integrated (Nikhil).
  - Extended extraction (regions, event types, products) and executive PDF/PPTX report generation (`atlas/report/`) are verified on live Databricks runs (Sachi).
  - Streamlit user interface (`app/`) is designed and scheduled for implementation (Parth).
* **Overall Completion:** Approximately **85% complete**. Core engines and report builders are functional; remaining work centers on frontend assembly, expanding vetted sources, live production runs, and empirical QA checks.

---

## B. Latest Repository Updates (Upstream Synchronization)

The local feature branch has been fully synchronised with the upstream repository (`nikhil191206/personal_mlcp`). A total of **9 upstream commits** (`ae10f91` through `d0e0e14`) were integrated seamlessly via merge commit `2f9e582` with zero conflicts.

### Upstream Commit Log Incorporated:
1. `ae10f91` — *Print live progress during runs; add `prepare.md` and pipeline diagram (`docs/images/pipeline.png`).*
2. `031d900` — *Add Phase 2 master briefs (`parent2.md`, `wd2.md`, 4 personal files), shared models, storage helpers, and default scout settings.*
3. `679b84b` — *[nikhil] Phase 2: settings store, settings-aware filter, fallback switching, story clustering, run integration, sample fixtures, and tests.*
4. `532bb37` — *Update `README.md`.*
5. `8fc775b` — *[ragini] Phase 2: source discovery, automatic vetting, rule-based trust scoring, discovery seeds, and tests.*
6. `7bdb870` — *[sachi] Phase 2: region (US/CA/MX), event type, product extraction, and PDF/PPTX report builder package.*
7. `24cb246` — *[sachi] Report package updates: use `StoryCluster.headline` and `first/last_published` timestamps from Nikhil's models.*
8. `43bc704` — *[sachi] Live-check bug fixes: non-North-American places yield null region; clearer report wording; Sachi live run results.*
9. `d0e0e14` — *[sachi] Progress report in `parent2.md` Section 20 documenting live Databricks run `20261115T045141Z`.*

### Key Architecture & Configuration Changes:
* **Dependencies Updated:** Added `python-pptx`, `reportlab`, and `matplotlib` to `requirements.txt` to power automated slide and document generation.
* **New Configuration Files:** Added `config/discovery_seeds.yaml` (40 candidate seeds), `config/products.yaml` (compressor model series), and `config/scout_settings.yaml` (runtime settings and watchlist).
* **Test Suite Expansion:** Total automated unit tests expanded from **127 to 339 tests** (100% pass rate).

---

## C. Current System Architecture

The pipeline operates as a unidirectional, memory-safe data flow running under Python 3.12:

```
                      settings/scout_settings.json (Cloud Storage / Databricks Volume)
                                        │
┌────────────── AUTO SCOUT ENGINE ──────┴────────────────────────────────────────────────┐
│  atlas/scout/discover.py ──► atlas/scout/vet.py ──► scout/candidates.json              │
│  (Finds seeds, checks robots & terms, scores trust 0-100; usable candidates admitted)   │
└───────────────────────────────────────┬────────────────────────────────────────────────┘
                                        │
                 Vetted Sources Register (config/sources.yaml) + Usable Discovered Sources
                                        │
                                        ▼
┌── STEP 1: COMPLIANCE GATE (atlas/compliance.py) ──────────────────────────────────────┐
│  Verifies robots.txt, terms of use, polite delays (>=3s), and official User-Agent.    │
│  Refuses unapproved or forbidden sources; halts politely on HTTP 429/503.             │
└───────┬───────────────────────────────────────────────────────────────────────────────┘
        │ Allowed URLs                                  │ Blocked / Refused Sources
        ▼                                               ▼
┌── STEP 2: COLLECTOR (atlas/collect.py) ──┐    ┌── STEP 2B: FALLBACK SWITCHING ────────┐
│  Fetches RSS feeds & listing pages.      │    │  (atlas/scout/fallback.py)             │
│  Metadata written to raw/<source>/<run>. │    │  Scans other allowed sources for same │
│  HTML kept in memory; never saved.       │    │  company/product. Labels via_fallback. │
└───────┬──────────────────────────────────┘    └───────┬────────────────────────────────┘
        │ Pages in memory                               │
        ▼                                               │
┌── STEP 3: EXTRACTOR & CLEANER (atlas/extract.py, clean.py) ───────────────────────────┐
│  • Trafilatura extracts article text and metadata.                                    │
│  • Presidio & spaCy redact PII (<PERSON>, <EMAIL>, <PHONE>) with company allow-list.  │
│  • Rule-based extraction tags Region (US/CA/MX), EventType, Technology, Product.     │
│  • RapidFuzz maps company aliases; content hashed to SHA-256 fingerprint.             │
│  • Article body text discarded from memory; clean items written to clean/<source>/<run>│
└───────┬───────────────────────────────────────────────────────────────────────────────┘
        │ Cleaned Items
        ▼
┌── STEP 4: RELEVANCE FILTER & STORIES (atlas/filter.py, atlas/scout/stories.py) ───────┐
│  Four-gate evaluation: Compressor Keyword + North America + Credibility + Recency.    │
│  Stories groups items about the same company/product/event across independent sources.│
└───────┬───────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌── STEP 5: OUTPUT ENVELOPE (atlas/run.py) ─────────────────────────────────────────────┐
│  Validates OutputEnvelope via Pydantic; writes output/poc_<run_id>.json.              │
│  Writes execution metrics to logs/<run_id>.json. Verifies zero local disk leakage.    │
└───────┬───────────────────────────────────────┬───────────────────────────────────────┘
        │                                       │
        ▼                                       ▼
┌── STEP 6: EXECUTIVE REPORTS ──────────┐   ┌── STEP 7: STREAMLIT FRONTEND (Phase 2) ───┐
│  (atlas/report/build.py)              │   │  (app/main.py, app/pages/)                │
│  Generates 10-slide PPTX & PDF report │   │  Dashboard, Item Browser, Settings Editor,│
│  Saved to reports/report_<run_id>.    │   │  Candidate Vetting, Run Launcher, Download│
└───────────────────────────────────────┘   └───────────────────────────────────────────┘
```

---

## D. Completed Work & Supporting Evidence

| Component / Task | Owner | Implemented Deliverables | Verification & Evidence | Status |
| :--- | :---: | :--- | :--- | :---: |
| **P0: Local Dev Environment** | Parth | Python 3.12 `.venv`, dependencies, spaCy model | 339 unit tests pass in 39.72s | **Complete** |
| **P1: Client Questionnaire** | Parth | `docs/questions_for_atlas_copco.md` | 10 strategic questions for leadership | **Complete** |
| **P2: Technical Glossary** | Parth | `docs/glossary.md` | Plain-English industrial & pipeline terms | **Complete** |
| **P3: Keyword Taxonomy** | Parth | `docs/keyword_suggestions.md` | False-positive risk analysis & merge guide | **Complete** |
| **P4: Executive Demo Note** | Parth | `docs/demo_note.md` | 1-page brief matching 5 proposed sources | **Template Ready** |
| **P5: QA Audit Framework** | Parth | `docs/check_results.md` | 8-dimension audit rubric & defect routing | **Framework Ready** |
| **Scout Engine: Settings & Stories** | Nikhil | `atlas/scout/settings_store.py`, `fallback.py`, `stories.py` | `test_scout_fallback.py`, `test_scout_stories.py` pass | **Complete** |
| **Pipeline Orchestrator** | Nikhil | `atlas/run.py`, `atlas/filter.py`, `atlas/storage.py` | `test_run.py`, `test_filter.py` pass | **Complete** |
| **Scout Engine: Discovery & Vet** | Ragini | `atlas/scout/discover.py`, `vet.py`, `discovery_seeds.yaml` | `test_scout_discover.py`, `test_scout_vet.py` pass | **Complete** |
| **Source Vetting Register** | Ragini | `config/sources.yaml`, `docs/source_vetting.md` | 15 sources vetted; 5 proposed for demo | **Complete** |
| **NLP Extraction & Scope** | Sachi | `atlas/extract.py`, `clean.py`, `products.yaml` | Region/Event/Product extraction tested | **Complete** |
| **PDF & PPTX Report Package** | Sachi | `atlas/report/` (`build.py`, `charts.py`, `pdf`, `pptx`) | Tested on live Databricks run `20261115T045141Z` | **Complete** |

---

## E. Work in Progress

1. **Streamlit Frontend Application (`app/`):** Assigned to Parth in Phase 2 (`parth2.md`). Structure designed; UI logic modules (`app/lib/`) and 5 screens scheduled for implementation.
2. **Expansion of Hand-Vetted Sources:** Ragini is evaluating 5 to 7 additional sources across Canada and specialized technologies (air treatment, blowers, vacuum, gas compressors) to expand the register from 5 to 10-12 proposed sources.
3. **Live Fallback Verification:** Live run `20261115T045141Z` encountered 0 fallback items because no watch entry matched the refused sources. Sachi and Nikhil are aligning watch entries to test switching under real network conditions.

---

## F. Pending Tasks & Operational Ownership

In strict alignment with team governance, **Databricks workspace administration, tokens, cloud connectivity, pipeline execution, and Volume screenshots are owned by Nikhil**. Parth performs downstream quality assurance once actual pipeline records are generated.

| Priority | Task Description | Owner | Dependencies / Blockers | Exact Next Action | Milestone |
| :---: | :--- | :---: | :--- | :--- | :---: |
| **P1** | **PR Review & Merge** | **Nikhil** | PR Compare Link ready | Merge branch `feature/parth-documentation-evidence` into upstream `main`. | Demo Req |
| **P2** | **Merge Keyword Suggestions** | **Nikhil** | `docs/keyword_suggestions.md` | Incorporate approved keywords into `config/keywords.yaml`. | Demo Req |
| **P3** | **Live Databricks Integration Run** | **Nikhil** | Cloud token in `.env` | Execute `python -m atlas.run` and provide `run_id` and Volume path to team. | Demo Req |
| **P4** | **Databricks Volume Screenshots** | **Nikhil** | Completed live run | Capture UI screenshots of Volume catalog (`raw`, `clean`, `output`) for Task P6. | Demo Req |
| **P5** | **Build Streamlit Frontend** | **Parth** | `parent2.md`, `parth2.md` | Implement `app/main.py`, 5 screens, `app/lib/`, and `tests/test_app_logic.py`. | Phase 2 |
| **P6** | **10-Item Empirical QA Audit** | **Parth** | Nikhil's live run output | Open source URLs, inspect against 8 dimensions, log in `docs/check_results.md`. | Demo Req |
| **P7** | **Finalize Demo Note Telemetry** | **Parth** | Nikhil's live run output | Populate Section 5 run metrics in `docs/demo_note.md`. | Demo Req |
| **P8** | **Vet Additional Sources** | **Ragini** | Candidate seeds | Hand-vet 5 to 7 new sources for Canada and gas technologies in `sources.yaml`. | Phase 2 |
| **P9** | **Rebuild Reports from D3 Run** | **Sachi** | Full run with fallback | Run `write_report(run_id, 'pptx')` and hand-check 3 fallback items. | Phase 2 |

---

## G. Detailed Individual Contributions

### Parth (Quality Assurance, Documentation & Frontend Lead)
* **Completed:**
  - Setup local testing environment with spaCy and Presidio; verified 339 tests.
  - Authored strategic client questions document ([`docs/questions_for_atlas_copco.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/questions_for_atlas_copco.md)).
  - Authored plain-English industrial glossary ([`docs/glossary.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/glossary.md)).
  - Researched compressor taxonomy and false-match mitigations ([`docs/keyword_suggestions.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/keyword_suggestions.md)).
  - Built the one-page executive brief template ([`docs/demo_note.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/demo_note.md)).
  - Prepared the 8-dimension QA audit rubric ([`docs/check_results.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/check_results.md)).
  - Created and maintained consolidated team handovers.
* **To Do:**
  - Build Phase 2 Streamlit application (`app/`) and test suite `tests/test_app_logic.py`.
  - Conduct the 10-item empirical QA check once Nikhil provides production records.
  - Finalize Section 5 run numbers in `docs/demo_note.md`.

### Nikhil (Pipeline & Tech Lead)
* **Completed:**
  - Maintained core data models (`atlas/models.py`) and Databricks storage client (`atlas/storage.py`).
  - Implemented relevance filter logic (`atlas/filter.py`) and pipeline runner (`atlas/run.py`).
  - Built Phase 2 settings store (`settings_store.py`), fallback switching (`fallback.py`), and story clustering (`stories.py`).
* **To Do:**
  - Merge Parth's documentation PR into `upstream/main`.
  - Execute live production run on Databricks under dev prefix and provide run records.
  - Maintain Volume folders and capture Volume screenshots for demo evidence.
  - Resolve team questions on default region settings and story clustering thresholds.

### Ragini (Source Vetting & Scout Discovery Lead)
* **Completed:**
  - Vetted initial 15 candidate sources in `docs/source_vetting.md`.
  - Authored Compliance Gate rules ensuring zero scraping violations.
  - Implemented Phase 2 candidate discovery (`discover.py`) and automatic vetting (`vet.py`).
  - Compiled initial 40 discovery seeds in `config/discovery_seeds.yaml`.
* **To Do:**
  - Hand-vet 5 to 7 new sources covering Canadian manufacturers and specialized technologies.
  - Review discovered candidate outputs from live runs.

### Sachi (NLP Extraction & Reporting Lead)
* **Completed:**
  - Implemented main text cleaning (`atlas/clean.py`) and alias deduplication with RapidFuzz.
  - Built PII redaction pipeline with Presidio and spaCy allow-lists.
  - Implemented Phase 2 extraction for geographic regions, industrial event types, and product models.
  - Built PDF and PPTX report generation engines (`atlas/report/`) and validated on Databricks run `20261115T045141Z`.
* **To Do:**
  - Rebuild reports from the final D3/D4 multi-source run.
  - Complete hand-checking on 3 fallback items once generated.

---

## H. Technical Risks, Issues & Mitigations

1. **Non-North-American Geography Leakage:**
   - *Issue:* In run `20261115T045141Z`, 2 items mentioning Portugal and the Netherlands were tagged US because the source itself was US-based.
   - *Resolution:* Sachi pushed fix commit `43bc704` ensuring that places outside North America return `region: null` instead of defaulting to US. Applies to all subsequent runs.
2. **Missing `lxml_html_clean` in Fresh Environments:**
   - *Issue:* Modern `lxml >= 5.2` separated HTML cleaning into `lxml_html_clean`. Without it, `justext` / `trafilatura` fails.
   - *Resolution:* Installed in local `.venv`; documented for Nikhil to append `lxml_html_clean>=0.1.0` to `requirements.txt`.
3. **Empty Fallback Yields in Test Runs:**
   - *Issue:* Switching triggered for refused competitor Ingersoll Rand, but zero articles were found in allowed sources because the watchlist keywords did not match current feed articles.
   - *Resolution:* Align watchlist terms in `config/scout_settings.yaml` with actively published topics.
4. **Cloud Access & Token Security:**
   - *Issue:* Accidental leakage of Databricks personal access tokens.
   - *Resolution:* Strict compliance rule enforced. `.env` is gitignored; tokens are never logged, passed as CLI flags, or displayed in the UI.

---

## I. Client Demo Readiness Assessment

| Deliverable | Status | Missing Evidence / What Is Needed Before Demo |
| :--- | :---: | :--- |
| **Pipeline Architecture Presentation** | **Ready** | Pipeline diagram (`docs/images/pipeline.png`) and `prepare.md` cheat-sheet ready. |
| **5 Proposed Sources Justification** | **Ready** | `docs/source_vetting.md` and `docs/demo_note.md` explain exact selection and exclusions. |
| **Zero Local Storage Compliance** | **Needs Verification** | Nikhil to capture Databricks Volume catalog screenshots (`raw`, `clean`, `output`). |
| **10 Strategic Client Questions** | **Ready** | [`docs/questions_for_atlas_copco.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/questions_for_atlas_copco.md) presentation-ready. |
| **Glossary of Terms** | **Ready** | [`docs/glossary.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/glossary.md) presentation-ready. |
| **Executive 1-Page Brief** | **Needs Numbers** | Parth to populate Section 5 run metrics in [`docs/demo_note.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/demo_note.md) after live run. |
| **10-Item Empirical QA Audit** | **Pending Run** | Parth to audit 10 live items in [`docs/check_results.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/check_results.md) once JSON is provided. |
| **Generated JSON Envelope** | **Pending Run** | Final `poc_<run_id>.json` from Nikhil's demo run. |
| **Executive PDF/PPTX Reports** | **Ready** | Report generator working; ready to compile final demo run data. |

---

## J. Immediate Team Next Steps (Action Plan)

1. **Step 1 (Nikhil):** Merge PR `feature/parth-documentation-evidence` into `main`.
2. **Step 2 (Nikhil):** Merge keyword recommendations from [`docs/keyword_suggestions.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/keyword_suggestions.md) into `config/keywords.yaml`.
3. **Step 3 (Nikhil):** Execute Databricks live pipeline run (`python -m atlas.run`) and post `run_id` and output JSON path in team chat.
4. **Step 4 (Parth):** Perform 10-item empirical audit in [`docs/check_results.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/check_results.md) against live source pages.
5. **Step 5 (Parth):** Fill final telemetry metrics into Section 5 of [`docs/demo_note.md`](file:///c:/Users/Parth%20Sardeshmukh/My_workspace/01_Academics/Semester_5/ML/CP/docs/demo_note.md).
6. **Step 6 (Nikhil):** Capture Volume catalog screenshots for Task P6.
7. **Step 7 (Team):** Conduct dry run of client presentation using `prepare.md`.
