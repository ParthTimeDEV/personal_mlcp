# PROJECT HANDOFF FOR CHATGPT: Atlas Copco Market & Technology PoC

**Project:** Atlas Copco Market & Technology PoC (Group 8, VIT Pune)  
**Client:** Atlas Copco (Industrial Compressor Division / Compressor Technique)  
**Primary Repository:** https://github.com/nikhil191206/personal_mlcp (upstream `main`)  
**Developer Fork:** https://github.com/ParthTimeDEV/personal_mlcp (origin `feature/parth-documentation-evidence`)  
**Assigned Developer:** Parth (Role: Evidence, Documentation, Quality Assurance, Client Deliverables)  
**Latest Update:** 30 October 2026 / Phase 2 Execution Completed  

---

## 1. Project Overview & Business Objective

### Client Background
Atlas Copco is a global Swedish industrial conglomerate operating across four primary business areas:
1. **Compressor Technique** (the largest division, accounting for ~46% of 2025 revenue)
2. **Vacuum Technique**
3. **Power Technique**
4. **Industrial Technique**

Atlas Copco’s aggressive growth strategy relies heavily on strategic acquisitions (e.g., 29 acquisitions announced in 2025 alone). These acquisitions range from local sales-and-service distributors to cutting-edge technology companies that fill specialized engineering gaps.

### Business Objective
The **Market & Technology Study** provides competitive market intelligence. The goal is to build an automated, reliable "Scout" pipeline that continuously monitors industrial compressor developments in the United States. This scout enables Atlas Copco's strategy and M&A teams to:
- Detect emerging compressor technologies earlier.
- Track competitor product launches, facility expansions, partnerships, and executive announcements.
- Identify potential acquisition targets or innovative market entrants before competitors do.

### Context & Client Alignment History
During the initial stakeholder meeting (16 Oct 2026), Atlas Copco provided critical feedback on the team's initial design:
- The initial design was **over-engineered** (unnecessary graph databases, vector embeddings, multi-agent frameworks, complex scrapers).
- The client demanded a **simple, rock-solid Proof of Concept (PoC)** demonstrating raw capability: polite, legally compliant data scraping, transparent rule-based filtering, clean data normalization, and cloud-native storage with **zero local data footprint**.
- Core client directive: **"Results over technical cleverness."**

---

## 2. Client Requirements & Original Problem Statement

### PoC Definition
A minimalist, cloud-first pipeline following a strict pattern: **Input → Engine → Output**.
1. **Input:** Read from vetted, approved public USA sources focused on industrial compressors.
2. **Engine:** Extract structured fields, remove Personal Identifiable Information (PII), drop full HTML/body text, deduplicate, normalize entities, and apply transparent relevance filters.
3. **Output:** Validate data structures against strict contracts and write structured JSON directly to a cloud Databricks Volume from memory.

### Core Non-Negotiable Rules
1. **Strict Cloud Storage (Zero Local Data):** No scraped HTML, raw text, intermediate CSVs, or JSON outputs may ever be written to or cached on local laptops. Data flows strictly memory-to-cloud via the Databricks Files API.
2. **Polite, Ethical & Legal Compliance First:**
   - Scrape only public, logged-out web pages. Paywalled or login-restricted sources are forbidden.
   - Respect `robots.txt` strictly on every run (dynamic parsing before every fetch, honoring `Crawl-delay`).
   - Audit site Terms of Use. If automated access is forbidden, mark the source `blocked` and exclude it.
   - **Never bypass blocks:** No spoofed user agents, no rotating proxy networks, no captcha bypass, no retry storms. Blocked sources are recorded as findings, not system failures.
3. **Facts and Signals, Not Copied Text:** Full articles or long prose are discarded in memory. Only extracted metadata, short key facts (max 3 sentences, <=200 chars each), and source URLs are preserved.
4. **No Guessing or Hallucinations:** Missing fields must remain `null`. Never invent published dates, companies, or specifications. When editorial attribution is ambiguous, default to `"claim"`.
5. **Security & Zero Secrets in Git:** Databricks access tokens and credentials live exclusively in untracked `.env` files. Never commit, log, or paste credentials.
6. **No AI/LLMs in PoC Phase:** The Friday PoC relies entirely on deterministic Python rules, regex, spaCy NER, and Presidio anonymization. LLM summarization is deferred to later project phases.

---

## 3. Complete Technical Architecture

