# parent2.md: Master brief for Phase 2

**Group 8, VIT Pune. Phase 1 (the Friday PoC) is built and on `main`. This file is the single source of truth for Phase 2.**
Read `parent.md` (Phase 1 rules and contracts) first, then this file, then your own file: `nikhil2.md`, `ragini2.md`, `sachi2.md` or `parth2.md`. `wd2.md` is the one-page split. Where this file and `parent.md` differ, this file wins for Phase 2.

> Everyone uses a different AI assistant, so interfaces, file names, field names and output formats are fixed here. Section 12 says how to brief your AI and what to demand back.

## Contents

1. What Phase 2 adds
2. Rules (Phase 1 rules still apply, plus new ones)
3. Architecture after Phase 2
4. Shared contracts (already in the repo)
5. Feature 1: the Auto Scout Engine
6. Feature 2: wider scope
7. Feature 3: the frontend
8. Feature 4: the PDF and PPTX report
9. File ownership
10. Interfaces (exact signatures)
11. Storage layout
12. How to work with your AI
13. Git workflow
14. Testing standards
15. Timeline
16. Definition of done
17. Decisions made and open questions

---

## 1. What Phase 2 adds

| # | Feature | Owner(s) |
|---|---|---|
| 1 | **Auto Scout Engine.** The scout finds valid, legal, trustworthy sources by itself. If a source is refused, it switches to articles about the same company or product from other allowed sources | Ragini (discovery and vetting), Nikhil (switching, stories, integration) |
| 2 | **Wider scope.** More regions, more technologies, more kinds of news, more sources | Ragini (sources), Sachi (extraction) |
| 3 | **Frontend** where the scout engine settings and all filters can be adjusted | Parth |
| 4 | **PDF and PPTX report** generated from a run | Sachi |

Phase 1 stays working throughout: with default settings, `python -m atlas.run` must behave exactly as before.

## 2. Rules

Everything in `parent.md` section 2 still applies. Phase 2 adds:

1. **"No fallback modes" means no silent engineering workarounds. It does not forbid the source-switching feature.** Source-switching is a designed, visible, logged feature: every substituted item is labelled `via_fallback=true` with `fallback_for=<refused source>`, appears in its own row in the run summary, and is explained in the report. What stays forbidden: switching to local storage, a different cloud, a different library without a team decision, or hiding a failure.
2. **A block is still never bypassed.** The scout may not fetch a refused site through a mirror, cache, web archive, proxy, translation service or any other route. It may only collect *other* sites' own articles about the same company or product.
3. **Discovery never approves anything.** Found sources are `Candidate`s. Only Atlas Copco approves sources. Automatic rules decide whether a candidate is `usable` in a run; a team member can accept or reject it in the frontend; neither is an Atlas Copco approval. Every discovered source is marked `origin: discovered` everywhere (data, frontend, report).
4. **Discovery uses only legitimate methods:** a curated seed list, outbound links from sources we already vetted, feed autodiscovery on a candidate's own homepage, and (only if the team chooses one) an **official search API with a key**. **Never scrape a search engine's result pages**: their terms forbid it.
5. **A discovered source is usable only if terms are positively `ok`.** `unknown` terms mean "needs human review", not "go".
6. **The frontend never shows or stores the Databricks token.** It reads `.env` like every other module. Run it only on a laptop, not on a public server.
7. **Settings are config, not scraped data,** but they still live in Databricks (`settings/scout_settings.json`), not on disk, so every machine sees the same settings.
8. **Reports contain only what the data contains.** Every statement in a report traces to an item with a source link. No invented numbers, no text copied from articles beyond the stored key facts, no personal data.

## 3. Architecture after Phase 2

```
                       settings/scout_settings.json  (saved from the frontend; defaults in config/scout_settings.yaml)
                                         │
 ┌─────────────── SCOUT ENGINE (new) ────┴───────────────────────────────────────────────┐
 │ discover.py → vet.py → scout/candidates.json ──(usable + not rejected)──► extra sources │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
                                         │
 register (config/sources.yaml) + usable discovered sources
        │
        ▼
 Compliance Gate → Collector → Extractor → Cleaner → Filter ─► passed items
        │ refused / empty                                          │
        ▼                                                          ▼
 fallback.py: find the same company/product                  stories.py: group items about the
 in OTHER allowed sources (never the refused one)            same company/product/event
        │                                                          │
        └──────────────► items (via_fallback=true) ───────────────►┘
                                         ▼
                      output/poc_<run_id>.json  (OutputEnvelope: items, stories, settings_used)
                         │                                  │
                         ▼                                  ▼
               Frontend (Streamlit, app/)            Report (atlas/report/): PDF and PPTX
               browse, adjust settings, run,         reports/report_<run_id>.pdf|pptx
               accept/reject candidates, download
```

