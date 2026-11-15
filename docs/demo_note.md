# Demo Note: Atlas Copco Market & Technology PoC

**Project:** Market & Technology Study — Industrial Compressor Scout  
**Team:** Group 8, VIT Pune  
**Demonstration Date:** Friday 30 October 2026  
**Audience:** Atlas Copco Stakeholders (Compressor Technique Division)  

> *Note:* Values marked `TODO(owner)` are reserved for empirical telemetry from the final integration and demo runs. No numbers or dates are estimated or fabricated.

---

## 1. What We Built

We built an automated market intelligence scout that continuously tracks public US sources for technological innovations and business moves in industrial compressor technology. The pipeline extracts verified facts, strips personal identifiable information, applies a four-part relevance filter, and writes structured JSON directly to cloud storage. In accordance with client specifications, no scraped data or raw text is ever stored on local machines.

---

## 2. How the Pipeline Works

The system follows a transparent three-stage workflow: **Input → Engine → Output**.

```
  [INPUT] Sources & Compliance ──► [ENGINE] Extraction & Cleaning ──► [OUTPUT] Relevance & Cloud Storage
   - config/sources.yaml            - trafilatura text extraction      - 4-rule relevance filter
   - robots.txt & terms audit       - Presidio PII scrub (spaCy)       - Databricks Volume write
   - Polite delay (>= 3.0s)         - Body text dropped (fingerprint)  - Zero local disk footprint
   - Memory-only FetchedPage        - Deduplication & RapidFuzz alias  - poc_<run_id>.json envelope
```

- **Zero Local Storage:** Scraped HTML and parsed text exist exclusively in volatile memory; all persistence uses the Databricks Files API into a managed cloud Volume.
- **Deterministic Rules (No AI for Friday PoC):** All extraction, entity normalization, and filtering logic rely on deterministic Python algorithms and standard NLP libraries. LLM summarization is reserved for Phase 2.

---

## 3. The 5 Proposed Sources (and Why)

We propose five initial US sources providing a balanced mix of industry trade press, competitor announcements, and government monitoring:

| Source Name | Source Type | Access Method | `robots.txt` Status | Terms of Use Status | Technical Rationale |
|---|---|---|---|---|---|
| **Compressed Air Best Practices** | Trade News | RSS Feed (`/rss.xml`) | Allowed | OK (No automation ban) | Premier US trade publication dedicated 100% to compressed air systems. High yield of relevant articles. |
| **Quincy Compressor** | Competitor | RSS Feed (`/blog/feed`) | Allowed | OK (No automation ban) | Established US manufacturer (Bay Minette, AL) providing dated technical and application posts. |
| **Sullair US News** | Competitor | HTML Listing (`/en/news`) | Allowed | OK (No automation ban) | Major US industrial compressor OEM (Hitachi Global Air Power) with frequent product and facility announcements. |
| **Pumps & Systems** | Trade News | RSS Feed | Allowed | OK (No automation ban) | Leading rotating equipment publication; covers adjacent fluid power, acquisitions, and plant installations. |
| **US Department of Energy** | Government | HTML Listing (`/newsroom`) | Allowed | OK (Federal public domain) | Authoritative public source for industrial energy efficiency standards, grants, and industrial decarbonization news. |

*Governance Note:* These five sources represent our proposed working register. Formal client sign-off is required, and Atlas Copco’s Legal team should review the list before full production deployment.

---

## 4. Sources Vetted and Blocked or Excluded

Our compliance audit inspected 15 candidate sources. Six sources were excluded due to strict legal compliance and zero-workaround rules:

| Candidate Source | Category | Finding | Verified Reason for Exclusion |
|---|---|---|---|
| **CAGI (Compressed Air & Gas Institute)** | Trade Body | **Blocked** | Terms of Use explicitly forbid *"data mining, robots, or similar automated data gathering and extraction tools"*. |
| **PR Newswire** | Press Wire | **Blocked** | Terms of Use strictly forbid scraping and any automated spider/crawler access. |
| **Plant Services** | Trade News | **Blocked** | Endeavor Business Media terms forbid robots and automated harvesting despite feed availability. |
| **Ingersoll Rand Newsroom** | Competitor | **Unreachable** | Responded with HTTP 429 (Too Many Requests) on initial request. We do not use proxies or circumvent rate limits. |
| **Plant Engineering** | Trade News | **Unreachable** | Responded with HTTP 403 (Forbidden) to our identified student user-agent. |
| **Business Wire Releases** | Press Wire | **Unreachable** | Disallow-all in robots.txt and HTTP 403 on root endpoint. |