```
                       INPUT STAGE (Ragini)
                   +---------------------------+
                   |    config/sources.yaml    |  (Source Register)
                   +-------------+-------------+
                                 |
                                 v
                   +---------------------------+
                   |     Compliance Gate       |  Obey robots.txt, Terms,
                   |   (atlas/compliance.py)   |  Polite crawl-delay (>=3s)
                   +-------------+-------------+
                                 |
                                 v
                   +---------------------------+
                   |         Collector         |  RSS first, HTML listings second;
                   |    (atlas/collect.py)     |  Memory-only FetchedPage
                   +-------------+-------------+
                                 |
                                 | ---> Writes raw/<source_id>/<run_id>.json (RawItem metadata)
                                 v
                       ENGINE STAGE (Sachi)
                   +---------------------------+
                   |         Extractor         |  Trafilatura in memory; metadata,
                   |    (atlas/extract.py)     |  Presidio PII scrub (en_core_web_sm),
                   |                           |  Key facts, keywords, text dropped!
                   +-------------+-------------+
                                 |
                                 v
                   +---------------------------+
                   |          Cleaner          |  URL normalisation, dedup by URL &
                   |     (atlas/clean.py)      |  SHA-256 fingerprint, RapidFuzz aliases
                   +-------------+-------------+
                                 |
                                 v
                       OUTPUT STAGE (Nikhil)
                   +---------------------------+
                   |     Relevance Filter      |  4 checks: compressor_related,
                   |    (atlas/filter.py)      |  north_america, credible_source, recent.
                   +-------------+-------------+
                                 |
                                 | ---> Writes clean/<source_id>/<run_id>.json (All Items)
                                 | ---> Writes facts/<source_id>/<run_id>.json (Passed Items)
                                 v
                   +---------------------------+
                   |     Run Orchestrator      |  Validates OutputEnvelope, writes:
                   |      (atlas/run.py)       |  output/poc_<run_id>.json
                   |                           |  logs/<run_id>.json
                   +-------------+-------------+
                                 |
                                 v
                   +---------------------------+
                   |     Databricks Volume     |  /Volumes/atlas_poc/default/data/
                   |    (atlas/storage.py)     |  (<prefix>/...)
                   +---------------------------+
```

---

## 4. Technology Stack & Dependencies

| Layer | Library / Tool | Version / Details | Purpose |
|---|---|---|---|
| **Runtime** | Python | 3.12.0 (supported 3.11+) | Core programming language |
| **HTTP Client** | `httpx` | 0.28.1 | Synchronous HTTP client with polite timeouts, redirect validation, and mockable via `MockTransport` |
| **Feed Parser** | `feedparser` | 6.0.14 | Parses RSS 2.0 / Atom XML feeds |
| **HTML Parsing** | `trafilatura` & `lxml` | 2.3.1 / 6.1.3 | High-precision web text and metadata extraction in memory |
| **HTML Cleaning** | `lxml_html_clean` | 0.4.6 | Required dependency for `justext` / `trafilatura` on modern `lxml` |
| **PII Scrubbing** | `presidio-analyzer` & `presidio-anonymizer` | 2.2.366 | Identifies and scrubs `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER` |
| **NLP Engine** | `spacy` + `en_core_web_sm` | 3.8.18 / 3.8.0 | Lightweight NLP model backing Presidio (explicitly avoids 400MB `en_core_web_lg`) |
| **Fuzzy Matching**| `rapidfuzz` | 3.14.6 | `fuzz.token_sort_ratio` for company alias resolution (threshold >= 92) |
| **Data Validation**| `pydantic` & `pydantic-settings` | 2.14.3 / 2.16.3 | Schema contracts, serialization, validation, and `.env` parsing |
| **Cloud SDK** | `databricks-sdk` | 0.166.0 | `WorkspaceClient.files` for memory-buffered Volume file operations |
| **Testing** | `pytest` | 9.2.0 | Offline test suite with mocked networks and storage (127 passed in 14.28s) |

---

## 5. Repository Directory Structure

```
personal_mlcp/
├── .env.example                  # Template for environment configuration
├── .gitignore                    # Excludes .env, .venv, pycache, data caches
├── Friday_PoC_Spec.md            # Initial customer specification (baseline)
├── README.md                     # Quickstart documentation (Owner: Nikhil)
├── nikhil.md                     # Task specification for Nikhil
├── parent.md                     # Single source of truth master brief
├── parth.md                      # Task specification for Parth (Current role)
├── pytest.ini                    # Test runner configuration (pythonpath = .)
├── ragini.md                     # Task specification for Ragini
├── requirements.txt              # Production package requirements (Owner: Nikhil)
├── sachi.md                      # Task specification for Sachi
├── wd.md                         # Work distribution summary
├── PROJECT_HANDOFF_FOR_CHATGPT.md # Comprehensive AI handoff context
├── atlas/                        # Core Python package
│   ├── __init__.py
│   ├── clean.py                  # Deduplication & company alias matching (Sachi)
│   ├── collect.py                # RSS & HTML web collector (Ragini)
│   ├── compliance.py             # robots.txt & terms compliance gate (Ragini)
│   ├── extract.py                # trafilatura & Presidio PII extractor (Sachi)
│   ├── filter.py                 # 4-stage relevance filter (Nikhil)
│   ├── models.py                 # Shared Pydantic data contracts (Nikhil)
│   ├── run.py                    # Orchestrator & CLI entrypoint (Nikhil)
│   ├── settings.py               # Settings & .env loader (Nikhil)
│   ├── storage.py                # Databricks SDK memory upload/download (Nikhil)
│   └── storage_check.py          # Storage validation script (Nikhil)
├── config/                       # Declarative configuration files
│   ├── aliases.yaml              # Canonical company names & aliases (Sachi)
│   ├── keywords.yaml             # Filter & signal keywords (Nikhil)
│   ├── sources.yaml              # Vetted source register (Ragini)
│   └── technologies.yaml         # Compressor technology patterns (Sachi)
├── docs/                         # Project documentation & deliverables
│   ├── check_results.md          # 10-item manual verification report (Parth)
│   ├── decisions.md              # Shared immutable decision log
│   ├── demo_note.md              # One-page executive demo note (Parth)
│   ├── glossary.md               # Plain-English technical & industry glossary (Parth)
│   ├── keyword_suggestions.md    # Recommended additions to keywords.yaml (Parth)
│   ├── parth_contribution_and_team_status.md # Comprehensive team progress report (Parth)
│   ├── questions_for_atlas_copco.md # 10 strategic questions for client (Parth)
│   └── source_vetting.md         # Source compliance & vetting audit (Ragini)
└── tests/                        # Comprehensive test suite (127 passing tests)
    ├── test_clean.py             # 9 tests for deduplication & alias matching
    ├── test_collect.py           # 10 tests for RSS/HTML collection
    ├── test_compliance.py        # 9 tests for compliance gate & robots.txt
    ├── test_extract.py           # 10 tests for text extraction & PII scrubbing
    ├── test_filter.py            # 9 tests for 4-check relevance filter
    └── test_run.py               # 6 tests for orchestrator execution & logging
```

