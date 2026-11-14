# Hand-Check Audit of 10 Output Items

**Author:** Parth (Quality Assurance Lead)  
**Status:** Audit Framework Prepared — Awaiting Pipeline Run Execution  
**Target Artifact:** `/Volumes/atlas_poc/default/data/<prefix>/output/poc_<run_id>.json`  

> **Integrity Notice:** This document is the quality assurance framework for the 10-item empirical verification. In strict accordance with project rules, no row below may be guessed or fabricated. Individual table cells will be filled only after inspecting the live web page corresponding to each extracted record from an actual Databricks pipeline run.

---

## 1. Audit Purpose & Verification Methodology

The purpose of this hand-check is to verify that the automated pipeline extracts true facts, eliminates personal data, classifies technology accurately, and applies transparent relevance filters without hallucination or data corruption.

### Step-by-Step Procedure
1. **Access Cloud Output:** Open Databricks workspace (`https://dbc-57cf1ee1-bdf1.cloud.databricks.com`), navigate to Catalog `atlas_poc` → Schema `default` → Volume `data` → `<prefix>` → `output` → `poc_<run_id>.json`.
2. **Item Selection:** Pick **10 distinct items** across at least **3 different sources** (e.g., Compressed Air Best Practices, Quincy Compressor, Sullair US, Pumps & Systems, US DOE).
3. **Live Web Inspection:** For each selected record, open `source_url` in a standard web browser.
4. **Evaluate Eight Audit Dimensions:**

| # | Dimension | Evaluation Standard | Pass Criteria (`yes`) | Failure Criteria (`no`) | Responsible Owner |
|---|---|---|---|---|---|
| 1 | **Title Match** | Compare `item.title` to the live article headline. | Headline matches accurately (ignoring minor whitespace normalization). | Truncated, garbled, or captures navigation text. | Sachi (`extract.py`) |
| 2 | **Date Match** | Compare `item.published_at` to the page dateline. | Date matches `YYYY-MM-DD`. If `null`, dateline is genuinely absent from page. | Date mismatch, wrong year, or `null` when page has a clear date. | Sachi (`extract.py`) |
| 3 | **Label Accuracy** | Compare `item.label` against the rule in `parent.md` section 19. | `claim` for company self-statements; `fact` for neutral reporting or government releases. | Competitor press labeled `fact`, or neutral regulatory report labeled `claim`. | Sachi (`extract.py`) |
| 4 | **Company Attribution** | Verify `item.company` against the entity described. | Correct canonical corporate entity (e.g., "Sullair", "Quincy Compressor"). | Incorrect company, generic noun, or `null` when subject is obvious. | Sachi (`clean.py`) |
| 5 | **Technology Class** | Verify `item.technology` against equipment in text. | Valid taxonomy label from `config/technologies.yaml`, or `null` if unstated. | Incorrect technology assigned (e.g., labeling a screw unit as centrifugal). | Sachi (`extract.py`) |
| 6 | **Key Facts Veracity** | Verify each statement in `item.key_facts` (max 3). | Statement appears verbatim or near-verbatim on page, $\le 200$ chars, factually true. | Distorted claims, hallucinated specs, or boilerplate/cookie text included. | Sachi (`extract.py`) |
| 7 | **Zero PII** | Inspect title, key facts, and metadata for personal data. | No human names, email addresses, phone numbers, or personal credentials present. | Any personal name, direct email, or phone number persists. | Sachi (`extract.py`) |
| 8 | **Filter Justification** | Verify `item.filter` boolean decision and reasons. | Article is genuinely compressor-related, North American, credible, and recent. | Passed an irrelevant article, or dropped a valid compressor item. | Nikhil (`filter.py`) |

---

## 2. Run Details Under Audit

- **Environment Prefix:** `TODO(Nikhil: e.g. dev/nikhil or dev/parth)`
- **Run Identifier (`run_id`):** `TODO(Nikhil: e.g. 20261030T073000Z)`
- **Execution Timestamp:** `TODO(Nikhil: ISO timestamp)`
- **Auditor:** Parth
- **Audit Date:** `TODO(Parth: Date of verification)`

