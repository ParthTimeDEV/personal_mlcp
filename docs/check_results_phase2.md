# Phase 2 hand-check (16 Nov 2026)

Run checked: `20261115T204628Z` (empty prefix, the real demo folders). Method: each item's page was fetched again
through the Compliance Gate (3 s delay) and compared with what the pipeline stored: title on the page, date year on
the page, company in the page text, and the share of each stored key fact's words that occur in the page text.

## Items (9 checked: 2 per source, one source gave 1)
| Source | Item | Result |
|---|---|---|
| airbestpractices_news | CalNEXT Studies AMS Assemblies for Energy Efficiency | title, date and facts match the page (fact overlap 1.0) |
| airbestpractices_news | Atlas Copco Group acquires a compressed-air company in Portugal | title, date, company, facts match; event type acquisition: right |
| quincy_compressor_blog | How to Size an Air Compressor for Jackhammers or Sandblasting | matches; event type other: right (how-to) |
| quincy_compressor_blog | What Industries Commonly Use Vacuum Pumps? | matches; technology vacuum pump: right |
| sullair_america_news | Electric Versus Diesel Portable Compressors | matches (the page names Hitachi Global Air Power more than Sullair) |
| sullair_america_news | Rep. <PERSON> Tours Hitachi Global Air Power ... | facts match (0.93 to 1.0); the name is correctly removed |
| fs_elliott_news | Lifecycle Optimization ... Episode 5 | matches; event type other: right (video series) |
| fs_elliott_news | Lifecycle Optimization ... Episode 1 | matches; was tagged product launch before the fix, now other |
| burckhardt_compression_news | Burckhardt Compression wins order for the Boaventura Energy Complex | matches; was tagged award before the fix, now other |

No wrong title, date, company or fact was found. Fact overlap ranged from 0.9 to 1.0 (the missing words are
punctuation or the stored sentence being shortened).

## Problems found by this check and fixed (all with regression tests)
1. Product and brand names were removed as if they were people ("Polaris P300", "Fluke", "Regulus Centrifugal",
   "Delivering Oil-Free"). The name removal now needs a full name: 2+ letter-only words and no machine word.
2. Wrong companies ("Alpha Pore" for Donaldson, "Service & Construction", "Bobcat Service"): 12 company aliases added.
3. A how-to article was tagged "regulation / standard"; a video episode was tagged "product launch"; "wins an
   order" was tagged "award". Event rules corrected.
4. The scout read Sundyne's purchase conditions as its website terms; Sundyne's real terms (Honeywell) forbid robots.
   Vetter fixed, Sundyne blocked, its files removed from the Volume (see `docs/source_vetting.md`).
5. Switching only looked at titles and key facts; a Kaeser article whose title never names Kaeser was missed. It now also
   uses the extracted company field.

## Switching (fallback) items
The demo run found no coverage of Ingersoll Rand in the 20 pages read per source, so it has 0 switched items; there
are no switched items to hand-check in the run. The mechanism was checked live on 16 Nov with a stand-in refused
company: followed company `Kaeser`, second pass over `airbestpractices_news`, one item came back labelled
`via_fallback` for the refused source, from
`https://www.airbestpractices.com/industry-news/best-practices-2026-expo-conference-delivers-record-attendance`
(a real page, title and facts match), and the refused host was never contacted.

## Not checked / limits
- 9 items, not 10, and 0 of the 3 switched items asked for in the brief (none exist in the run).
- Items are mostly company claims (labelled `claim`); only a few are `fact`.
- The one-page summary's PPTX could not be rendered here; the PDF was rendered and read.