---

## 6. Important Modules & Responsibilities

### `atlas/models.py` (Owner: Nikhil)
The bedrock data contract. Must never be redefined.
- `Source`: Represents a row in `config/sources.yaml`. Contains `source_id`, `name`, `url`, `type` (`competitor`, `trade_news`, `government`), `access_method` (`rss`, `html`, `api`), `feed_url`, `item_url_pattern`, `robots_status`, `terms_status`, `vetting_status`, `status` (`proposed`, `approved`, `blocked`, `needs_permission`), `region`, `licence_note`, `crawl_delay`.
- `GateDecision`: Result of compliance check (`allowed: bool`, `reasons: list[str]`).
- `Refusal`: Structured refusal event logged during compliance check or collection (`source_id`, `url`, `reason`, `timestamp`).
- `FetchedPage`: Raw fetched page in memory (`html: str` excluded from dumps).
- `RawItem`: Metadata of fetched pages written to `raw/`.
- `FilterResult`: The 4 checks (`compressor_related`, `north_america`, `credible_source`, `recent`, `passed`, `reasons`, `date_missing`).
- `Item`: The core evidence record. Holds `id` (12-char SHA-256), `source_id`, `source_name`, `source_url`, `collected_at`, `published_at`, `title`, `company`, `product` (`null` on Friday), `technology`, `key_facts` (max 3, each max 200 chars), `label` (`fact` vs `claim`), `filter`, `page_fingerprint`, `personal_data_removed`, `matched_keywords`, `mentions_us_location`, `industrial_hint`.
- `CleanResult`: Wraps `items: list[Item]` and `duplicates_dropped: int`.
- `OutputEnvelope`: Final client output JSON containing `run_id`, `generated_at`, `scope`, `sources: list[SourceSummary]`, `items: list[Item]`.
- `RunLog`: Execution telemetry and audit logs.

### `atlas/compliance.py` (Owner: Ragini)
- `load_register(path)`: Loads and validates `config/sources.yaml`.
- `ComplianceGate`:
  - Enforces `CONTACT_EMAIL` in User-Agent (`AtlasCopcoStudentPoC/0.1 (+contact: {email})`).
  - `check_source(source)`: Pre-flight check. Refuses blocked/unreachable sources. Allows only `status in {"proposed", "approved"}` and `vetting_status == "working"`.
  - In-memory `robots.txt` fetch and parsing using `urllib.robotparser.RobotFileParser`. Caches per host for run duration.
  - `can_fetch(source, url)`: Dynamic URL-level robots check.
  - `wait(source)`: Host-level politeness enforcement using `time.monotonic()` (minimum delay 3.0 seconds, or `Crawl-delay`).

### `atlas/collect.py` (Owner: Ragini)
- `collect_source(source, gate, max_items=20, client=None)`:
  - If `access_method == "rss"`: Fetches feed XML via `httpx`, parses via `feedparser`, extracts candidate article URLs, then fetches each full article page into memory (never using RSS summary as body).
  - If `access_method == "html"`: Fetches listing page, extracts `<a href>` links matching `item_url_pattern` via `lxml.html`.
  - Ensures all targets are on the same host (refuses cross-host redirects).
  - Yields `FetchedPage` instances in memory.

### `atlas/extract.py` (Owner: Sachi)
- `extract_item(page, source) -> Item`:
  - Extracts clean text and metadata using `trafilatura`.
  - Normalizes headline and published date (`YYYY-MM-DD`). Future dates or garbage dates become `null`.
  - Scrubs PII using `presidio-analyzer` and `presidio-anonymizer` backed by `en_core_web_sm`. Redacts `PERSON`, `PHONE_NUMBER`, `EMAIL_ADDRESS` into `<PERSON>`, `<PHONE>`, `<EMAIL>`.
  - Signals extraction: checks `clean_text` against `config/keywords.yaml` (`matched_keywords`, `industrial_hint`, `mentions_us_location`).
  - Classifies technology using patterns in `config/technologies.yaml`.
  - Extracts key facts: max 3 sentences containing compressor keywords, quantitative specs, or event verbs, truncated to <= 200 characters.
  - Assigns `label`: `"claim"` by default or for competitor press; `"fact"` only for government sources or verifiable neutral trade reporting.
  - Drops raw HTML and text completely from memory; stores only `page_fingerprint` (SHA-256 of cleaned text).

