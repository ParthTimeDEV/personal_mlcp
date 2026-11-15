# wd2.md: Phase 2 work distribution (one page)

Read `parent2.md` first (the full brief), then your own file. Phase 1 is done and on `main`.

**New tasks:** (1) Auto Scout Engine, (2) wider scope, (3) frontend with adjustable scout and filter settings, (4) PDF/PPTX report.
**Already done by Nikhil, so nobody waits:** all Phase 2 data models in `atlas/models.py`, new storage helpers, default settings and watchlist in `config/scout_settings.yaml`.

## Who does what

| Person | Task area | Owns | Main deliverable |
|---|---|---|---|
| **Nikhil** | Scout engine: switching and stories. Filter obeys settings. Integration | `atlas/scout/fallback.py`, `stories.py`, `settings_store.py`, `atlas/filter.py`, `atlas/run.py`, `models.py`, `storage.py`, their tests | When a source is refused, the run finds coverage from other allowed sources and labels it; items are grouped into stories; every setting changes the result; one command runs it all |
| **Ragini** | Scout engine: discovery and automatic vetting. Hand-check of the scout's finds (optional) | `atlas/scout/discover.py`, `vet.py`, `config/discovery_seeds.yaml`, `config/sources.yaml`, `docs/source_vetting.md`, their tests | The scout finds candidate sources, vets them legally, scores their trust; 5 to 7 new vetted sources (Canada and new technologies) |
| **Sachi** | Wider scope in extraction. PDF/PPTX report | `atlas/extract.py`, `clean.py`, `atlas/report/*`, configs for technologies, keywords, aliases, products, their tests | Region, event type and product on every item; new technology labels; a PDF and a PPTX report built from a run |
| **Parth** | Frontend | `app/*`, `tests/test_app_logic.py`, frontend docs | A Streamlit app: dashboard and item browser, settings editor, candidate review, run launcher, report download |

## How the work connects (nobody waits idle)

```
Ragini: discovery  ──► Candidate list ───────────────┐
Nikhil: settings_store (D0) ──► ScoutSettings ───────┼──► run.py (Nikhil) ──► output JSON ──► Frontend (Parth)
Sachi: region / event / product on items ────────────┘                              └────────► Report (Sachi)
```
Each person builds against the models already in `atlas/models.py` and against synthetic inputs, so the first version of every module can be written and tested on day one.

## Load check (roughly equal)

| Person | Main module(s) | Rough size |
|---|---|---|
| Nikhil | fallback, stories, settings store, filter changes, run integration | 5 modules, heavy on integration and tests |
| Ragini | discovery, automatic vetting, trust score, hand-check of 3 scout finds | 3 modules plus real-world vetting |
| Sachi | event, product and region extraction, new configs, 2 report builders, charts | 5 modules plus design work |
| Parth | 5 frontend screens, helper library, run launcher | 1 app, 5 screens, UI logic tests |

## Stages (D0 = the day this is pushed; the real date is an open question in `parent2.md`)

| Stage | Nikhil | Ragini | Sachi | Parth |
|---|---|---|---|---|
| D0 | `settings_store.py`, sample output file | setup, seed list started | setup, product list started | setup, app skeleton |
| D0 to D1 | `filter.py` with settings, `fallback.py` | `vet.py` and `trust_score` | event type, region, product | Dashboard and item browser on the sample file |
| D1 to D2 | `stories.py`, `run.py` wiring | `discover.py`, first new sources | new technology labels, report skeleton | Settings screen |
| D2 | integration with discovery | candidates to Nikhil | real-run extraction check | Sources and Run screens |
| D3 | full run, fix list | vet remaining sources | PDF and PPTX from a real run | Report screen, polish |
| D4 | final demo run, push, tag | present sources and discovery | present scope and report | present frontend, hand-check items |

## Shared rules (short version)

- No data on laptops. Use your own prefix `ATLAS_PATH_PREFIX=dev/<yourname>`.
- Public pages, robots.txt and terms obeyed; **a block is never bypassed**, including through mirrors or archives.
- Switching is a visible, labelled feature, never a hidden fallback.
- Discovery never approves a source; terms must be positively `ok`.
- Unknown values stay `null`. No invented numbers in the report.
- Everyone generates their own token and never pastes it anywhere.
- Commit to `main`, only your own files, `git pull --rebase origin main` before `git push origin main`.
- Report with the format at the end of `parent2.md`. Do not say "works" until you ran it.
