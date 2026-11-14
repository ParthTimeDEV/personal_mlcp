# Decisions log

Questions asked, answers received, and spec deviations. Newest last.

| Date | Question / issue | Answer / decision |
|---|---|---|
| 2026-10-29 | Working rule | Serious project: no workarounds or fallback modes without explicit user approval. |
| 2026-10-29 | Databricks workspace, schema `atlas_poc`, volume `data`, token | Already set up by the user; user fills `.env`. |
| 2026-10-29 | Volume location | Differs from spec: catalog `atlas_poc`, schema `default`, volume `data` (so root is `/Volumes/atlas_poc/default/data`). |
| 2026-10-29 | VERIFY: Free Edition allows personal access tokens and the Files API? | Yes. `storage_check` PASS: write, read back, list all work from memory with a token; no local files created. |
| 2026-10-29 | Contact email for the User-Agent | `industrymlcp@gmail.com` |
| 2026-10-29 | Which 5 sources run on Friday | airbestpractices_news, quincy_compressor_blog, sullair_america_news, pumps_systems_news, doe_newsroom (team to confirm). Replaced after live runs: atlas_copco_usa_news (the client's own site adds nothing to a market study) and kaeser_usa_blog (posts carry no date, so none can pass "recent"). Vetted but not in the register: atlas_copco_usa_news, kaeser_usa_blog, atlas_copco_group_press, elgi_usa. |
| 2026-10-29 | Sources that refuse us without a ban (403/429) | Recorded `vetting_status: unreachable`, approval `status: needs_permission`; not retried or bypassed (Plant Engineering, Ingersoll Rand, Business Wire). |
| 2026-10-29 | Kaeser terms | No terms-of-use page found; recorded `terms_status: unknown` and flagged for Atlas Copco Legal. |
| 2026-10-29 | Dates found by trafilatura's extensive search | A date of exactly 1 January found only by that search is treated as no date (a bare "© 2026" footer was read as 2026-01-01). Real datelines in the text are still used. |
| 2026-10-29 | `fact` label for trade news | Narrowed to acquires/acquired/files/filed/completes/completed/appoints/fined/recall/regulation. "standard", "rule", "opens", "announces plans" removed: trade sites mostly republish company press releases, which are claims. |
| 2026-10-29 | Company for non-competitor sources | Known companies (`config/aliases.yaml`) first; spaCy ORG fallback only if the same name appears at least twice (headline repeats not counted); otherwise `null`. |
| 2026-10-29 | Personal-data scrub | Presidio allow-list of known company names and US place names, so they are not replaced by `<PERSON>`. The small model still over-removes some other words; this errs on the safe side. |
| 2026-10-29 | Team work split | Four people, file-level ownership; contracts fixed in `parent.md` and `atlas/models.py`. See `wd.md`. |
| 2026-10-29 | Dev vs demo storage | `ATLAS_PATH_PREFIX=dev/<name>` for development; only the final demo run uses an empty prefix. |
| 2026-10-29 | Filter inputs | Text is dropped after extraction, so extract computes `matched_keywords`, `mentions_us_location`, `industrial_hint` on `Item`; filter uses those and the title. |
| 2026-10-29 | Is "industrial" a required keyword? | No. Recorded as the `industrial_hint` flag only. |
| 2026-10-29 | Personal-data removal tool | Presidio + spaCy `en_core_web_sm`. |
| 2026-10-29 | Spec gap: gate vs `proposed` status | Spec says the gate skips non-approved sources, but all sources stay `proposed` until Atlas Copco signs off. Gate admits `proposed` and `approved`; rejects `blocked`, `needs_permission`, `unreachable`. |
| 2026-10-29 | Spec gap: two status lists | `sources.yaml` gets `vetting_status` (working / blocked / needs_permission / unreachable) separate from approval `status` (proposed / approved). |
| 2026-11-15 | Phase 2: what "no fallback" means | Silent engineering workarounds stay forbidden. Source switching is a visible, labelled feature (`via_fallback`, a `kind="fallback"` row, a log note, a line in the printed summary) and never reaches a refused site through any route. |
| 2026-11-15 | Switching guard | Every URL fetched during switching is checked: the refused host and its subdomains, and any URL containing web.archive.org, archive.org, archive.ph, archive.today, archive.is, webcache, cachedview, translate.goog, translate.google, googleusercontent are refused with `fallback_forbidden_route`. The guard wraps the real Compliance Gate, so robots.txt, the 3 s delay and the 429/503 stop still apply. |
| 2026-11-15 | When switching triggers | A source refused by the gate, a source that returned zero pages, or one that hit 429/503, if a watch entry (name or alias, `follow_when_blocked`) matches its name or company. No matching entry: nothing is switched and the log says so. |
| 2026-11-15 | Switching, two passes | Pass 1 labels items other sources already gave this run. Pass 2 collects up to `fallback_max_items_per_source` NEW pages per allowed source (URLs already collected are skipped, not re-fetched) and keeps only items whose title or key facts mention a followed entry. |
| 2026-11-15 | Filter region rule with settings | The four Phase 1 checks and their fields are unchanged. The chosen regions are an extra rule (`region_not_selected`): the item's own `region` if known, otherwise the Phase 1 evidence (source region, US location in text) restricted to the chosen regions. Default settings reproduce Phase 1 for Phase 1 items. |
| 2026-11-15 | Technology / event type unknown | With a technology or event-type selection, an item whose value is `null` fails (it cannot be confirmed to match). Empty selection means all. |
| 2026-11-15 | `usable_sources` extra rules | Takes an optional `register` and skips a candidate whose site is already in it; skips duplicate candidate ids. `accepted` decisions change nothing; only `rejected` excludes. Discovered source ids are `disc_<candidate_id>`. |
| 2026-11-15 | `RunLog.notes` added | Discovery and switching findings (not errors) go to `RunLog.notes`. Optional field, so Phase 1 logs stay valid. |
| 2026-11-15 | Stories | Same canonical company AND (same product OR same event type with RapidFuzz token_set_ratio >= 80) AND within 10 days; undated items join only on the same product; union-find. Story product/event type are set only when all items agree. `story_id` = sha256(smallest item id + company)[:12]. |
| 2026-11-15 | Invalid saved settings | `run.py` stops with exit code 1 and names the file; it never silently falls back to defaults. A discovery failure is logged and the run continues. |
