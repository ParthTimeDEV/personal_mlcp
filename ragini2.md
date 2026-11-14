# ragini2.md: Source discovery, automatic vetting, new sources

**Person:** Ragini. Read `parent2.md` first, fully. This file is your task spec and the prompt kit for your AI.

## Using this file with your AI
Give your AI, in order: (1) all of `parent2.md`, (2) this file, (3) `atlas/models.py`, `atlas/compliance.py`, `atlas/collect.py`, (4) the kickoff prompt below. Demand the output format from `parent2.md` section 12. The AI cannot browse for you: you read real pages and give it facts; every claim about a site must come from what you or your code saw today, never from the AI's memory.

### Kickoff prompt (paste as-is)
> You are helping me build the source-discovery part of a scraping pipeline for an industrial-compressor market scout. I have pasted the Phase 2 master brief, my task file, and the shared code (`models.py`, `compliance.py`, `collect.py`). Implement `atlas/scout/discover.py`, `atlas/scout/vet.py` and the tests listed in my task file, using the exact signatures in `parent2.md` section 10 and the models in `atlas/models.py` (import them, never redefine). Return each file in full under a heading with its repo path. All HTTP must go through the existing `ComplianceGate` (robots.txt, delay, User-Agent). Never scrape a search engine's result pages, never bypass a block, never mark anything approved. A discovered source is usable only if its terms are positively `ok`. Never write data files to local disk. Tests run offline with `pytest` and `httpx.MockTransport`. List every assumption at the end. If a requirement is ambiguous, ask me instead of choosing.

## Your files
| File | What |
|---|---|
| `atlas/scout/discover.py` | find candidate sources |
| `atlas/scout/vet.py` | vet one candidate automatically, trust score |
| `config/discovery_seeds.yaml` | the curated seed list |
| `config/sources.yaml`, `docs/source_vetting.md` | new vetted sources for the wider scope |
| `tests/test_scout_discover.py`, `tests/test_scout_vet.py` | tests |

## Task R0: Setup
`parent.md` section 12 setup; `python -m atlas.storage_check` PASS with `ATLAS_PATH_PREFIX=dev/ragini`; `CONTACT_EMAIL=industrymlcp@gmail.com`. Read `docs/source_vetting.md`: the automatic vetting must reproduce those steps.

## Task R1: Seed list (`config/discovery_seeds.yaml`)
A list of up to about 40 starting points, each with: `name`, `url` (homepage), `type_guess` (competitor | trade_news | government), `region` (US | CA | MX), `why`, and `verified: false`. Cover the wider scope: US and Canadian compressor makers and distributors, trade publications for compressed air, vacuum, blowers, gas and hydrogen compression, industry associations, government energy and standards pages (US and Canada). Compile it from what you can see today (trade-magazine directories, association member pages, the footers of sources we already use); mark everything `verified: false`. Seeds are suggestions, not approvals; the automatic vetting decides. Do not include sites already in `config/sources.yaml`, and do not include the sites we found blocked (CAGI, PR Newswire, Plant Services) unless you note they need permission.