## 4. Shared contracts (already in the repo)

`atlas/models.py` now contains all Phase 2 models. **Import them; never redefine.** Phase 1 records stay valid because every new field has a default.

| Model | Purpose | Written by → read by |
|---|---|---|
| `ScoutSettings`, `WatchEntry` | Everything the frontend can adjust, and the watchlist | Parth (saves) → Nikhil's `run.py`, filter, fallback; Ragini's discovery |
| `Candidate` | A discovered source with its evidence and trust score | Ragini → Nikhil (`run.py`), Parth (review screen) |
| `CandidateDecision` | A team member's accept or reject | Parth → Nikhil (`run.py`) |
| `StoryCluster` | Items about the same company/product/event across sources | Nikhil → Parth, Sachi (report) |
| `Item` (new fields) | `region`, `event_type`, `story_id`, `via_fallback`, `fallback_for`, `watch_matches` (and `product`, which is no longer always null) | Sachi (region, event type, product), Nikhil (the rest) |
| `Source` (new fields) | `origin`, `trust_score` | Ragini |
| `SourceSummary.kind`, `.fallback_for` | `registered`, `discovered` or `fallback` | Nikhil |
| `OutputEnvelope` (new fields) | `stories`, `settings_used`, `candidates_considered` | Nikhil → Parth, Sachi |

`atlas/storage.py` gained `write_bytes`, `read_bytes`, `exists`, `read_json_or_none`, and three new folders (`settings`, `scout`, `reports`). `config/scout_settings.yaml` holds the defaults and the first watchlist. **Change a model only through Nikhil** and update this file's section 4 in the same commit.

Allowed values: `Region`: US, CA, MX. `EventType`: product_launch, acquisition, investment_expansion, partnership, regulation_standard, appointment, award, event, other.

## 5. Feature 1: the Auto Scout Engine

Two halves.

**1A. Discovery and automatic vetting (Ragini).** Finds candidate sources and checks, by the same procedure we did by hand in `docs/source_vetting.md`, whether each is legal and trustworthy.

- *Where candidates come from:* (a) `config/discovery_seeds.yaml`, a curated list of publisher, association and company domains that Ragini compiles and marks unverified; (b) outbound links from pages of sources already `working` (a few pages per source, politely); (c) feed autodiscovery (`<link rel="alternate" type="application/rss+xml">`) on a candidate's own homepage; (d) optional official search API behind `SEARCH_API_KEY` (decision in section 17; off by default).
- *Automatic vetting of one candidate:* fetch robots.txt, find the terms page, scan it for automation language and keep a short quote (max 200 characters), find a feed, confirm public and logged-out, fetch one listing, sample up to 10 items, count dated items and compressor-keyword matches. All through `ComplianceGate`.
- *Trust score (0 to 100), transparent and rule-based:* a points table in `ragini2.md`, one line of reasoning stored per point (`trust_reasons`). No model.
- *`usable` is true only if all of:* robots allow, terms `ok` (not unknown), public, a dated feed or list, trust score at or above `min_trust_score`.
- *Output:* `scout/candidates.json` in the Volume (a list of `Candidate`).

**1B. Switching, stories and integration (Nikhil).**

- *When switching triggers:* a source is refused by the gate, or collection returns zero pages or stops on HTTP 429/503, **and** `fallback_enabled` is on.
- *What it does:* for every `WatchEntry` linked to the refused source (matched by company name and aliases) with `follow_when_blocked`, it looks for articles about that company or product in the **other** allowed sources: first among items already collected this run, then by collecting up to `fallback_max_items_per_source` from allowed sources and keeping those that mention the watch entry. Items found this way carry `via_fallback=true`, `fallback_for`, `watch_matches`.
- *Never:* fetch the refused site, a copy of it, or a syndication of it that is itself forbidden.
- *Stories:* group items (from any source) about the same company, product and event within a date window; the result is `StoryCluster`s. A story seen in several independent sources is stronger evidence, which the report and frontend show.

## 6. Feature 2: wider scope

The scope was "industrial compressors, USA". Phase 2 widens it "a bit". Defaults (change in section 17 if the team decides otherwise):

