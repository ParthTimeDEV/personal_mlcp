# sachi2.md: Wider scope in extraction, and the PDF/PPTX report

**Person:** Sachi. Read `parent2.md` first, fully. This file is your task spec and the prompt kit for your AI.

## Using this file with your AI
Give your AI, in order: (1) all of `parent2.md`, (2) this file, (3) `atlas/models.py`, `atlas/extract.py`, `atlas/clean.py`, the config files, `atlas/storage.py`, (4) `tests/fixtures/sample_output.json` for the report part (Nikhil pushes it on D0), (5) the kickoff prompt below. Demand the output format from `parent2.md` section 12.

### Kickoff prompt (paste as-is)
> You are helping me extend an extraction engine and build a report generator for an industrial-compressor market scout. I have pasted the Phase 2 master brief, my task file, and the shared code. Part A: extend `atlas/extract.py` and the YAML configs with region, event type and product detection, using the exact signatures in `parent2.md` section 10. Part B: implement the `atlas/report/` package that builds a PPTX (python-pptx) and a PDF (reportlab) from an `OutputEnvelope`, with charts drawn in memory by matplotlib. Page text must only ever exist in memory; the report must contain only data from the envelope; nothing is written to local disk; files are uploaded through `atlas/storage.py`. Never guess a missing value: it stays `null`. Return each file in full under a heading with its repo path. Tests run offline with `pytest`, using synthetic data. List every assumption at the end. If a requirement is ambiguous, ask me instead of choosing.

## Your files
| File | What |
|---|---|
| `atlas/extract.py`, `atlas/clean.py` | extend (Part A) |
| `config/technologies.yaml`, `keywords.yaml`, `aliases.yaml`, `products.yaml` | extend; `products.yaml` is new |
| `atlas/report/__init__.py`, `build.py`, `charts.py`, `pptx_builder.py`, `pdf_builder.py` | new (Part B) |
| `tests/test_extract.py`, `test_clean.py`, `test_report.py` | tests |
| `docs/report_design.md` | one page describing slides and rules |

## Task S0: Setup
`parent.md` section 12 setup. `pip install python-pptx reportlab matplotlib`, then append `python-pptx`, `reportlab` and `matplotlib` (one line each) to `requirements.txt` and tell Nikhil. `storage_check` PASS with `ATLAS_PATH_PREFIX=dev/sachi`.

# Part A: Wider scope in extraction

## Task S1: Technology labels and keywords
Add to `config/technologies.yaml` (specific above general; first match wins): air treatment (dryers, filters: already partly there; add desiccant, refrigerated, membrane, coalescing filter, aftercooler), **blowers** (rotary lobe, centrifugal blower, turbo blower), **vacuum pumps** (rotary vane, dry screw vacuum, claw, liquid ring), **gas compressors** (natural gas, biogas, CO2, nitrogen booster), **hydrogen compression**. Add the corresponding terms to `config/keywords.yaml` under `compressor` (or a new key `adjacent` only if you tell Nikhil first, because `filter.py` reads three keys; the simplest agreed route is to add them to `compressor`). Add new companies seen in the new sources to `config/aliases.yaml` (append only). Add 5 to 8 Canadian place names (provinces, big cities) to `us_locations`? No: create a new list `ca_locations` and `mx_locations` in `keywords.yaml`; tell Nikhil, who reads them in `filter.py`. Keep keyword matching whole-word and case-insensitive.

## Task S2: Region (`detect_region`)
```python
def detect_region(source: Source, title: str | None, text: str) -> Region | None
```
Return `"US"`, `"CA"` or `"MX"` when the item itself is clearly about that region: the most frequent hit among the three location lists in title plus text (title counts double); a tie or no hit falls back to the source's region only if the source is a company or publisher based there and the text has no conflicting location; otherwise `None`. Never default to US. Abbreviations are case-sensitive (e.g. `ON`, `QC` only with a city or the word "Ontario"), like `_found_location` today. Fill `Item.region`; keep `mentions_us_location` as is.

## Task S3: Event type (`classify_event`)
```python
def classify_event(title: str | None, text_signals: str) -> EventType | None
```
Rule-based, no model. Look at the title first, then the first sentences. Suggested patterns (put them in a table at the top of `extract.py` or a new `config/events.yaml`, your choice, record it): `acquisition` (acquires, acquired, acquisition of, to acquire, merger, buys), `investment_expansion` (invests, investment, expands, expansion, opens, new facility, breaks ground, plant, hiring), `product_launch` (launches, introduces, unveils, new series, now available, released), `partnership` (partners with, partnership, agreement, collaboration, distributor, joint venture), `regulation_standard` (regulation, standard, rule, directive, compliance, ISO, ASME, EPA, DOE efficiency), `appointment` (appoints, names, joins as, promoted, welcomes), `award` (wins, awarded, named a winner, recognised, top workplace), `event` (webinar, conference, trade show, expo, summit, meeting). First matching category in this priority: acquisition, regulation_standard, partnership, investment_expansion, product_launch, appointment, award, event. No match: `other`, or `None` if there is no usable title. Fill `Item.event_type`.

## Task S4: Product (`detect_product`)
```python
def detect_product(title: str | None, text: str, company: str | None) -> str | None
```
Create `config/products.yaml`: product families by company (for example for companies in `aliases.yaml`: series names and model patterns you can verify on their own sites today; mark `verified: false` for any you could not). Detection order: (1) a known product or series name from `products.yaml` found in title or text; (2) a model code in the title next to the company or a compressor word, matching a conservative pattern (letters then digits, 2 to 12 characters, e.g. `OFE1550`, `ZR 160`, `QGD-25`), only if it also appears in the text at least once more; (3) otherwise `None`. **Never guess**: no product beats a wrong product. Fill `Item.product` (it was always `None` in Phase 1).