## Task R2: Discovery (`atlas/scout/discover.py`)
```python
def discover_candidates(sources, gate, settings, seeds_path="config/discovery_seeds.yaml",
                        known_domains=None, max_new=25) -> list[Candidate]
```
- Methods, in this order, tagging `discovered_via`: **seed** (read the seed file), **outbound_link** (from up to 3 pages of each source in `sources` that is `working`: collect external links to other domains that look like publishers, associations or companies: skip social media, ad networks, search engines, link shorteners, and anything already known), **feed_autodiscovery** (fetch a candidate's own homepage once and read `<link rel="alternate" type="application/rss+xml|atom+xml">`), and **search_api** only if `settings` allows it and `SEARCH_API_KEY` is set (otherwise skip silently with one log line; do not implement any provider that is not an official API).
- **Never fetch a search engine's results pages.** The code must have no URL for a search engine's website.
- De-duplicate by registered domain; skip `known_domains` (the register and earlier candidates); stop at `max_new`.
- Every fetch goes through `gate.can_fetch` and `gate.wait`. A candidate whose robots.txt disallows its homepage becomes a `Candidate` with `robots_status="disallowed"`, `status="rejected_by_rules"` and is never fetched further.
- `candidate_id` = first 12 hex of `sha256(domain)`. `type_guess` from the seed, or from the discovery context (a publisher link from a trade source is `trade_news`; unknown stays `trade_news` with a note). Region from the seed or `US`.
- A failure on one candidate is recorded in `Candidate.notes` and the loop continues.

## Task R3: Automatic vetting (`atlas/scout/vet.py`)
```python
def vet_candidate(candidate, gate, settings) -> Candidate
def trust_score(candidate) -> tuple[int, list[str]]
```
`vet_candidate` does, in order, through the gate, **at most 8 requests per candidate**:
1. **robots.txt:** allowed for the listing or feed URL → `robots_status`.
2. **Terms:** find the terms page (homepage footer links containing terms, legal, conditions, "terms of use"). Fetch it; extract text (trafilatura); search the whole page for sentences containing scrape, scraping, crawl, spider, robot, bot, data mining, harvest, automated means, machine learning (the same approach we used by hand; a long page must be searched in full, not just the main block). If found, `terms_status="forbids_automation"` and keep a quote of at most 200 characters in `terms_evidence`. If a terms page is found and none of those appear, `ok`. If no terms page is found or it cannot be read, `unknown`. Store `terms_url`.
3. **Feed or list:** use a discovered feed (`access_method="rss"`), else look for a news or press listing (`access_method="html"`, derive an `item_url_pattern` from article-like links). Neither found → `needs_review`.
4. **Public:** the listing returned 200 without a login redirect or paywall marker.
5. **Sample:** parse the feed or list; fetch at most 3 articles; read dates; compute `newest_item_date`, and `relevance_sample` as the share of sampled titles or feed entries (up to 10) containing a compressor-family keyword from `config/keywords.yaml`.
6. Set `status`: `rejected_by_rules` if robots disallow or terms forbid; `needs_review` if terms are `unknown`, no feed or list, or not public; else `auto_vetted`.
7. Set `usable = status == "auto_vetted" and terms_status == "ok" and robots_status == "allowed" and public_ok is True and newest_item_date is not None`.
8. Compute `trust_score` and reasons.

**Trust score** (pure function of the candidate; max 100; one reason line per row, including rows that earned 0):

| Points | Condition |
|---|---|
| 25 | terms read and `ok` (0 if `unknown`; automatic fail if `forbids_automation`) |
| 15 | robots allow |
| 15 | a feed exists (10 if only an HTML listing) |
| 15 | newest dated item within 30 days (10 within 90 days, 5 within 365, 0 otherwise or no date) |
| 15 | `relevance_sample` >= 0.5 (10 if >= 0.25, 5 if > 0, 0 otherwise or no sample) |
| 10 | `type_guess` is `government` or an association, or the domain is an official company or publisher site named in a seed with `verified: true` (5 for other seeds, 0 for links found by chance) |
| 5 | HTTPS and the same registered domain for feed and articles |

`trust_score` must never be a model call. Thresholds (`min_trust_score` default 70) are applied by `usable_sources`, not here.

### Tests (offline, `httpx.MockTransport`)
Discovery: seed read; outbound links filtered (social, search engines, already-known domains skipped); feed autodiscovery from a mock homepage; robots-disallowed homepage becomes `rejected_by_rules` and nothing else is fetched; `max_new` honoured; no URL of a search engine anywhere (grep-style assertion on every request made); one failing candidate does not stop the rest.
Vetting: terms with a scraping ban found deep in a long page → `forbids_automation` with a quote ≤ 200 characters; terms clean → `ok`; no terms page → `unknown` and `usable=False`; request budget (≤ 8) respected; 429 stops that candidate; trust score table for 5 hand-made candidates, each reason line present; score never above 100; default settings change nothing in Phase 1 modules.

## Task R4: Wider-scope sources (by hand, same procedure as Phase 1)
Vet **5 to 7 new sources** for the wider scope: at least 2 Canadian (English-language), at least 2 covering the new technologies (air treatment, blowers, vacuum, gas or hydrogen compression), and at least 1 more US competitor. Use the Phase 1 procedure and write them into `docs/source_vetting.md` (same format, with quotes) and `config/sources.yaml` (`region: CA` where applicable; all `proposed`). Use the automatic vetter on the same sites as a check: write in the vetting doc where its verdict and yours differ. Blocked or unreachable ones stay in the register with their status and reason. Target: the register has 10 to 12 `working` proposed sources in total.

## Task R5: Live check
Under `dev/ragini`, run discovery on the seed list with the real gate and print only metadata:
```python
from atlas.compliance import load_register, ComplianceGate
from atlas.scout.discover import discover_candidates
from atlas.scout.vet import vet_candidate
from atlas.scout.settings_store import load_settings
srcs = load_register(); gate = ComplianceGate(srcs); st = load_settings()
cands = [vet_candidate(c, gate, st) for c in discover_candidates(srcs, gate, st, max_new=10)]
for c in cands: print(c.domain, c.status, c.terms_status, c.trust_score, c.usable)
```
Report the table to the team. Then hand-check 3 `usable` candidates against the real site (terms, robots, feed). Send Nikhil the `scout/candidates.json` path so he can use it in a run, and give Parth sample candidates for the review screen.

## Acceptance criteria
- [ ] `pytest tests/test_scout_discover.py tests/test_scout_vet.py -q` passes offline.
- [ ] A real discovery run produces candidates with evidence, trust scores and reasons; unusable ones say why.
- [ ] No search-engine results page is ever fetched; no request bypasses the gate.
- [ ] 5 to 7 new sources vetted by hand and recorded with quotes; the register has 10 to 12 working proposed sources.
- [ ] Nothing is marked `approved`.

## Do not
- Do not scrape a search engine; do not use a search API without a team decision and a key in `.env`.
- Do not take robots or terms content from the AI's memory.
- Do not treat `unknown` terms as `ok`.
- Do not edit `models.py`; ask Nikhil.