### `atlas/clean.py` (Owner: Sachi)
- `clean_items(items, aliases_path)`:
  - Normalizes URLs (strips tracking query params `utm_*`, `gclid`, fragments, trailing slashes).
  - Deduplicates items: drops identical URLs; drops identical `page_fingerprint`s (keeping the more complete record).
  - Canonicalizes company names using `config/aliases.yaml` and `rapidfuzz.process.extractOne` (token_sort_ratio >= 92).

### `atlas/filter.py` (Owner: Nikhil)
- `apply_filter(items, sources_by_id, today, recent_months=12, keywords_path)`:
  - Evaluates 4 transparent yes/no rules:
    1. `compressor_related`: `matched_keywords` non-empty OR title contains a compressor keyword. (Failure code: `no_compressor_keyword`).
    2. `north_america`: Source region in `{"US", "CA", "MX", "NA"}` OR `mentions_us_location == True`. (Failure code: `not_north_america`).
    3. `credible_source`: Source exists in register, `vetting_status == "working"`, `status in {"proposed", "approved"}`. (Failure code: `source_not_credible`).
    4. `recent`: `published_at` within last 12 months. If missing/null -> `date_missing`. If in future -> `date_in_future`. If > 12 months old -> `too_old`.
  - `passed = all four are True`. Populates `FilterResult.reasons` with all failures.

### `atlas/run.py` (Owner: Nikhil)
- Pipeline orchestrator CLI (`python -m atlas.run [--only SOURCE_ID] [--max-items N]`).
- Sequences: ensure folders -> copy register -> compliance gate -> collect -> write raw -> extract -> clean -> filter -> write clean & facts -> validate OutputEnvelope -> write output -> write log -> print console summary table -> perform local data audit.

### `atlas/storage.py` (Owner: Nikhil)
- Unity Catalog volume accessor.
- Uploads memory buffers directly to `/Volumes/atlas_poc/default/data/<prefix>/`.
- Methods: `ensure_folders()`, `write_json(path, obj)`, `read_json(path)`, `list_dir(path)`.

---

## 7. Complete Pipeline Execution Flow

```
[Start CLI] python -m atlas.run
    │
    ├── 1. Generate run_id (UTC ISO YYYYMMDDTHHMMSSZ). Initialize telemetry RunLog.
    ├── 2. storage.ensure_folders(): Creates 6 Volume folders under <prefix>/.
    ├── 3. compliance.load_register(): Validates sources.yaml.
    │      Uploads to: <prefix>/source_register/sources.json
    ├── 4. Initialize ComplianceGate: Verifies CONTACT_EMAIL.
    │
    ├── 5. FOR EACH SOURCE in register (respecting --only):
    │      │
    │      ├── a. gate.check_source(source)
    │      │      └── If not allowed: record refusal, emit SourceSummary(status), continue.
    │      │
    │      ├── b. collect_source(source, gate, max_items):
    │      │      ├── Fetch RSS XML or HTML list page
    │      │      ├── Enforce gate.can_fetch(url) and gate.wait(source) (polite delay)
    │      │      └── Yield FetchedPage objects in memory.
    │      │
    │      ├── c. Write raw metadata:
    │      │      └── Upload RawItem list to: <prefix>/raw/<source_id>/<run_id>.json
    │      │
    │      ├── d. FOR EACH PAGE:
    │      │      └── extract_item(page, source):
    │      │          ├── Parse title, published date
    │      │          ├── Presidio scrub PII -> <PERSON>, <EMAIL>, <PHONE>
    │      │          ├── Match compressor keywords, US locations, technologies
    │      │          ├── Extract max 3 key facts (<=200 chars)
    │      │          ├── Assign label ('fact' vs 'claim')
    │      │          ├── Compute SHA-256 text fingerprint
    │      │          └── DISCARD RAW TEXT & HTML FROM MEMORY.
    │      │
    │      ├── e. clean_items(items):
    │      │      ├── Deduplicate by normalized URL & fingerprint
    │      │      └── Standardize company names via RapidFuzz + aliases.yaml
    │      │
    │      ├── f. apply_filter(items):
    │      │      └── Evaluate 4 checks: compressor, NA, credible, recent.
    │      │
    │      └── g. Write intermediate records to Databricks:
    │             ├── All items -> <prefix>/clean/<source_id>/<run_id>.json
    │             └── Passed items only -> <prefix>/facts/<source_id>/<run_id>.json
    │
    ├── 6. Aggregate OutputEnvelope (passed items across all sources).
    │      Validate via OutputEnvelope.model_validate().
    │      Upload to: <prefix>/output/poc_<run_id>.json
    │
    ├── 7. Finalize RunLog (errors, gate decisions, refusals, execution counts).
    │      Upload to: <prefix>/logs/<run_id>.json
    │
    ├── 8. Print formatted console summary table.
    │
    └── 9. Local Data Check:
           Walk project directory (excluding .venv, .git, caches).
           Assert zero new files appeared on local disk!
```