## Task S5: Wire it into `extract_item` and clean
`extract_item` computes region, event type and product while the text is in memory and does not keep it (the existing "no page text in the item" test must still pass). `clean.py` is unchanged except: when merging duplicate items, keep the one with more filled phase 2 fields (extend `_completeness` naturally: it already counts non-empty fields). Do not change the signatures.

## Tests for Part A (in `tests/test_extract.py`, synthetic HTML)
Region: US, Canada, Mexico, tie → None, no location → None, abbreviation rule. Event: one test per category plus priority order plus no match. Product: known series, model code seen twice, model code seen once → None, nothing → None, never invented. Technologies: each new label. No page text in the item. Existing tests stay green. Real-page check (in memory only, print metadata, never save pages) on 3 items from each of 3 sources: report what you see.

# Part B: The report

## Task S6: Report data model and rules
`build_report(envelope, fmt)` and `write_report(run_id, fmt)` as in `parent2.md` section 10. `write_report` reads `output/poc_<run_id>.json` with `storage.read_json`, validates it as `OutputEnvelope`, builds the bytes, uploads with `storage.write_bytes` to `reports/report_<run_id>.<fmt>`, returns the path. Content rules:
- Only items in the envelope; every item shown has its source link, date, label (fact or claim), and via-fallback marker if set. Discovered sources are marked "discovered, not yet approved".
- No numbers that are not computed from the envelope. Show the counts you compute (items, sources, stories, by company, technology, event type, region, label).
- Key facts are shown as stored (they are already short). No other article text.
- State clearly: "Prepared for Atlas Copco by Group 8, VIT Pune. Source list is proposed, pending approval."
- Personal data: none expected; the builder must refuse (raise) if an item field contains `@` followed by a domain or a phone-number pattern, as a last line of defence.
- Layout: neutral and readable; no Atlas Copco logo or branding. If Atlas Copco provides a template, adapt after (open question 5 in `parent2.md`).

## Task S7: Structure (about 10 slides or pages, same content in both formats)
1. **Title:** project, run date, run id.
2. **Executive summary:** 3 to 5 sentences generated from the counts only (templated text, filled with computed numbers), plus 3 headline items with links.
3. **Scope and method:** regions, technologies, event types, window, sources used; one line on the rules-based filter and on legal compliance.
4. **What we found:** the top 8 items ranked by a transparent rule (stories seen in more sources first, then most recent), each with company, event type, date, label, link.
5. **By company:** bar chart of items per company (top 10) with the list of event types.
6. **By technology and event type:** two charts.
7. **Seen in several sources:** stories with 2 or more distinct sources, with the sources named; fallback items marked.
8. **Sources and compliance:** table of sources with status; refused sources with reasons (never hide them); discovered sources flagged; switching shown ("coverage for X came from Y, Z").
9. **How to read this report:** fact vs claim; what "passed the filter" means; limits (rules, small sample).
10. **Appendix:** full item list in compact form with links (paginates in the PDF; split across slides in the PPTX, 12 rows per slide).

## Task S8: Builders
- `charts.py`: matplotlib figures rendered to PNG bytes in memory (`BytesIO`), consistent colours, readable at slide size, colour-blind-safe palette, no chart with fewer than 2 data points (show a sentence instead). Use the Agg backend.
- `pptx_builder.py`: python-pptx, 16:9, one layout; pictures from the chart bytes via `BytesIO`; text never overflows its box (wrap and truncate long titles with an ellipsis, link text kept full in the appendix); speaker notes on slides 2 to 8 saying where each number comes from.
- `pdf_builder.py`: reportlab platypus, A4, header and footer with page numbers, tables that split across pages, clickable links.
- `build.py`: shared computation (counts, rankings, stories) used by both builders so the two formats always agree; `build_report` dispatches.
- Empty or small envelopes must produce a valid report with an honest "no items passed the filter" message, not an error.

## Tests (`tests/test_report.py`, synthetic envelopes, no network, no disk)
Builds both formats from `tests/fixtures/sample_output.json`; the PPTX reopens with python-pptx and has the expected number of slides; the PDF starts with `%PDF` and reopens (use `pypdf` only if you add it, otherwise check bytes and page count markers); numbers in the text equal numbers computed from the envelope; a refused source and a fallback item appear; an empty envelope works; a PII-like string raises; no file is written outside memory (monkeypatch `open` or use `tmp_path` cwd and assert it stays empty); `write_report` uses `storage.write_bytes` (mocked).

## Task S9: Live check
Run `python -m atlas.run --max-items 5` under `dev/sachi`, then `write_report(run_id, "pptx")` and `"pdf"`. Open both from Databricks (download through the Volume UI) and read every slide: are the numbers right, are the links right, does text overflow, are refused sources visible. Record the result in `docs/report_design.md` ("what I checked"). Give Parth the function name for the frontend button.

## Acceptance criteria
- [ ] `pytest tests/test_extract.py tests/test_clean.py tests/test_report.py -q` passes offline.
- [ ] Real items show region, event type and (where stated) product; unknown stays `null`.
- [ ] PPTX and PDF open correctly and contain the same numbers and links.
- [ ] No report or data file is written to the laptop.
- [ ] The report states compliance findings and refused sources honestly.

## Do not
- Do not store page text; do not copy article paragraphs into the report.
- Do not guess a region, event type or product.
- Do not invent numbers or quotes in the report; templates fill only computed values.
- Do not use an AI model to write report text.
- Do not edit `models.py`, `filter.py` or `run.py`; ask Nikhil.