*Reserve Sources (Vetted, held in reserve):*
- **Atlas Copco USA / Group:** Usable, but excluded from the active scout to avoid reporting the client's own announcements back to itself.
- **Kaeser Compressors USA Blog:** Usable, but blog posts omit publication datelines in their HTML, causing them to fail the 12-month recency filter (`date_missing`).
- **ELGi US:** Feed carries static product marketing brochures rather than timestamped market news.

---

## 5. The Four Relevance Filters & Run Telemetry

Every collected item must pass four transparent yes/no checks. Items failing any check are excluded from `facts/` and the final output JSON, but are retained in `clean/` with their exact failure reason codes:

1. `compressor_related`: Article contains matched compressor keywords or title mentions compressor technology (`no_compressor_keyword`).
2. `north_america`: Source region is US/CA/MX/NA or article text explicitly references US locations (`not_north_america`).
3. `credible_source`: Source exists in register, is vetted as `working`, and is marked `proposed` or `approved` (`source_not_credible`).
4. `recent`: Published within the rolling 12-month window. Missing dates or future dates fail (`too_old`, `date_missing`, `date_in_future`).

### Final Run Execution Summary
*Telemetry to be recorded from final demo run `TODO(Nikhil: run_id)` at `TODO(Nikhil: timestamp)`:*

| Source Name | Items Collected | Duplicates Dropped | Passed Filter | Dropped by Filter | Primary Reasons for Drop |
|---|---|---|---|---|---|
| **Compressed Air Best Practices** | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil: e.g. too_old)` |
| **Quincy Compressor** | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` |
| **Sullair US News** | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` |
| **Pumps & Systems** | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil: e.g. no_compressor_keyword)` |
| **US Department of Energy** | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil)` | `TODO(Nikhil: e.g. no_compressor_keyword)` |

*Sample Real Exclusions from `clean/`:*
- `TODO(Parth: Real Item Title 1)` (`Source Name`) — Dropped due to: `TODO(Parth: reason code)`.
- `TODO(Parth: Real Item Title 2)` (`Source Name`) — Dropped due to: `TODO(Parth: reason code)`.

---

## 6. What We Checked by Hand (Quality Audit)

To guarantee that the pipeline does not invent facts or leak personal data, we conduct an empirical 10-item audit on live records from `output/poc_<run_id>.json`:
- **Audit Methodology:** 10 records across $\ge 3$ sources are verified against live web URLs across 8 criteria: headline accuracy, publication dateline validity, company attribution, technology classification, factual veracity of key facts ($\le 200$ chars), PII scrubbing completeness, fact/claim classification, and filter justification.
- **Audit Findings:**  
  `TODO(Parth: Upon completion of docs/check_results.md, summarize: "X of 10 items fully verified against live web pages. Main anomalies noted: ...")`

---

## 7. Open Strategic Questions for Atlas Copco

Full questionnaire available in `docs/questions_for_atlas_copco.md`. Key decision points for Friday:
1. **Source Register Approval:** Does Atlas Copco sign off on the 5 proposed sources?
2. **Access to Blocked Sites:** Does Atlas Copco hold corporate subscriptions or syndication feeds for major blocked competitors (e.g., Ingersoll Rand)?
3. **Workspace Provisioning:** Can Atlas Copco provision a dedicated Azure / Databricks workspace to host production data within the client perimeter?
4. **Filter Tuning:** Should the `"industrial"` keyword remain an informational metadata hint, or become a mandatory filter gate?

---

## 8. What Comes Next (Roadmap Beyond PoC)

- **Phase 2 (Reporting & AI Summary):** Automated executive PDF/PowerPoint report generation; LLM-based trend synthesis (self-hosted or private cloud).
- **Phase 3 (Operational Automation):** Automated weekly cron scheduling, webhook alerts for high-priority competitor moves.
- **Phase 4 (Geographic & Source Expansion):** Extension to Canadian and Mexican sources; patent application scraping (USPTO) and academic literature tracking.