| Dimension | Phase 1 | Phase 2 default |
|---|---|---|
| Region | US | **US + Canada**, English-language sources. Mexico only for English-language sources; Spanish is a stretch goal, not required |
| Technology | compressors | add **air treatment (dryers, filters), blowers, vacuum pumps, gas compressors (including hydrogen)** |
| News type | any | tag every item with an `event_type` (product launch, acquisition, expansion, partnership, regulation, appointment, award, event) |
| Sources | 5 proposed | the 5 registered sources **plus every source the scout finds and vets as `usable`** (used when `use_discovered_sources` is on); the register itself only grows when a human promotes a find |
| Products | `product` always null | extract a `product` (model or series name) when stated; never guess |

Work split: **Ragini** vets and adds the new sources. **Sachi** teaches the engine the new scope: region tagging, event types, product names, new technology labels and keywords. **Nikhil** makes the filter obey `ScoutSettings` (regions, technologies, event types, extra and excluded keywords, `require_industrial`).

## 7. Feature 3: the frontend

A **Streamlit** app in `app/` (default decision, see section 17). It talks to Databricks only through `atlas/storage.py` and to the pipeline only by starting `python -m atlas.run`. Screens:

1. **Dashboard:** the latest run (summary per source, refused sources and reasons, counts), and an item browser with filters (source, label, passed or failed, company, technology, event type, region, date range, story, via-fallback). An item detail view shows every field and why it passed or failed.
2. **Settings:** edit every `ScoutSettings` field with validation, a watchlist editor, "reset to defaults", "save" (writes `settings/scout_settings.json`), and a visible diff against the defaults.
3. **Sources:** the register with status, and the discovered candidates with trust score, evidence and reasons. Buttons to accept or reject (writes `scout/decisions.json`).
4. **Run:** start a run with chosen settings and prefix; show live progress; show the summary at the end.
5. **Report:** generate a PDF or PPTX for a run, preview the slide list, download.

## 8. Feature 4: the PDF and PPTX report

`atlas/report/` builds a PPTX (python-pptx) and a PDF (reportlab) from an `OutputEnvelope`. Charts are drawn with matplotlib into memory. Nothing is written to local disk: files are uploaded to `reports/` in the Volume and returned as bytes for download. Structure (about 10 slides or pages): title, executive summary, scope and method, what we found (top items), by company, by technology and event type, stories seen in several sources, sources and compliance (including refused sources), how to read fact vs claim, appendix with the full list and links. Layout and content rules are in `sachi2.md`.

## 9. File ownership

Every file has exactly one owner. Only the owner edits it. Shared append-only files: `docs/decisions.md` and `requirements.txt`.

```
parent2.md wd2.md nikhil2.md ragini2.md sachi2.md parth2.md   (this planning set)
atlas/models.py  atlas/settings.py  atlas/storage.py          Nikhil (done; change requests go to him)
config/scout_settings.yaml                                    Nikhil (seed exists); Parth may append watchlist entries only
atlas/scout/__init__.py                                       Nikhil
atlas/scout/discover.py   atlas/scout/vet.py                   Ragini
config/discovery_seeds.yaml                                   Ragini
config/sources.yaml  docs/source_vetting.md                   Ragini
atlas/scout/fallback.py  atlas/scout/stories.py               Nikhil
atlas/scout/settings_store.py                                 Nikhil  (load/save ScoutSettings, load candidates + decisions)
atlas/filter.py  atlas/run.py                                 Nikhil
atlas/extract.py  atlas/clean.py                              Sachi
config/technologies.yaml  config/keywords.yaml  config/aliases.yaml  config/products.yaml   Sachi
atlas/report/__init__.py  build.py  charts.py  pptx_builder.py  pdf_builder.py              Sachi
app/main.py  app/pages/*.py  app/lib/*.py                     Parth
tests/test_scout_discover.py  test_scout_vet.py               Ragini
tests/test_scout_fallback.py  test_scout_stories.py  test_filter.py  test_run.py  test_settings_store.py   Nikhil
tests/test_extract.py  test_clean.py  test_report.py          Sachi
tests/test_app_logic.py                                       Parth
tests/fixtures/                                               synthetic only, owned by whoever writes the test
docs/ (phase 2 docs)                                          see each person's file
```

## 10. Interfaces (exact signatures)

Implement **exactly these names and signatures**. Extra helpers are fine.