---

## 8. Databricks Integration & Storage Architecture

### Cloud Infrastructure
- **Databricks Host:** `https://dbc-57cf1ee1-bdf1.cloud.databricks.com`
- **Unity Catalog Hierarchy:**
  - Catalog: `atlas_poc`
  - Schema: `default`
  - Volume: `data`
  - Root Path: `/Volumes/atlas_poc/default/data/`

### Partitioning & Prefix Layout
```
/Volumes/atlas_poc/default/data/
    ├── dev/parth/                      <-- Parth's isolated development prefix
    │   ├── source_register/sources.json
    │   ├── raw/<source_id>/<run_id>.json
    │   ├── clean/<source_id>/<run_id>.json
    │   ├── facts/<source_id>/<run_id>.json
    │   ├── output/poc_<run_id>.json
    │   └── logs/<run_id>.json
    ├── dev/nikhil/
    ├── dev/ragini/
    ├── dev/sachi/
    └── [empty prefix for final demo run]  <-- Only Nikhil runs with ATLAS_PATH_PREFIX=""
        ├── source_register/
        ├── raw/
        ├── clean/
        ├── facts/
        ├── output/poc_<run_id>.json
        └── logs/<run_id>.json
```

---

## 9. Team Members & Responsibility Mapping

| Team Member | Module / Scope | Key Deliverables | File Ownership | Incoming Dependencies | Outgoing Dependencies |
|---|---|---|---|---|---|
| **Nikhil** | Core orchestrator, filter, Databricks storage, config coordination | `atlas/filter.py`, `atlas/run.py`, Databricks volume setup, final demo run | `atlas/filter.py`, `atlas/run.py`, `atlas/models.py`, `atlas/settings.py`, `atlas/storage.py`, `atlas/storage_check.py`, `config/keywords.yaml`, `requirements.txt`, `README.md` | Needs clean items from Sachi; needs vetted sources from Ragini; merges keyword suggestions from Parth | Provides `run_id`, run summaries, and dev prefix data to Parth for hand-checking |
| **Ragini** | Input stage: compliance gate, source vetting, politeness, collector | Source register with 8+ candidates, ComplianceGate, polite collector | `config/sources.yaml`, `docs/source_vetting.md`, `atlas/compliance.py`, `atlas/collect.py`, `tests/test_compliance.py`, `tests/test_collect.py` | Needs contact email from settings; needs team consensus on final 5 sources | Provides in-memory `FetchedPage`s to Sachi; provides source vetting details to Parth |
| **Sachi** | Engine stage: text extraction, PII removal, deduplication, company cleaning | `extract_item`, `clean_items`, alias matching, technology mapping | `atlas/extract.py`, `atlas/clean.py`, `config/aliases.yaml`, `config/technologies.yaml`, `tests/test_extract.py`, `tests/test_clean.py` | Needs `FetchedPage`s from Ragini | Provides normalized `Item`s to Nikhil; receives extraction issue reports from Parth |
| **Parth** *(You)* | Quality verification, client documentation, glossary, keyword research, demo collateral | Questions document, glossary, keyword suggestions, demo note, 10-item audit, volume screenshot | `docs/questions_for_atlas_copco.md`, `docs/glossary.md`, `docs/keyword_suggestions.md`, `docs/demo_note.md`, `docs/check_results.md`, `docs/parth_contribution_and_team_status.md` | Needs run metrics from Nikhil, source status from Ragini, live URLs from pipeline runs | Delivers client-ready documentation, hand-check audit report, team status summary, and suggested keywords |

---

## 10. Parth's Exact Responsibilities from `parth.md`

Parth is the **Quality Assurance, Domain Analyst, and Client Communications Lead**. Parth does not modify the pipeline codebase; instead, Parth audits pipeline behavior, ensures strict client alignment, enriches domain keywords, verifies output validity, and prepares executive demo materials.

### Mandatory Deliverables
1. `docs/questions_for_atlas_copco.md` (Client alignment document)
2. `docs/glossary.md` (Plain-English technical dictionary)
3. `docs/keyword_suggestions.md` (Domain keyword & location enhancements)
4. `docs/demo_note.md` (One-page client demo executive briefing)
5. `docs/check_results.md` (Rigorous 10-item empirical hand-check against live URLs)
6. `docs/parth_contribution_and_team_status.md` (Team contribution & dependency report)
7. Databricks Volume Screenshots (Saved **outside** the repo for client presentation)

### Strict Operational Constraints
- **Do not modify core pipeline code** (`atlas/`).
- **Do not modify configuration files** (`config/keywords.yaml`, `config/sources.yaml`, etc.); submit suggestions via docs for the owners to merge.
- **Do not invent numbers, quotes, or statuses.** Where data is pending a pipeline run or input from a teammate, use explicit `TODO(owner)` tags.
- **Never commit credentials, access tokens, or sensitive information.**
- **Never commit screenshots or raw scraped data files.**