---

## 3. Empirical Verification Results Table

*Each row must be evaluated against the live `source_url`. Enter `yes`, `no`, or `n/a` (with reason).*

| # | Item ID | Source ID | Live Article URL | Title OK | Date OK | Label OK | Company OK | Tech OK | Facts OK | No PII | Filter OK | Notes & Root Cause | Fix Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 2 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 3 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 4 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 5 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 6 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 7 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 8 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 9 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |
| 10 | `TODO` | `TODO` | `TODO` | - | - | - | - | - | - | - | - | Awaiting run | - |

---

## 4. Audit Summary & Defect Routing Protocol

*To be populated upon completion of empirical checks:*
- **Total Items Fully Correct:** `TODO(Parth: X of 10)`
- **Total Minor Anomalies:** `TODO(Parth)`
- **Total Critical Failures:** `TODO(Parth)`

### Anomaly Escalation Protocol
When an evaluation cell is marked `no`, record the specific failure in the "Notes" column and immediately dispatch the defect to the responsible module owner:
- **Extraction & Cleaning Defects:** Route to **Sachi** (`atlas/extract.py`, `atlas/clean.py`, `config/aliases.yaml`, `config/technologies.yaml`).
- **Relevance Filter & Logic Defects:** Route to **Nikhil** (`atlas/filter.py`, `config/keywords.yaml`).
- **Crawler, Politeness & Blocking Defects:** Route to **Ragini** (`atlas/compliance.py`, `atlas/collect.py`, `config/sources.yaml`).

---

## 5. Global Storage Verification Checklist

These global assertions verify compliance with the client's non-negotiable architectural mandates:

| Verification Item | Required Standard | Status | Verified Evidence / Command |
|---|---|---|---|
| **1. Volume Directory Structure** | Six required folders exist under prefix: `source_register`, `raw`, `clean`, `facts`, `output`, `logs`. | `TODO(Nikhil)` | Managed & verified by Nikhil in Databricks Volume catalog. |
| **2. Zero Local Data Footprint** | Local repository working tree contains zero scraped data, cached HTML, or output JSON files. | `VERIFIED` | `git status` shows clean tree; no files outside `.gitignore`. |
| **3. Memory-Only Output** | Scraped HTML exists only in volatile memory during execution. | `VERIFIED` | Unit tests verify `FetchedPage.model_dump()` excludes `html`. |
| **4. Offline Test Integrity** | All unit tests pass completely offline with zero live network calls. | `VERIFIED` | `pytest -q` passes 127 tests in 14.28s. |

---

## 6. Task P6: Databricks Evidence & Screenshot Protocol (Owner: Nikhil)

As established in the project ownership matrix, Nikhil owns the Databricks workspace administration, run execution, and cloud-side evidence collection. Nikhil captures the Volume screenshots following the final demo run; Parth reviews the evidence to ensure compliance before including references in presentation collateral.

### Mandatory Screenshot Requirements (Captured by Nikhil)
1. **Catalog View:** Navigate to `Catalog` → `atlas_poc` → `default` → `data` in the Databricks UI.
2. **Folder Completeness:** Ensure the UI display clearly reveals all six subfolders:
   - `source_register/`
   - `raw/`
   - `clean/`
   - `facts/`
   - `output/`
   - `logs/`
3. **Payload Inspection:** Open `output/poc_<run_id>.json` in the Databricks file preview window to show valid JSON formatting.
4. **Security & Privacy Masking:**
   - Verify that browser address bar tokens or user session cookies are not visible.
   - Verify that no personal email address or credentials appear in the frame.
5. **Storage Location:** Save screenshots **strictly outside the Git repository** (e.g., `Desktop/atlas_poc_evidence/`). Do NOT commit image files into the repo.
