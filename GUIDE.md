# Atlas Copco Market & Technology PoC: the complete guide

Group 8, VIT Pune (Nikhil, Ragini, Sachi, Parth). This is the one document that explains everything: what the
project is, what we built in Phase 1 and Phase 2, how every part works, how to run it, what the results are, what
is not finished, and how to fix common problems. Read it top to bottom once; use the contents to jump back.

**Contents**
1. [What the project is](#1-what-the-project-is)
2. [The result in numbers](#2-the-result-in-numbers)
3. [How a run works, step by step](#3-how-a-run-works-step-by-step)
4. [What we built, by phase](#4-what-we-built-by-phase)
5. [How to set it up](#5-how-to-set-it-up)
6. [How to run everything](#6-how-to-run-everything)
7. [The frontend, screen by screen](#7-the-frontend-screen-by-screen)
8. [The reports (one page and full)](#8-the-reports-one-page-and-full)
9. [The filter: every rule and reason code](#9-the-filter-every-rule-and-reason-code)
10. [The scout engine: discovery, trust score, switching](#10-the-scout-engine-discovery-trust-score-switching)
11. [Sources: what we use and what we refused](#11-sources-what-we-use-and-what-we-refused)
12. [Where everything is stored](#12-where-everything-is-stored)
13. [Legal and safety rules](#13-legal-and-safety-rules)
14. [Who did what](#14-who-did-what)
15. [The problems we found and fixed](#15-the-problems-we-found-and-fixed)
16. [What is not finished, and what we need from Atlas Copco](#16-what-is-not-finished-and-what-we-need-from-atlas-copco)
17. [Troubleshooting](#17-troubleshooting)
18. [A 10-minute demo script](#18-a-10-minute-demo-script)
19. [File map](#19-file-map)

---

## 1. What the project is

Atlas Copco wants to know what is happening in the industrial compressor market: new products, acquisitions, new
plants, regulations, competitors' moves. Our program does this automatically:

1. It reads **public** news pages of a short list of sources, politely and legally.
2. It pulls out only **facts**: date, company, product, technology, event type, region, and 1 to 3 short key
   facts. It never stores article text.
3. It keeps only items that are about compressors, in North America, from a credible source, and recent.
4. It saves everything as JSON files in a **Databricks Volume**. Nothing is stored on any laptop.
5. It can produce a **one-page summary** and a **full report** as PowerPoint or PDF, and a **web app** to look at the
   results and change the settings.

It is plain Python and rules. **No AI model** is used to read, judge or write anything. Everything is explainable:
every dropped item has a reason code.

**Phase 1** was the pipeline (collect, clean, filter, save). **Phase 2** added four things you asked for:
an **auto scout engine** (finds and checks new sources by itself and switches to other sources when one refuses us),
a **wider scope** (Canada, more technologies, event types, products), a **frontend**, and **PPT/PDF reports**.

---

## 2. The result in numbers

Final demo run `20261115T204628Z` (in the real demo folders of the Volume, empty prefix):

| What | Number |
|---|---|
| Sources read | 7 (5 from the first list plus FS-Elliott and Burckhardt Compression, both hand-checked) |
| Sources refused or blocked, shown honestly | 7 |
| Items that passed the filter | 47 |
| Items about Atlas Copco itself | 2 |
| Items about other companies | 45 |
| Stories (same event in several items) | 46, of which 1 is seen in 2 or more sources |
| Errors | 0 |
| Local data files created | 0 |
| Automated tests | 442, all passing offline |

In the same run the scout engine looked at **67 candidate sites** (found from a seed list and from links on our own
sources) and vetted them automatically. Only a few passed every legal rule, which is the point: the scout does not
loosen the rules to look productive.

Switching for Ingersoll Rand (refused today) was **tried correctly and found nothing** in the pages read, so the demo
run shows 0 switched items. The mechanism was proven live separately (see section 10).

---

## 3. How a run works, step by step

One command, `python -m atlas.run`, does all of this.

```
 settings --> register + discovered sources --> for each source:
   1 Compliance Gate  2 Collect  3 Extract  4 Clean  5 Filter  6 Save
 --> switching for refused sources --> stories --> output + log
```

**0. Settings.** The run loads the saved settings (or the defaults). They control regions, how many months back,
words to include or exclude, which source types, whether discovery and switching are on, and the watchlist.

**0b. Discovery (only if on).** The scout finds new candidate sites, vets them, saves them. Sites that pass every
rule can be used as extra sources in the same run (section 10).

**1. Compliance Gate.** Before any page is touched: is the source allowed? It must not be blocked, must be vetted
as working, its terms must not forbid automation, and its `robots.txt` must allow the listing. A refusal is
recorded with a reason and the source is **never** contacted again in that run.

**2. Collect.** The list of articles comes from the RSS feed (preferred) or from a list page. Each article is
fetched with 3 seconds between requests, with our identified User-Agent. A 429 or 503 answer stops that source.
Pages are held **in memory only**.

**3. Extract.** From each page: title, publish date (never guessed; unknown stays empty), company, product,
technology, event type, region, 1 to 3 short key facts, a fact-or-claim label, and signals the filter needs. Personal
data is removed. The page text is then thrown away.

**4. Clean.** Duplicates are removed (same URL or same content), dates are made ISO format, and company-name
variants are merged ("Ingersoll-Rand" and "Ingersoll Rand Inc." become one).

**5. Filter.** The four checks plus any extra rules from the settings (section 9). Nothing is deleted here; every item
gets a pass/fail and the list of reasons. Only passed items go into the final output file, but the failed ones are
kept in `clean/` so you can see why.

**6. Save.** Metadata of what was collected goes to `raw/`, all cleaned items to `clean/`, passed items to
`facts/`.

**7. Switching.** If a source was refused, returned nothing, or hit a rate limit, and a watch entry follows that
company, the run looks for the same company in the other allowed sources and labels what it finds
(`via_fallback`). It never reaches the refused site by any route (section 10).

**8. Stories.** Items about the same company and the same product or event, within 10 days, are grouped into a
story, even if they came from different sources.

**9. Output.** `output/poc_<run_id>.json` (the results), `logs/<run_id>.json` (what ran, what was refused and why),
and a printed summary. The run ends with a check that no data file was created on the laptop.

Exit code 0 means everything worked. Blocked sources are findings, not errors.

---

## 4. What we built, by phase

### Phase 1: the pipeline
- Storage on Databricks (`atlas/storage.py`) and a check that proves it works (`atlas/storage_check.py`).
- Source vetting by hand: 15 candidates checked against robots.txt, terms, feed and public access
  (`docs/source_vetting.md`), leaving 5 working sources and 6 refused ones.
- Compliance Gate and collector (`atlas/compliance.py`, `atlas/collect.py`).
- Extractor with personal-data removal, cleaner, filter (`atlas/extract.py`, `atlas/clean.py`, `atlas/filter.py`).
- The run command with live progress (`atlas/run.py`).
- Docs: `parent.md`, `wd.md`, one brief per person, `prepare.md` (presentation prep with a pipeline picture).

### Phase 2: the four new tasks
| Task | What was built | Main files |
|---|---|---|
| Auto scout engine | Discovery of candidate sources, automatic legal vetting, trust score 0 to 100, switching to other sources when one refuses us, stories | `atlas/scout/discover.py`, `vet.py`, `fallback.py`, `stories.py`, `settings_store.py` |
| Wider scope | Region (US, Canada, Mexico), event type, product detection, new technologies (air treatment, blowers, vacuum, gas and hydrogen compression), new keywords and company aliases | `atlas/extract.py`, `config/*.yaml` |
| Frontend | A Streamlit app with five screens | `app/` |
| PPT/PDF report | A one-page summary and a full 10-slide report | `atlas/report/` |

---

## 5. How to set it up

You need Python 3.12, a Databricks workspace with a Volume, and a personal access token.

```
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
copy .env.example .env            # macOS/Linux: cp .env.example .env
```

Fill `.env`:

| Key | Meaning |
|---|---|
| `DATABRICKS_HOST` | your workspace URL |
| `DATABRICKS_TOKEN` | **your own** personal access token. Never paste it in chat, never commit it. `.env` is git-ignored |
| `DATABRICKS_CATALOG`, `DATABRICKS_SCHEMA`, `DATABRICKS_VOLUME` | `atlas_poc`, `default`, `data` (the Volume root is `/Volumes/atlas_poc/default/data`) |
| `CONTACT_EMAIL` | the address placed in our User-Agent so websites can contact us: `industrymlcp@gmail.com` |
| `ATLAS_PATH_PREFIX` | your own sandbox folder inside the Volume, for example `dev/nikhil`. **Leave it empty only for the final demo run**, because empty means the real demo folders |

Then check the connection:

```
python -m atlas.storage_check      # must print PASS
```

**Important on Windows:** always use the project's Python. Anaconda's Python on your PATH does not have the project's
packages. Write `.venv\Scripts\python.exe ...` or activate the venv first.

---

## 6. How to run everything

### Run the pipeline
```
python -m atlas.run                          # all sources, saved settings
python -m atlas.run --only fs_elliott_news   # one source
python -m atlas.run --max-items 5            # fewer pages per source (quick test)
python -m atlas.run --use-default-settings   # ignore saved settings, use config/scout_settings.yaml
python -m atlas.run --no-discovery           # skip the scout's discovery this run
python -m atlas.run --no-fallback            # do not switch to other sources
```
It prints progress as it goes (a full run takes 20 to 25 minutes because of the 3-second politeness delay) and ends
with a summary and `run_id: ...`. Use your own `ATLAS_PATH_PREFIX` while testing.

### Start the web app
```
.venv\Scripts\python.exe -m streamlit run app/main.py
```
Open `http://localhost:8501`. If that port is already in use, add `--server.port 8599`. The app only reads and
writes the Volume through our code and starts runs by launching `python -m atlas.run`; it never contacts a website.

### Build the reports from the command line
```python
from atlas.report.onepager import write_onepager
from atlas.report.build import write_report
write_onepager("20261115T204628Z", "pptx")   # one page; also "pdf"
write_report("20261115T204628Z", "pdf")      # full report; also "pptx"
```
Files go straight to `reports/` in the Volume. The Report screen of the app does the same with buttons.

### Search a finished run in the terminal
```
python demo_search.py hydrogen
python demo_search.py compressor --event acquisition --source fs-elliott
```

### Run the tests (offline, nothing touches Databricks)
```
pytest -q            # 442 tests
```

### Where do I see the results?
In Databricks: Catalog, `atlas_poc`, `default`, `data`, then `output/` (the results), `reports/` (PPTX, PDF),
`logs/` (what happened), `clean/` (every item including the dropped ones with reasons). Or in the app.

---

## 7. The frontend, screen by screen

Start it as in section 6. Use the sidebar to pick a run and see which data folder (prefix) you are looking at. A
warning appears when the prefix is empty, meaning "you are looking at the real demo folders".

| Screen | What it shows | What you can do |
|---|---|---|
| **Dashboard** | The run in one place. Top row: counts (collected, kept, dropped, refused sources, switched items). Sources table: each site and what it gave. Item browser: the kept items; the filters on the left narrow them (company, source, date, event type, technology, region, fact or claim, text search). Click an item to see every field and **why it passed or failed**. Stories view and charts | Download the visible items as JSON or CSV (in memory, not saved on the laptop) |
| **Settings** | Every control that changes the next run: regions, technologies, event types, months back, extra and excluded keywords, "require industrial", source types, use discovered sources, minimum trust score, items per source, discovery on or off, switching on or off, the watchlist | Save, reset to defaults, see a list of what differs from the defaults. Changes apply to the next run |
| **Sources** | The register (approved and refused sites with reasons) and the **candidates the scout found**, with trust score, evidence and whether they are usable | Accept or reject a candidate. Accept is disabled for an unusable candidate: a person cannot override the safety rules. Nothing here is an Atlas Copco approval |
| **Run** | A launcher for `python -m atlas.run` with live progress | Start, stop, see the summary when done |
| **Report** | Choose a run, then **One-page summary (default)** or **Full report**, then PPTX or PDF | Generate, download, list reports already in the Volume |

---

## 8. The reports (one page and full)

### One-page summary (for Atlas Copco)
One slide or one page, four boxes, every line computed from the run's data (no invented text):

1. **Look at first:** the 3 most important events at other companies, ranked acquisition, partnership,
   investment or expansion, regulation, then product launch. One per company, with date, a fact, "fact" or "claim",
   and a clickable source link.
2. **Other facts:** 3 more recent facts in the same form.
3. **Difference from Atlas Copco:** how many items are Atlas Copco's own news and how many are about others, the
   topics others cover where Atlas Copco has no item, and the most common events at other companies.
4. **Sources:** how many were read, how many refused, and whether scout-found sources are not yet approved.

What counts as a fact on this page: it must contain a number or an event verb (acquired, launched, expanding...), must
not be a blog teaser ("in this article we will..."), and a text containing a removed-name placeholder is never
shown. Only one entry per company is shown.

### Full report (about 10 slides or pages)
Title, executive summary, scope and method, what we found, by company, by technology and event type, stories seen in
several sources, sources and compliance (refused sources are never hidden), how to read fact versus claim, and an
appendix with every item and link. Built by `atlas/report/build.py` with `pptx_builder.py`, `pdf_builder.py` and
`charts.py`. A last-line check refuses to build a report if an item contains an email or phone number.

Both reports are built in memory and uploaded to `reports/`. No file is written to the laptop.

---

## 9. The filter: every rule and reason code

Four checks (Phase 1). An item passes only if all four pass:

| Check | Passes when | Reason code if not |
|---|---|---|
| Compressor-related | a compressor keyword is in the title or text (plus your extra keywords) | `no_compressor_keyword` |
| North America | the source is based in US, Canada or Mexico, or the text names a place there | `not_north_america` |
| Credible source | the source is vetted "working" and not blocked | `source_not_credible` |
| Recent | the date is within the last N months (default 12) | `date_missing`, `date_in_future`, `too_old` |

"Industrial" is only a flag (`industrial_hint`), not a gate, unless you turn on "require industrial".

Extra rules from the settings (Phase 2), checked after the four, in this order:

| Rule | Reason code |
|---|---|
| The item's region (US, CA, MX) must be one of the chosen regions | `region_not_selected` |
| If technologies are chosen, the item's technology must be one of them | `technology_not_selected` |
| If event types are chosen, the item's event type must be one of them | `event_type_not_selected` |
| The title or key facts must not contain an excluded keyword | `excluded_keyword` |
| If "require industrial" is on, the industrial flag must be set | `not_industrial` |
| The source's type must be one of the chosen types | `source_type_not_selected` |

Every failed check is listed (not just the first). With no settings the filter behaves exactly like Phase 1.
The default regions are now **US + Canada**.

---

## 10. The scout engine: discovery, trust score, switching

### Discovery (`atlas/scout/discover.py`)
Finds candidate sites in this order: a **seed list** (`config/discovery_seeds.yaml`, about 37 starting points,
all marked unverified), **links found on our own sources**, and **RSS feeds advertised on a candidate's homepage**.
An official search API is supported only as an optional, off-by-default setting; **no search engine page is ever
scraped**. Every request goes through the Compliance Gate. A run can add up to 60 new candidates.

### Automatic vetting (`atlas/scout/vet.py`)
For each candidate, with at most 8 requests, it repeats the hand procedure:
1. `robots.txt` allows the feed or listing?
2. **Terms:** find the website terms of use (purchase and sales conditions do not count), including a parent
   company's terms when the footer links to them. Search the **whole** page for scraping, crawling, spider, robot, bot,
   data mining, harvest, automated means, machine learning. A match means `forbids_automation` and a short quote
   is kept. No terms page found means `unknown`, which is treated as **not usable**.
3. Is there an RSS feed or a news list? Is the page public (no login or paywall)?
4. Sample the newest items: newest date and the share of titles that mention compressors.

A candidate is **usable** only if robots allow, terms are positively ok, it is public, and it has a dated item.

### Trust score (0 to 100, no AI, every row explained)
| Points | Condition |
|---|---|
| 25 | website terms read and ok (0 if unknown; a forbidding clause forces the score to 0) |
| 15 | robots.txt allows |
| 15 | a feed exists (10 if only an HTML list) |
| 15 | newest dated item within 30 days (10 within 90, 5 within a year) |
| 15 | at least half the sampled titles are about compressors (10 if a quarter, 5 if any) |
| 10 | a government site, an association, or an official company site from a verified seed |
| 5 | HTTPS and the same domain for feed and articles |

### Which discovered sources a run may use
All of these must hold: "use discovered sources" is on; the candidate is usable; trust score is at or above the
minimum (default 70); its type is allowed; it has not been rejected by a person; it is not already in the register;
its newest item is inside the recency window; and its relevance sample is not zero. **Nothing is ever approved
automatically.** Discovered sources are always labelled "not approved by Atlas Copco".

### Switching (`atlas/scout/fallback.py`)
If a source is refused by the gate, returns zero pages, or hits a 429/503, and a **watch entry** follows its company
(the watchlist is in the settings: Ingersoll Rand, Kaeser, Sullair, Quincy, Gardner Denver, Hertz), the run:
1. Labels items other sources already gave it that mention the company.
2. Collects more from the other allowed sources and keeps only items that mention the company in their title,
   key facts or extracted company.
3. Labels them `via_fallback`, adds a "switched" row to the sources table, prints and logs it.

A guard refuses the refused site, its subdomains, and any web archive, cache, translation or proxy route to it
(`fallback_forbidden_route`). So switching is a **visible, labelled feature**, never a hidden workaround and never a
way around a block.

### Stories (`atlas/scout/stories.py`)
Items join one story when the company is the same and either the product is the same, or the event type is the same
(and not the catch-all "other") with similar titles of 4 or more words, and they are within 10 days. Groups are
transitive and the story id is stable between runs.

---

## 11. Sources: what we use and what we refused

**Read in the final run (7):**

| Source | Type | Notes |
|---|---|---|
| Compressed Air Best Practices | trade news | RSS |
| Quincy Compressor blog | competitor | RSS |
| Sullair (Hitachi Global Air Power) US news | competitor | list page |
| Pumps & Systems | trade news | RSS; mostly off-topic, 0 items passed |
| US DOE newsroom | government | list page; 0 items passed |
| FS-Elliott news | competitor | found by the scout, **hand-checked**, terms read |
| Burckhardt Compression news | competitor | found by the scout, **hand-checked**; region set to CH so an item passes only if its text names a North American place |

**Refused (7), shown in every report:** CAGI, PR Newswire and Plant Services (their terms forbid automation); Plant
Engineering, Ingersoll Rand and Business Wire (they answered 403/429 to our polite agent, so we did not retry or bypass);
**Sundyne** (its website is under Honeywell's terms, which forbid "any robot, spider, or other automatic device").

We also **did not** use Atlas Copco's own newsroom (it adds nothing to a market study) and Kaeser's blog (its posts
carry no dates).

**Candidates held back:** Mikropor (server drops our connection about one time in three), Powerex (no website terms,
no news since 2024), Gas Compression Magazine, Northwest Pump and Sullivan-Palatek (robots allow and they have
feeds, but there is no terms page at all, so they need the owner's permission), and every Canadian site we tried
(blocked by robots.txt or by terms). The evidence is in `docs/source_vetting.md`.

---

## 12. Where everything is stored

All in the Databricks Volume `/Volumes/atlas_poc/default/data/<prefix>/`:

| Folder | Contents |
|---|---|
| `source_register/` | the list of sources used in the run (`sources.json`) |
| `raw/<source>/<run>.json` | metadata of what was collected (URL, title, status). No page text |
| `clean/<source>/<run>.json` | every cleaned item, passed or failed, with its reasons |
| `facts/<source>/<run>.json` | only the items that passed the filter |
| `output/poc_<run>.json` | the results: sources, items, stories, the settings used |
| `logs/<run>.json` | gate decisions, refusals, errors, discovery and switching notes |
| `settings/scout_settings.json` | the saved settings |
| `scout/candidates.json`, `scout/decisions.json` | what the scout found, and the team's accept/reject decisions |
| `reports/` | the generated PPTX and PDF files |

Items written for switching sit under `.../fallback_<refused source>/`. The repo's own config lives in `config/`:
`sources.yaml` (the register), `keywords.yaml`, `technologies.yaml`, `aliases.yaml`, `products.yaml`,
`scout_settings.yaml` (defaults), `discovery_seeds.yaml`.

---

## 13. Legal and safety rules

- Only **public** pages; robots.txt checked for every run and every URL; terms read.
- At least **3 seconds** between requests; identified User-Agent with a contact address.
- **A block is never bypassed**: no mirrors, no archives, no proxies, no retries to dodge limits. A 429 or 503 stops that source.
- **Facts, not text:** we store short facts and links, never article text. Personal data (names, emails, phones) is removed.
- **Nothing on laptops:** everything is written to Databricks from memory; every run checks that no data file was created locally.
- **No source is approved by us.** All stay "proposed" until Atlas Copco approves them. Discovery only suggests.
- **Unknown terms mean not usable.** A site with no terms page cannot be used without the owner's permission.
- **Secrets:** the token lives only in your own `.env`, which is git-ignored. Never paste it anywhere. Rotate it if it was ever shared.

---

## 14. Who did what

| Person | Phase 1 | Phase 2 |
|---|---|---|
| **Nikhil** | Storage, compliance gate, collector, run command, shared data models, source vetting, docs | Saved settings, settings-aware filter, switching, stories, run integration, sample data, one-page summary, final demo run and hand-checks, plus fixes across the others' files after live testing |
| **Ragini** | Collector and source work | Discovery, automatic vetting, trust score, seed list, demo search tool |
| **Sachi** | Extractor, cleaner, filter keywords | Region, event type and product detection, new technologies and aliases, full PDF and PPTX report |
| **Parth** | Documentation and checks | The Streamlit app (five screens) and its tests |

Each person kept to their own files and `parent2.md` fixed the exact interfaces, so four people using different AI
tools still produced code that fits together. The final integration also changed some files of the others where live
tests showed problems; every such change is in `docs/decisions.md`.

---

## 15. The problems we found and fixed

Live runs and hand-checks against real pages found real bugs. All have regression tests.

| Problem | Fix |
|---|---|
| Brand and product names ("Polaris P300", "Fluke") were deleted as if they were people | name removal needs a full name and ignores machine words |
| Wrong companies ("Alpha Pore" for Donaldson) | 12 company aliases added |
| A how-to article tagged "regulation"; a video episode tagged "launch"; "wins an order" tagged "award" | event rules corrected |
| The scout read Sundyne's purchase conditions and marked its terms fine, but the real website terms (Honeywell) forbid robots | vetter reads website terms first, follows a parent's terms link, ignores third-party platforms; Sundyne blocked; its three fetched pages deleted |
| Story grouping merged two unrelated "other" articles | "other" never joins items; short titles cannot join |
| Switching missed an article whose title did not name the company | it also uses the extracted company |
| The discovery cap of 25 left half the seeds untried | raised to 60 |
| Dates faked as 1 January from page footers | such dates are treated as no date |
| Presidio downloaded a 400 MB model | the small model is pinned |
| A terminal that looked frozen | live progress lines |

---

## 16. What is not finished, and what we need from Atlas Copco

**Not finished or not proven**
- Only **7 sources** are read. More need written permission or a verified terms page (see section 11).
- **No Canadian source** works yet, so "Canada" in the scope is only covered through items that mention it.
- **0 switched items** in the demo run. The mechanism is proven live (one real labelled item, refused host never
  contacted), but the demo itself shows none, and so no switched item could be hand-checked from the run.
- **9 items** hand-checked (target was 10): `docs/check_results_phase2.md`.
- Most facts are company press releases, so they are labelled **claim**. Only a few are **fact**.
- The one-page **PPTX** was not rendered during development (the PDF was), so open it once before presenting.
- Mikropor and other flaky or unclear sites remain candidates only.

**What we need from Atlas Copco** (also in `docs/questions_for_atlas_copco.md`)
1. Approval of the source list (everything is "proposed").
2. A short permission email to the owners of the sites that have no terms page, and to a Canadian trade magazine.
3. Whether they have a slide template, so the report can match it.
4. Whether Mexico (Spanish-language sources) is in scope.
5. Whether a search API may be used for discovery (default: no).

---

## 17. Troubleshooting

| Problem | Cause and fix |
|---|---|
| `ModuleNotFoundError` for rapidfuzz, streamlit and others | You used Anaconda's Python. Use `.venv\Scripts\python.exe` or activate the venv |
| `Port 8501 is not available` | An older app is already running. Open `http://localhost:8501`, or start another with `--server.port 8599` |
| The app shows no run or the wrong data | `ATLAS_PATH_PREFIX` in `.env` decides the folder. Empty means the real demo folders, `dev/<name>` means your sandbox |
| `storage_check` fails | Check `DATABRICKS_HOST` and `DATABRICKS_TOKEN` in `.env`; the token may have expired |
| Run seems to hang | It is waiting 3 seconds between requests and loads the language model on the first page (about 15 seconds). Watch the progress lines |
| A source shows "refused by the compliance gate" | By design. The reasons are in the log and the Sources screen. It is never bypassed |
| "settings ... is not a valid ScoutSettings" | A saved settings file is invalid; the run stops on purpose and names the file. Fix it in the Settings screen or delete `settings/scout_settings.json` |
| Report fails with `PersonalDataError` | An item contained an email or phone number. Inspect it in the Dashboard and fix the extractor |
| `Cannot start: CONTACT_EMAIL is not set` | Fill `CONTACT_EMAIL` in `.env` |
| A site that worked now fails | Sites change. Re-vet it; never retry around a block |

---

## 18. A 10-minute demo script

1. **The problem (1 min).** Atlas Copco needs market intelligence; we automate it legally and explainably.
2. **The pipeline (2 min).** Show `docs/images/pipeline.png`: gate, collect, extract, clean, filter, save. Stress
   facts-not-text and nothing on laptops.
3. **The one-page summary (2 min).** Open `onepager_20261115T204628Z.pdf`: what to look at, facts, difference from
   Atlas Copco, sources. Click a link.
4. **The dashboard (2 min).** Start the app. Show the sources table (7 read, 7 refused with reasons), open one item, show
   "why was this kept or dropped".
5. **The scout engine (2 min).** Sources screen: candidates with trust score and evidence. Tell the Sundyne story:
   the scout was wrong, a human check caught it, we fixed the vetter. This shows the safety net working.
6. **Settings (1 min).** Change "months back" or add an excluded keyword, save, point out it applies to the next run.
7. **Close.** What we need from Atlas Copco (section 16).

---

## 19. File map

```
GUIDE.md                this file
README.md               short setup and run
parent.md / parent2.md  the full team briefs (Phase 1 / Phase 2) with interfaces and rules
wd.md / wd2.md          who does what (one page each); nikhil*.md ragini*.md sachi*.md parth*.md personal briefs
prepare.md              presentation prep with a pipeline picture
Friday_PoC_Spec.md      the original specification
demo_search.py          search a finished run from the terminal

atlas/
  settings.py           reads .env
  models.py             every data shape (Source, Item, OutputEnvelope, ScoutSettings, Candidate ...)
  storage.py            all reads and writes to the Databricks Volume
  storage_check.py      proves the storage works
  compliance.py         the Compliance Gate (robots, terms, delay, User-Agent)
  collect.py            RSS or list page, polite fetching, in memory
  extract.py            facts, dates, company, product, region, event type, personal-data removal
  clean.py              duplicates, ISO dates, company-name merging
  filter.py             the four checks plus settings rules
  run.py                the one command that runs everything
  scout/
    settings_store.py   save and load settings, candidates, decisions; which discovered sources may run
    discover.py         finds candidate sources
    vet.py              checks a candidate legally and scores its trust
    fallback.py         switching when a source is refused
    stories.py          groups items into stories
  report/
    onepager.py         the one-page summary (PPTX and PDF)
    build.py            the full report (shared numbers), pptx_builder.py, pdf_builder.py, charts.py
app/                    the Streamlit app: main.py, pages/1..5, lib/ (logic with tests)
config/                 sources, keywords, technologies, aliases, products, scout defaults, seeds
docs/                   decisions.md (every decision), source_vetting.md, check_results*.md, frontend.md,
                        report_design.md, glossary.md, questions_for_atlas_copco.md, demo_note.md, images/
tests/                  442 offline tests and synthetic fixtures
```

`docs/decisions.md` is the log of every decision and fix with its reason; read it when someone asks "why did we do it this way?".