---

## 11. Detailed Task-by-Task Status & Breakdown (P0 to P6)

| Task ID | Deliverable File | Previous Status | Current Verified Status | Work Completed | Remaining Work | Blockers & Dependencies |
|---|---|---|---|---|---|---|
| **P0** | `.env` / Local Environment | Not configured | **Locally Verified / Storage Pending Token** | Installed Python 3.12 venv, all dependencies, spaCy `en_core_web_sm`, installed `lxml_html_clean`, verified 127 offline tests pass. Created `.env` with `dev/parth` prefix. | Run `storage_check` to PASS once token is added. | Blocked on user's personal Databricks access token. |
| **P1** | `docs/questions_for_atlas_copco.md` | Initial draft | **Completed & Verified** | Audited against all 10 questions from `parth.md`. Confirmed high business/technical value, clear "Why we ask" and "What we do with answer", zero redundancy. | None. Ready for Friday presentation. | None. Independent work complete. |
| **P2** | `docs/glossary.md` | Initial draft | **Completed & Verified** | Verified alphabetical ordering, plain-English definitions, coverage of compressor engineering concepts and pipeline architecture terms. Suitable for verbal explanation. | None. Ready for presentation. | None. Independent work complete. |
| **P3** | `docs/keyword_suggestions.md` | Initial list | **Completed & Enriched** | Structured into technical compressor categories (types, motor/drives, air treatment, standards), industrial sectors, US manufacturing hubs, detailed false-positive risk analysis, and structured merge table for Nikhil. | Nikhil merges approved keywords into `config/keywords.yaml`. | Waiting on Nikhil to review and merge into config. |
| **P4** | `docs/demo_note.md` | Initial template with outdated sources | **Template Ready & Synchronized** | Synchronized with finalized 5 sources from `source_vetting.md` (Quincy & Pumps & Systems replacing Atlas Copco USA & Kaeser). Detailed 6 blocked/unreachable sources, 4 relevance filters, and QA audit methodology. Retained clean `TODO` markers. | Fill Section 5 run numbers and Section 6 audit summary after demo run. | Dependent on final demo run execution and telemetry by Nikhil. |
| **P5** | `docs/check_results.md` | Blank template | **QA Framework Complete** | Structured 10-item empirical QA framework covering all 8 evaluation criteria, live URL verification instructions, failure note routing protocol, and global storage assertions. All 10 item rows clearly designated pending live run. | Execute live URL inspection on 10 records from `output/poc_<run_id>.json`. | Dependent on Nikhil providing dev/integration run ID and cloud path. |
| **P6** | Volume Screenshots | Unspecified | **Protocol Prepared** | Documented exact screenshot requirements (6 Volume folders, open JSON payload view, privacy masking, off-repo storage location). | Capture screenshot in Databricks UI once demo run finishes. | Dependent on final demo run execution and Databricks UI access. |

---

## 12. Dependencies & Pending Inputs from Teammates

| Dependency Item | Providing Teammate | Parth's Dependent Task | Action Required | Current Status |
|---|---|---|---|---|
| Databricks Workspace Access Token | User | P0 (Storage Check), P5 (Audit), P6 (Screenshots) | Generate token in Databricks UI, paste into `.env` | **Pending (User Action)** |
| Merge Approved Keywords | Nikhil | P3 (Keyword suggestions) | Review `docs/keyword_suggestions.md` and merge into `config/keywords.yaml` | Ready for Nikhil's review |
| Update `requirements.txt` | Nikhil | Repository Health | Append `lxml_html_clean` to `requirements.txt` | Suggested to Nikhil |
| Integration Dev Run (`dev/nikhil` or `dev/parth`) | Nikhil | P5 (10-item hand check) | Execute run, provide `run_id` and confirm Databricks path | Awaiting live integration run |
| Final Demo Run Telemetry & Counts | Nikhil | P4 (Demo note section 5) | Provide exact counts (collected, dropped, passed) | Awaiting final demo run |
| Vetted Source Audit (`source_vetting.md`) | Ragini | P4 (Demo Note section 3 & 4) | Finalized candidate statuses integrated into demo note | Fully synchronized |
| Fixes for Extraction / Date / PII bugs | Sachi | P5 (Hand-check follow-up) | Sachi resolves any extraction failures found in audit | On call during Friday dry run |

---

## 13. Environment Setup & Configuration Instructions

### Prerequisites
- Python 3.12 (or 3.11+)
- Git configured with SSH or personal access token

### Setup Commands (Windows PowerShell)
```powershell
# 1. Clone repository fork
git clone https://github.com/ParthTimeDEV/personal_mlcp.git cp
cd cp

# 2. Configure remotes
git remote add upstream https://github.com/nikhil191206/personal_mlcp.git
git fetch upstream

# 3. Create and activate virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies and models
pip install -r requirements.txt
pip install lxml_html_clean    # Required for modern lxml with trafilatura
python -m spacy download en_core_web_sm

# 5. Create environment configuration
copy .env.example .env
```