### Settings and scout state: `atlas/scout/settings_store.py` (Nikhil, written first)
```python
def default_settings(path: str = "config/scout_settings.yaml") -> ScoutSettings: ...
def load_settings() -> ScoutSettings:            # settings/scout_settings.json if present, else defaults
def save_settings(settings: ScoutSettings) -> None: ...
def load_candidates() -> list[Candidate]: ...    # scout/candidates.json, [] if none
def save_candidates(candidates: list[Candidate]) -> None: ...
def load_decisions() -> list[CandidateDecision]: ...
def save_decision(decision: CandidateDecision) -> None: ...   # replaces an earlier decision for the same candidate
def usable_sources(settings: ScoutSettings, candidates: list[Candidate],
                   decisions: list[CandidateDecision]) -> list[Source]: ...
    # candidates -> Source(origin="discovered", status="proposed", vetting_status="working"); only if
    # settings.use_discovered_sources, candidate.usable, trust_score >= settings.min_trust_score,
    # and not rejected by a decision.
```

### Discovery (Ragini)
```python
def discover_candidates(sources: list[Source], gate: ComplianceGate, settings: ScoutSettings,
                        seeds_path: str = "config/discovery_seeds.yaml",
                        known_domains: set[str] | None = None, max_new: int = 25) -> list[Candidate]: ...
def vet_candidate(candidate: Candidate, gate: ComplianceGate, settings: ScoutSettings) -> Candidate: ...
def trust_score(candidate: Candidate) -> tuple[int, list[str]]: ...    # (score, reasons), pure function
```

### Switching and stories (Nikhil)
```python
def plan_fallback(refused: list[Source], watchlist: list[WatchEntry]) -> list[WatchEntry]: ...
def collect_fallback(entries: list[WatchEntry], refused_by: dict[str, str], allowed: list[Source],
                     gate: ComplianceGate, settings: ScoutSettings, already: list[Item]) -> CollectResult: ...
def apply_fallback_labels(items: list[Item], entries: list[WatchEntry], refused_by: dict[str, str]) -> list[Item]: ...
def build_stories(items: list[Item], window_days: int = 10) -> tuple[list[Item], list[StoryCluster]]: ...
    # returns the items with story_id set, and the clusters
```
`refused_by` maps a watch entry name to the `source_id` it stands in for.

### Filter and run (Nikhil)
```python
def apply_filter(items: list[Item], sources_by_id: dict[str, Source], today: date | None = None,
                 recent_months: int = 12, keywords_path: str = "config/keywords.yaml",
                 settings: ScoutSettings | None = None) -> list[Item]: ...
# settings=None reproduces Phase 1 exactly. With settings, its fields override recent_months and add
# region, technology, event_type, extra/excluded keyword and require_industrial rules (new reason codes
# are listed in nikhil2.md).
def main(argv: list[str] | None = None) -> int: ...
# python -m atlas.run [--only ID] [--max-items N] [--use-default-settings] [--no-discovery] [--no-fallback]
```

### Extraction (Sachi)
```python
def extract_item(page: FetchedPage, source: Source) -> Item: ...   # unchanged signature; now also fills region, event_type, product
def classify_event(title: str | None, text_signals: str) -> EventType | None: ...   # pure, rule-based
def detect_product(title: str | None, text: str, company: str | None) -> str | None: ...
def detect_region(source: Source, title: str | None, text: str) -> Region | None: ...
```
`extract_item` must not keep the text: `classify_event`, `detect_product` and `detect_region` run inside it while the text is in memory.

### Report (Sachi)
```python
def build_report(envelope: OutputEnvelope, fmt: Literal["pptx", "pdf"]) -> bytes: ...
def write_report(run_id: str, fmt: Literal["pptx", "pdf"]) -> str: ...   # reads output/poc_<run_id>.json, uploads reports/report_<run_id>.<fmt>, returns the Volume path
```

