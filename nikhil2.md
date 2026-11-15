# nikhil2.md: Switching, stories, settings-aware filter, integration

**Person:** Nikhil. Read `parent2.md` first, fully. This file is your task spec and the prompt kit for your AI.

## Using this file with your AI
Give your AI, in order: (1) all of `parent2.md`, (2) this file, (3) `atlas/models.py`, `atlas/storage.py`, `atlas/filter.py`, `atlas/run.py`, (4) the kickoff prompt below. Demand the output format from `parent2.md` section 12.

### Kickoff prompt (paste as-is)
> You are helping me extend a scraping pipeline for an industrial-compressor market scout. I have pasted the Phase 2 master brief, my task file, and the current shared code. Implement `atlas/scout/__init__.py`, `atlas/scout/settings_store.py`, `atlas/scout/fallback.py`, `atlas/scout/stories.py`, the changes to `atlas/filter.py` and `atlas/run.py`, and the tests listed in my task file, using the exact signatures in `parent2.md` section 10 and the models in `atlas/models.py` (import them, never redefine). Return each file in full under a heading with its repo path. Never write data files to local disk; all persistence goes through `atlas/storage.py`. Source-switching must never contact a refused site, a mirror, a cache or an archive of it. No silent fallbacks: record failures and show them. With default settings the pipeline must behave exactly as before. Tests run offline with `pytest`. List every assumption at the end. If a requirement is ambiguous, ask me instead of choosing.

## Your files
| File | Status |
|---|---|
| `atlas/models.py`, `atlas/storage.py`, `config/scout_settings.yaml` | done; you handle change requests |
| `atlas/scout/__init__.py`, `settings_store.py` | you write (first) |
| `atlas/scout/fallback.py`, `stories.py` | you write |
| `atlas/filter.py`, `atlas/run.py` | you change |
| `tests/test_settings_store.py`, `test_scout_fallback.py`, `test_scout_stories.py`, `test_filter.py`, `test_run.py` | you write and extend |
| `docs/decisions.md`, `requirements.txt`, `README.md` | you maintain |

## Task N0: Unblock the others (do first, same day)
1. Write `settings_store.py` (signatures in `parent2.md` section 10). Storage paths: `settings/scout_settings.json`, `scout/candidates.json`, `scout/decisions.json`. `load_settings` returns the saved settings if present, otherwise `default_settings()` from `config/scout_settings.yaml`. A saved file that fails validation raises a clear error naming the file; do not silently use defaults.
2. Create `tests/fixtures/sample_output.json`: a **synthetic** `OutputEnvelope` (invented companies and text) with 8 to 10 items covering all new fields, 2 stories, 1 item with `via_fallback=true`, 1 refused source and 1 discovered source in `sources`. Generate it from the models so it validates. Parth and Sachi build against it.
3. Add Ragini, Sachi and Parth to the new files' ownership notes in `parent2.md` if anything changes. Tell the team when D0 is done.

## Task N1: `usable_sources` (in `settings_store.py`)
Turn `Candidate`s into `Source`s for a run: `origin="discovered"`, `status="proposed"`, `vetting_status="working"`, `trust_score` copied, `region` from the candidate, `licence_note` default. Include a candidate only if all are true: `settings.use_discovered_sources`; `candidate.usable`; `trust_score >= settings.min_trust_score`; its type is in `settings.source_types`; no `rejected` decision; and (if you add this rule, record it) not already in the register by domain. An `accepted` decision does not override `usable=false`: acceptance only makes an eligible candidate eligible, it cannot make an unsafe one usable.

## Task N2: Filter obeys settings (`atlas/filter.py`)
Add `settings: ScoutSettings | None = None`. `None` means Phase 1 behaviour exactly (existing tests must pass unchanged). With settings:
- `recent_months` from settings.
- **Region:** an item passes the region rule if its `region` is in `settings.regions`; if `item.region` is None, fall back to the Phase 1 rule (source region in US/CA/MX or `mentions_us_location`) restricted to the chosen regions. Reason code `region_not_selected`.
- **Technologies:** if `settings.technologies` is non-empty, `item.technology` must be one of them. Reason `technology_not_selected`.
- **Event types:** if non-empty, `item.event_type` must be one of them. Reason `event_type_not_selected`.
- **Extra compressor keywords:** counted as compressor matches for the compressor-related check (matched in title and key facts only, because page text is gone). **Excluded keywords:** an item whose title or key facts contain one fails with `excluded_keyword`.
- **`require_industrial`:** if true, `industrial_hint` must be true, reason `not_industrial`.
- **Source types:** an item whose `source_type` is not in `settings.source_types` fails `source_type_not_selected`.
- All new reason strings are appended to the closed set; every failed check is still listed, in a fixed order (Phase 1 four first, then the new ones in the order above). `FilterResult` fields stay as they are; the new checks only add reasons and can set `passed=false`.
- `via_fallback` items go through the same filter. Nothing special.

Tests: every new rule with a passing and a failing case; `settings=None` equals Phase 1; reasons order; nothing dropped here (dropping stays in `run.py`).