### Environment Variables (`.env`)
```ini
DATABRICKS_HOST=https://dbc-57cf1ee1-bdf1.cloud.databricks.com
DATABRICKS_TOKEN=dapi...               # YOUR PERSONAL ACCESS TOKEN (Do not commit)
DATABRICKS_CATALOG=atlas_poc
DATABRICKS_SCHEMA=default
DATABRICKS_VOLUME=data
CONTACT_EMAIL=industrymlcp@gmail.com
ATLAS_PATH_PREFIX=dev/parth            # Parth's isolated development folder
```

---

## 14. Commands Required to Run and Test the Project

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 1. Run full offline test suite (All 127 tests must pass)
pytest -q

# 2. Verify Databricks volume connectivity and memory-only storage
python -m atlas.storage_check

# 3. Test pipeline on a single source (Development sandbox)
python -m atlas.run --only airbestpractices_news --max-items 3

# 4. Run pipeline on all sources with item limit
python -m atlas.run --max-items 5

# 5. Inspect local disk state (must show zero data files created)
git status
```

---

## 15. Current Git Configuration & Branch Information

- **Working Directory:** `C:\Users\Parth Sardeshmukh\My_workspace\01_Academics\Semester_5\ML\CP`
- **Active Branch:** `feature/parth-documentation-evidence`
- **Active Commit Hash:** `64c2a8e39aeec1ee0d0fbb42499a000adca5ad0d` (Short: `64c2a8e`)
- **Origin Remote (Push destination):** `https://github.com/ParthTimeDEV/personal_mlcp.git`
- **Upstream Remote (Tracking source):** `https://github.com/nikhil191206/personal_mlcp.git`
- **Latest Upstream Commit Inspected:** `5f07b80a4629b4379acd80ea6dcbcc4da0338d0e` (`[sachi] allow-list: canonical names, names without legal suffix, single brand words`)
- **Upstream Alignment:** Fully synchronized; 0 divergence or merge conflicts.
- **Push Confirmation:** Verified pushed and tracked on `origin/feature/parth-documentation-evidence`.

---

## 16. Known Limitations, Risks & Unresolved Questions

### Known Limitations & Bottlenecks
1. **Dependency Gap:** Modern `lxml` (>=5.2) separates `clean` into `lxml_html_clean`. `requirements.txt` currently omits `lxml_html_clean`. We installed it locally in `.venv`, but Nikhil must append `lxml_html_clean` to `requirements.txt`.
2. **Access Blocked Competitor Sites:**
   - **Ingersoll Rand:** Returns HTTP 429 (Rate limited) on initial request.
   - **Business Wire & Plant Engineering:** Return HTTP 403.
   - **CAGI, PR Newswire, Plant Services:** Expressly forbid scraping in Terms of Use.
   - *Strategic mitigation:* Highlighted in `docs/questions_for_atlas_copco.md` to request client-sponsored access or API keys.
3. **Date Omission in Blogs:** Kaeser Compressors USA blog posts lack publication datelines in their HTML, causing them to fail the 12-month recency filter (`date_missing`). Kaeser was properly replaced by Quincy Compressor in the proposed 5.

### Open Questions for Team Coordination
1. Confirmation of exact Friday demo time with Atlas Copco.
2. Confirming that Nikhil has executed the dev run and provided the active `run_id` for hand-checking.

---

## 17. Recommended Implementation Sequence

```
[Phase 1: Environment & Connectivity]
  ├── Step 1: Obtain personal Databricks Access Token from workspace UI.
  ├── Step 2: Populate DATABRICKS_TOKEN in .env.
  └── Step 3: Execute `python -m atlas.storage_check` (Verify PASS).

[Phase 2: Independent Documentation Review & Expansion] (COMPLETED)
  ├── Step 4: Review `docs/questions_for_atlas_copco.md` for client alignment.
  ├── Step 5: Review `docs/glossary.md` to ensure presentation readiness.
  ├── Step 6: Expand `docs/keyword_suggestions.md` with categories & false-positive analysis.
  ├── Step 7: Update `docs/demo_note.md` with verified 5 sources & filter explanations.
  ├── Step 8: Prepare `docs/check_results.md` 10-item empirical QA framework.
  ├── Step 9: Create `docs/parth_contribution_and_team_status.md` team report.
  └── Step 10: Commit and push independent documentation to origin fork.

[Phase 3: Integration & Hand-Check Audit] (NEXT)
  ├── Step 11: Await Nikhil's dev run notification (obtain prefix and run_id).
  ├── Step 12: Open `output/poc_<run_id>.json` in Databricks Volume UI.
  ├── Step 13: Audit 10 items across 3+ sources; populate `docs/check_results.md`.
  └── Step 14: Dispatch any extraction errors to Sachi and filter anomalies to Nikhil.

[Phase 4: Final Demo Collateral & Submission]
  ├── Step 15: Ingest final demo run metrics into `docs/demo_note.md` (remove all TODOs).
  ├── Step 16: Capture Volume UI screenshot showing 6 folders (save outside repo).
  ├── Step 17: Run `pytest -q` to guarantee zero regressions.
  └── Step 18: Commit final populated documents and push to origin fork.
```