### Frontend (Parth)
Pure logic lives in `app/lib/` (filtering items, diffing settings, building a settings object from form values, parsing a run's progress) so it can be unit-tested without a browser:
```python
def filter_items(items: list[dict], f: "ItemFilters") -> list[dict]: ...
def settings_diff(current: ScoutSettings, defaults: ScoutSettings) -> list[tuple[str, object, object]]: ...
def latest_run_id() -> str | None: ...
def start_run(args: list[str]) -> "subprocess.Popen": ...
```

**Error policy (all modules):** do not swallow exceptions silently. Record failures in the structures above (`Refusal`, `RunLog.errors`, `Candidate.notes`) and keep going for other sources. Never return fake or partial data to hide a failure.

## 11. Storage layout

Under `/Volumes/atlas_poc/default/data/<prefix>/`:

```
source_register/ raw/ clean/ facts/ output/ logs/      Phase 1, unchanged
settings/scout_settings.json                           saved ScoutSettings
settings/... (decisions are in scout/)                 
scout/candidates.json                                  list[Candidate]
scout/decisions.json                                   list[CandidateDecision]
reports/report_<run_id>.pdf   report_<run_id>.pptx     generated reports
```
`ATLAS_PATH_PREFIX=dev/<yourname>` for development, as before. Only the final demo run uses an empty prefix.

## 12. How to work with your AI

Give your AI, in this order: (1) all of `parent2.md`, (2) all of your own file, (3) `atlas/models.py` and `atlas/storage.py`, (4) any module you consume (listed in your file), (5) the kickoff prompt at the top of your file. Demand:

1. **Complete files only**, each under a heading with the exact repo path. No "rest unchanged", no `...`, no placeholders.
2. **Exact names and signatures** from section 10. Import models from `atlas.models`; never redefine one.
3. **No local data.** No code writes data files to disk; persistence goes through `atlas/storage.py`.
4. **Offline tests** with `pytest` (mock HTTP with `httpx.MockTransport`, mock `atlas.storage`), covering a happy path, a "missing data stays null" case and a failure path.
5. **Runnable commands** and the expected output after the code.
6. **Python 3.11+, type hints, short docstrings.** A new package must be named, justified, and appended to `requirements.txt`.
7. **Assumptions listed** at the end. If a requirement is ambiguous or breaks section 2, the AI must ask, not choose.

After the answer: save files at the exact paths, run the commands, paste real failures back to the AI and ask for the root-cause fix (never "make the error go away"), run `pytest -q`, then commit.

Quick checks without reading the code: does the path match section 9? Do the signatures match section 10? Does it import models instead of defining them? Does anything write a data file to disk? Does it contain a hidden fallback, a way around a block, or a search-engine page scrape? Reject if so.

## 13. Git workflow

As `parent.md` section 13: commit to `main`, only your own files, `git pull --rebase origin main` before `git push origin main`, never force, message format `[name] what changed`, never commit `.env`, data, tokens or generated reports. New dependencies: append one line to `requirements.txt` and tell Nikhil.

## 14. Testing standards

As `parent.md` section 16, plus: every Phase 2 module must have a test proving that **default settings give Phase 1 behaviour**, and a test proving that **a refused source is never contacted again or bypassed**. Report and frontend tests use synthetic data only.

## 15. Timeline

The demo or hand-in date for Phase 2 is **not yet set**; Section 17 asks for it. Until then work in these relative stages (D0 = the day this brief is pushed):

| Stage | Deliverable |
|---|---|
| D0 | Everyone: pull, `pip install -r requirements.txt`, `storage_check` PASS under own prefix. Nikhil pushes `settings_store.py` and the sample output file |
| D0 to D1 | Each person pushes a first working version of their main module against synthetic inputs |
| D2 | Integration: discovery output reaches `run.py`; the frontend reads a real `output/` file; the report builds from a real run |
| D3 | Full run with discovery and fallback on; frontend settings change the result; reports generated |
| D4 | Fixes, hand-check of 10 items and of 3 fallback items, docs updated, final demo run with an empty prefix |

## 16. Definition of done

- [ ] Default settings reproduce Phase 1 output (same items for the same pages).
- [ ] A candidate can be discovered, vetted automatically, shown in the frontend with its evidence, accepted, and then used in a run.
- [ ] A refused source triggers visible switching: items with `via_fallback=true` appear in the output, the summary and the report, and the refused site is never contacted again.
- [ ] Settings changed in the frontend change the result of the next run.
- [ ] Scope: Canada sources, the new technologies and event types appear in a real run.
- [ ] A PDF and a PPTX are generated from a real run and open correctly.
- [ ] `pytest -q` passes for the whole repo; no data or report files on any laptop.
- [ ] 10 items and 3 fallback items hand-checked against their live pages.
- [ ] `docs/decisions.md` records every Phase 2 decision.

## 17. Decisions made and open questions

### Decided (defaults; change by team vote and record in `docs/decisions.md`)
| Topic | Decision |
|---|---|
| Frontend | Streamlit, in `app/` |
| PDF and PPTX libraries | python-pptx and reportlab, charts by matplotlib in memory |
| Discovery without a paid key | seed list, outbound links, feed autodiscovery. Search API optional |
| Terms `unknown` for a discovered source | not usable automatically |
| Scope | US + Canada, new technologies, event types, registered sources plus scout-found ones (section 6) |
| Switching | by watchlist (company or product), only through other allowed sources |

### Open (need an answer)
| # | Question | Who | Default if no answer |
|---|---|---|---|
| 1 | Phase 2 demo or hand-in date | team | D4 as in section 15 |
| 2 | Use an official search API for discovery? Which one, and who holds the key? | team | No. Seeds, links and feeds only |
| 3 | Mexico: English sources only, or add Spanish? | team | English only |
| 4 | Which extra technologies are in scope (air treatment, blowers, vacuum, gas, hydrogen)? | team, Atlas Copco | all five |
| 5 | Report template from Atlas Copco? | ask Atlas Copco | our own neutral layout |
| 6 | Has Atlas Copco approved the Phase 1 source list yet? | ask Atlas Copco | all stay `proposed` |

## Glossary additions
**Candidate:** a source the scout found but nobody has approved. **Trust score:** 0 to 100 points from transparent rules about a candidate. **Watchlist:** companies, products or technologies the scout keeps following. **Fallback / switching:** collecting articles about a watched company or product from other allowed sources when its own source is refused. **Story:** items from different sources about the same company, product and event. **Via fallback:** an item collected because of switching, labelled as such.

## Reporting format

After each piece of work, post this (as `parent.md` section 20):
```
WHO / WHEN
DONE: <files pushed, commit hash>
WORKS (I ran it): <command> -> <result>
FAILED / NOT WORKING: <exact error or "none">
ASSUMPTIONS / DECISIONS NEEDED
NEXT
NEED FROM OTHERS
```
Do not write "works" unless you ran it and saw the result.

---

## 20. Progress reports

Each person adds their report below, newest at the bottom, in the format above.

### Sachi, 15 Nov 2026
WHO / WHEN
Sachi, 15 Nov 2026

DONE: pushed to main

24cb246: Part A + Part B
· Part A, extraction (atlas/extract.py, atlas/clean.py, config/technologies.yaml, keywords.yaml, aliases.yaml, new config/products.yaml): region (US/CA/MX), event type and product detection, plus the new technologies, keywords, aliases and products
· Part B, report package (atlas/report/: build.py, charts.py, pptx_builder.py, pdf_builder.py)
· tests (test_extract, test_clean, test_report + fixture) and docs (docs/report_design.md, docs/decisions.md)
43bc704: fixes from the live check
· places outside North America now give region null instead of US
· a switching row is no longer counted as a source
· “other” is not reported as the most common type of news
· a switch that found nothing is now stated in the report

WORKS (I ran it):

.venv/bin/python -m pytest -q -> 339 passed
python -m atlas.storage_check (prefix dev/sachi) -> PASS
python -m atlas.run --max-items 5 -> run 20261115T045141Z: 13 items from 3 of 11 sources, 6 refused, Ingersoll Rand switching tried with 0 items, 0 multi-source stories
write_report(‘20261115T045141Z’, ‘pptx’ / ‘pdf’) -> /Volumes/atlas_poc/default/data/dev/sachi/reports/report_20261115T045141Z.pptx and .pdf
Read both reports in the Volume UI: numbers match the run, links open the right articles, no text overflow, new wording shows
Hand-checked 7 items against their live pages:
· event types right (acquisition, product launch, award x2, event, other)
· product OFE1550 right; Fluke item correctly has no product (the article names two models)
· Best Practices 2026 EXPO: company Kaeser, technology blower, both right

FAILED / NOT WORKING:

In this run, 2 items are still tagged US although they are about Portugal and the Netherlands. The fix applies only to new runs; the stored items were not changed.
0 fallback items in this run, so no fallback item could be hand-checked yet.

ASSUMPTIONS / DECISIONS NEEDED:

Region stays null when an article names places outside North America at least as often as US/CA/MX places. It never defaults to US.
Report layout is our own neutral design. No Atlas Copco template has been received yet (open question 5).

NEXT:

Rebuild the reports from the D3 full run (discovery + fallback on) and hand-check 3 fallback items once a run produces them.
Hand-check 3 more items so the total reaches 10.

NEED FROM OTHERS:

Nikhil: the default regions [“US”] drops US-source articles about Canada and Mexico. Should the default be US, CA and MX? Also, story grouping joined two unrelated Sullair “other” articles into one story.
Parth: the frontend report button calls atlas.report.write_report(run_id, “pptx” or “pdf”). It returns the Volume path.
Ragini: new companies were added to config/aliases.yaml. Please pull before editing it.
