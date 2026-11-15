# Report design (PDF and PPTX)

Owner: Sachi. Code: `atlas/report/`. Spec: `sachi2.md` Part B, `parent2.md` section 8.

## How to make one

```python
from atlas.report import write_report, build_report
write_report("<run_id>", "pptx")   # reads output/poc_<run_id>.json, uploads reports/report_<run_id>.pptx, returns the Volume path
write_report("<run_id>", "pdf")
build_report(envelope, "pdf")      # bytes only (for the frontend download button)
```
Frontend (Parth): call `atlas.report.write_report(run_id, fmt)` for the "Generate" button and
`atlas.report.build_report(envelope, fmt)` if you only need bytes for `st.download_button`.

## Slides / pages (same content in both formats)

| # | Section | Content | Where the numbers come from |
|---|---|---|---|
| 1 | Title | run id, run date, "Prepared for Atlas Copco by Group 8, VIT Pune. Source list is proposed, pending approval." | `run_id`, `generated_at` |
| 2 | Executive summary | 3 to 5 fixed sentences filled with counts; 3 headline items with links | counts of `items`, `sources`, stories, `via_fallback` |
| 3 | Scope and method | regions, technologies, event types, time window, sources used; one line on the filter, one on compliance | `settings_used` (or `scope` when no settings were saved) |
| 4 | What we found | top 8 items: company, event type, date, label, flags, link | ranking rule below |
| 5 | By company | bar chart, top 10 companies; event types seen per company | `item.company` |
| 6 | By technology and event type | two bar charts; label and region counts | `item.technology`, `item.event_type`, `item.label`, `item.region` |
| 7 | Seen in several sources | stories whose items come from 2 or more distinct sources; switching items counted | `stories`, `item.story_id`, `item.source_id` |
| 8 | Sources and compliance | every source with kind, status, collected, passed, note; refused sources marked REFUSED with the gate's reason; discovered sources marked "discovered, not yet approved"; "Coverage for X came from Y, Z" | `sources`, `item.via_fallback`, `item.fallback_for` |
| 9 | How to read this report | fact vs claim, what "passed the filter" means, switching, discovered sources, limits | fixed text |
| 10+ | Appendix | every item: date, company, title, event type, region, label, flags, full link | `items` |

Slide 8 continues on a second slide past 12 sources; the appendix holds 12 rows per slide. The PDF
appendix paginates by itself (the table header repeats on every page).

## Rules the code enforces

- **Only envelope data.** Every number is counted in `atlas/report/build.py`; both builders read the
  same `ReportData`, so the PPTX and PDF cannot disagree.
- **No invented text.** Sentences are fixed templates filled with computed values. No AI model is used.
  Missing values show as "(not stated)" or "date not stated", never a guess.
- **Ranking for "What we found":** items in stories seen in more distinct sources first, then the
  newest publication date (undated last), then title A to Z.
- **Key facts** are shown as stored (max 3, max 200 characters). No other article text exists.
- **Personal data guard:** `build_report` raises `PersonalDataError` if any item field contains
  `@domain` or a phone-number pattern. This is a last line of defence; the extractor removes personal
  data before this point.
- **Charts:** matplotlib, Agg backend, PNG bytes in memory, Okabe-Ito colour-blind-safe colours. Fewer
  than 2 data points: a sentence instead of a chart.
- **Text never overflows:** titles and table cells are cut at a word boundary with "…"; the full link
  is kept in the appendix.
- **Speaker notes** on slides 2 to 8 say where each number comes from.
- **No local files.** Builders return bytes; `write_report` uploads with `atlas.storage.write_bytes`.
  A test patches `open()` and fails on any write.
- **No branding:** neutral layout, no Atlas Copco logo (adapt if Atlas Copco sends a template:
  `parent2.md` open question 5).

## What I checked

- Synthetic fixture (`tests/fixtures/report_envelope.json`, 14 items, 6 sources, 1 refused, 1
  discovered, 1 fallback source, 2 multi-source stories): built both formats, converted the PPTX to
  images and read every slide and page. Numbers match the fixture; links work; no text runs out of
  its box; the refused source, its reason, the switching line and the discovered flag are visible.
- Empty envelope and one-item envelope: valid reports with "No items passed the filter" and
  "Only one company in this run …" instead of charts.
- Real run, 14 Nov 2026: built both formats from the Friday demo run `output/poc_20261030T041113Z.json`
  (read from the Volume; a Phase 1 run, so region / event type / product are empty and show as
  "(not stated)"). Checked every slide and page: 15 items from 3 of 11 sources; all 6 refused sources
  shown with the gate's reasons (CAGI, PR Newswire, Plant Services, Plant Engineering, Ingersoll Rand,
  Business Wire); links open the right articles; no text overflow. Two fixes came out of it: the
  sources slide now holds 12 rows (11 sources had spilled one row onto a second slide), and the
  refused line points to the table instead of a list that was cut off. The same titles showed two
  event-type rule fixes (a distributor meeting is an `event`; "<PERSON> COO of ..." is an
  `appointment`), now in tests.
- Live run (S9), 15 Nov 2026, run `20261115T045141Z` under `dev/sachi` (`atlas.run --max-items 5`,
  default settings, regions US): `write_report` built and uploaded `reports/report_20261115T045141Z.pptx`
  and `.pdf`. Read every slide and page against the run's own printout: 13 items from 3 of 11 sources,
  6 refused sources with the gate's reasons, Ingersoll Rand switching tried with 0 items, 0 stories in
  two or more sources. Links open the right articles; no text overflow. Three wording fixes came out of
  it: the row that records a switching attempt is no longer counted as a source ("3 of 12" -> "3 of 11");
  "other" is no longer reported as the most common type of news ("Apart from 8 general articles, the
  most common type of news is award"); and a switch that found nothing is now stated ("Switching was
  tried for Ingersoll Rand (irco.com): no items about it were found in other allowed sources") instead
  of "No switching was needed".
- Real-page check of the same run (title, event type, product, region against the live articles):
  event types right for all items checked (acquisition, product launch, award x2, event, and "other"
  for the how-to blog posts); product `OFE1550` right (the Sullair OFE1550 award page); no product
  invented for the Fluke release, which names two models (ii1050 and ii1030), so `null` is correct;
  label `fact` right for the Atlas Copco acquisition. One bug found: two articles about places outside
  North America were tagged `US` because they name no North American place and the rule fell back to
  the source's region (Atlas Copco buying Iberoair in Agueda, Portugal; a Fluke release dated
  Eindhoven, Netherlands). Fixed: `config/keywords.yaml` now has `other_locations`, and an item that
  names places outside North America at least as often as its top North American region gets `null`.
  The fix applies to new runs; this run's stored items keep `US`.
- Not verified: the airbestpractices.com page for "Best Practices 2026 EXPO" (company `Kaeser
  Compressors`, technology `blower`), because the page could not be opened from here. Open it and check
  that Kaeser is the main company named; if not, the alias count picked a sponsor.