---

## 18. Deliverables Checklist & Acceptance Criteria

- [x] `docs/questions_for_atlas_copco.md` is complete, professional, and max 10 questions.
- [x] `docs/glossary.md` is complete, alphabetical, and explainable out loud.
- [x] `docs/keyword_suggestions.md` follows exact markdown schema with false match risks.
- [x] `docs/demo_note.md` template is synchronized with 5 proposed sources and 6 excluded sources.
- [x] `docs/check_results.md` framework covers all 8 audit criteria and global storage checks.
- [x] `docs/parth_contribution_and_team_status.md` summarizes team progress and blockers.
- [x] `PROJECT_HANDOFF_FOR_CHATGPT.md` continuously updated with live project state.
- [ ] `docs/demo_note.md` has all `TODO` placeholders replaced with real run metrics.
- [ ] `docs/check_results.md` contains 10 verified live URLs with error reporting logged.
- [ ] Databricks Volume screenshot captured and stored **outside** repository.
- [x] Zero secrets, tokens, raw scraped texts, or screenshots committed to git.
- [x] `git status` verifies clean local directory with no untracked data caches.

---

## 19. Distinction: Verified Facts, Assumptions & Pending TODOs

### Verified Facts
- Repository cloned directly into `cp` folder; remotes `origin` and `upstream` properly set.
- Python 3.12 virtual environment configured with all dependencies and `en_core_web_sm`.
- 127 offline unit tests pass with 100% success rate in 14.28s.
- `lxml_html_clean` identified as necessary addition to `requirements.txt`.
- `.env` is confirmed ignored by `.gitignore`.
- Databricks storage architecture verified: `/Volumes/atlas_poc/default/data/`.
- Proposed sources verified in `config/sources.yaml` & `docs/source_vetting.md`.

### Working Assumptions
- The team will proceed with the proposed 5 sources: Compressed Air Best Practices, Quincy Compressor, Sullair US, Pumps & Systems, US DOE.
- Nikhil will execute the integration run and final demo run on schedule and provide run telemetry.
- Sachi and Ragini will be on call during Friday dry runs to patch extraction or collection anomalies.

### Pending TODOs
- `TODO(Parth)`: Obtain personal Databricks token, paste into `.env`, verify `python -m atlas.storage_check` PASS.
- `TODO(Nikhil)`: Append `lxml_html_clean` to `requirements.txt`.
- `TODO(Nikhil)`: Merge suggested keywords from `docs/keyword_suggestions.md`.
- `TODO(Nikhil)`: Provide `run_id` and run statistics from integration run.
- `TODO(Parth)`: Complete 10-item hand-check in `docs/check_results.md` once run data exists.
- `TODO(Parth)`: Populate `docs/demo_note.md` with verified run numbers.
- `TODO(Parth)`: Capture Databricks Volume screenshots outside repository.

---

## 20. Progress History & Activity Log

- **Phase 1 (Environment Setup & Architectural Analysis):**
  - Cloned personal fork directly into `cp/` without nested folders.
  - Configured git remotes (`origin`: fork, `upstream`: main repo). Created feature branch `feature/parth-documentation-evidence`.
  - Built Python 3.12 virtual environment, installed dependencies, downloaded spaCy `en_core_web_sm`.
  - Diagnosed `ImportError` in `justext`/`trafilatura` under modern `lxml`, installed `lxml_html_clean` in `.venv`.
  - Executed offline test suite: 127 of 127 tests passed.
  - Created `.env` with `dev/parth` prefix. Executed `python -m atlas.storage_check` (reported honest auth block due to missing token).
  - Authored initial comprehensive `PROJECT_HANDOFF_FOR_CHATGPT.md`.
- **Phase 2 (Independent Deliverables Completion & Fork Push):**
  - Executed upstream sync checks: fetched `upstream/main`, confirmed commit `5f07b80a4629b4379acd80ea6dcbcc4da0338d0e` with 0 divergence.
  - Verified and confirmed `docs/questions_for_atlas_copco.md` (10 strategic questions).
  - Verified and confirmed `docs/glossary.md` (alphabetical plain-English dictionary).
  - Extensively enhanced `docs/keyword_suggestions.md` with 5 technical categories, false-match risk analysis, and a structured merge guide for Nikhil.
  - Fully updated `docs/demo_note.md` to synchronize with the 5 proposed sources from `source_vetting.md`, documented the 6 excluded sources, detailed the 4 relevance filters, and retained explicit `TODO` markers.
  - Enhanced `docs/check_results.md` with the 8-dimension audit criteria, responsible owner mapping, live URL inspection procedure, global assertions, and Task P6 screenshot protocol.
  - Created new team handoff report: `docs/parth_contribution_and_team_status.md`.
  - Re-validated offline test suite with `pytest -q` (127 passed).
  - Staged and committed verified documentation deliverables to `feature/parth-documentation-evidence` (commit `64c2a8e39aeec1ee0d0fbb42499a000adca5ad0d`) and pushed successfully to `origin/feature/parth-documentation-evidence`.