## Task N3: Switching (`atlas/scout/fallback.py`)
Functions as in `parent2.md` section 10.
1. `plan_fallback(refused, watchlist)`: for each refused `Source`, return the `WatchEntry`s with `follow_when_blocked` whose name or alias matches the source's name or its company (use `company_from_source_name` from `atlas.extract` or a local equivalent; record which). A refused source with no matching watch entry produces nothing and is logged as "no watch entry, nothing to switch to".
2. `collect_fallback(...)`: 
   - First pass: items already collected this run (`already`) that mention an entry (whole-word, case-insensitive, name or aliases, in title or key facts).
   - Second pass only if `fallback_enabled`: for each allowed source (not refused, type allowed by settings), collect up to `settings.fallback_max_items_per_source` through the existing `collect_source` and the same gate, extract and keep only items whose title or key facts mention an entry. Respect the 3 s delay; do not exceed the per-source item cap; stop on 429/503 as usual.
   - **Never fetch the refused source, any URL on its domain, a web-archive copy, a cache, a translation or proxy URL.** Add a guard: refuse any URL whose host equals or is a subdomain of a refused source's host, and any URL containing `web.archive.org`, `archive.ph`, `webcache`, `translate.goog`; record such a refusal with reason `fallback_forbidden_route`.
   - Return a `CollectResult` (pages and refusals) for the new pages only.
3. `apply_fallback_labels(items, entries, refused_by)`: set `via_fallback=True`, `fallback_for=<source_id>`, `watch_matches=[...]` on matching items (copy, do not mutate). An item from the refused source's own competitor newsroom is never labelled, because that source was not read.
4. Visibility: in `run.py` each fallback appears as a `SourceSummary(kind="fallback", fallback_for=<refused id>, ...)` row, is printed in the summary ("Switched: ingersoll_rand_news → 7 items from 3 other sources"), and is written to the log.

Tests (offline, mocked transports): switching triggers on gate refusal, on zero pages and on 429; no request ever goes to the refused host or to archive hosts (assert on the mock's request log); fallback off means no second pass; no watch entry means no switching and a log line; items are labelled; delay and caps respected.

## Task N4: Stories (`atlas/scout/stories.py`)
`build_stories(items, window_days=10)` returns `(items_with_story_id, clusters)`.
- Two items belong to one story if: same canonical `company` (non-null) **and** (same non-null `product` **or** same non-null `event_type` with titles similar enough: RapidFuzz `token_set_ratio >= 80`) **and** published within `window_days` of each other (items with no date can join only on same product).
- Use union-find so groups are transitive. Same-source duplicates are already removed by `clean.py`; a story only counts as multi-source if it has 2 or more distinct `source_id`s, but single-item stories are still produced (every item gets a `story_id`).
- `story_id` = first 12 hex of sha256 of the sorted `item_id`s' earliest id plus company; stable across reruns for the same members.
- `headline` = title of the earliest dated item; fill `first_published`, `last_published`, `via_fallback_count`.
- Never merge across different companies; never create a company or product that no item has.

Tests: same story across 3 sources; different companies are not merged; date window; transitive merge; a no-date item; stable ids; empty input.

## Task N5: `run.py` integration
1. New flags: `--use-default-settings`, `--no-discovery`, `--no-fallback`. Without flags, load settings with `load_settings()`.
2. Source list = register + `usable_sources(...)` from saved candidates and decisions. If `settings.discovery_enabled` and not `--no-discovery`, call Ragini's `discover_candidates` and `vet_candidate` first, save with `save_candidates`, then compute usable sources. A discovery error is logged, never fatal.
3. Existing loop per source stays. Pass `settings` to `apply_filter`, and `max_items = settings.max_items_per_source` unless `--max-items` is given.
4. After the loop: if fallback is enabled, run the switching step for refused (and empty or rate-limited) sources; extract, clean and filter those items the same way; label them.
5. `build_stories` over all passed items. Write `OutputEnvelope` with `stories`, `settings_used`, `candidates_considered`.
6. Summary prints: discovery (found, vetted, usable), switching (what was switched for what), stories (count, multi-source count), and the existing checks. Progress lines as in Phase 1.
7. Exit code semantics unchanged: refusals and switching are findings, not errors.
8. Extend `tests/test_run.py` with mocked stages: discovery adds a source; switching adds a fallback row; settings are passed to the filter; default settings equal Phase 1 output.

## Task N6: Integration and final run
1. As each teammate pushes, `git pull --rebase origin main`, `pip install -r requirements.txt`, run `python -m atlas.run --max-items 5` under `dev/nikhil`.
2. If an interface does not match `parent2.md` section 10, ask the **owner** to fix it; do not patch their file.
3. Run with a refused source and a watch entry (Ingersoll Rand is refused today) and confirm real fallback items appear. Hand-check 3 of them against their live pages.
4. Final demo run with an empty prefix; tag it `phase2-demo`; give Parth the numbers for the frontend demo.
5. Update `README.md` (new commands, the app, the report), `docs/decisions.md`.

## Acceptance criteria
- [ ] `pytest -q` passes offline for the whole repo.
- [ ] Default settings reproduce Phase 1 output.
- [ ] A refused source triggers visible switching; the request log proves the refused host was never contacted again.
- [ ] Settings changes alter the next run's output.
- [ ] Stories group items across sources; ids are stable.
- [ ] No data or report files on the laptop (`run.py`'s own check passes).

## Do not
- Do not fetch a refused site through any route; do not add retries to dodge limits.
- Do not make discovery or acceptance approve anything for Atlas Copco.
- Do not change another person's file; ask the owner.
- Do not print or commit the token.
