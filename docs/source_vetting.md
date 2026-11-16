# Source vetting

Checked on **2026-10-29** with the procedure in `parent.md` section 11. Agent used for every request: `AtlasCopcoStudentPoC/0.1 (+contact: industrymlcp@gmail.com)`, at least 3 s between requests, nothing saved to disk. Per source we fetched: `/robots.txt`, the homepage (to find news, feed and terms links), the terms page, and then one listing and one article through our own Compliance Gate and Collector.

**Result: 15 candidates vetted. 9 `working` (5 proposed, 4 vetted but not used), 3 `blocked` by their terms, 3 `unreachable` (the site refuses our agent without a ban).** After the first live runs two proposed sources were replaced: Atlas Copco USA (the client's own newsroom adds nothing to a study of the market) and the Kaeser USA blog (its posts carry no publication date, so none can pass the "recent" check). Quincy Compressor and Pumps & Systems took their places. Nothing was worked around. All sources stay `proposed` until Atlas Copco approves them; Atlas Copco's Legal team should review the list before go-live.

## Summary table

| # | source_id | name | type | access | robots | terms | public | test fetch | vetting_status | in register |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | airbestpractices_news | Compressed Air Best Practices | trade_news | rss | allowed | ok | yes | listing 25 entries, article 200 | **working** | proposed |
| 2 | atlas_copco_usa_news | Atlas Copco USA news | competitor (client) | html | allowed (crawl-delay 1) | ok | yes | listing 7 links, article 200 | working | **not used** (client's own site) |
| 3 | sullair_america_news | Sullair US news | competitor | html | allowed | ok | yes | listing 10 links, article 200 | **working** | proposed |
| 4 | kaeser_usa_blog | Kaeser USA blog | competitor | html | allowed | unknown | yes | listing 11 links, article 200 | working | **not used** (posts have no date) |
| 5 | doe_newsroom | US DOE newsroom | government | html | allowed | ok | yes | listing 14 links, article 200 | **working** | proposed |
| 6 | cagi_news | CAGI | trade_news | html | allowed | **forbids automation** | yes | not fetched (terms ban) | **blocked** | blocked |
| 7 | prnewswire_releases | PR Newswire | trade_news | html | allowed | **forbids automation** | yes | not fetched (terms ban) | **blocked** | blocked |
| 8 | plant_services_news | Plant Services | trade_news | rss | allowed | **forbids automation** | yes | not fetched (terms ban) | **blocked** | blocked |
| 9 | plant_engineering_news | Plant Engineering | trade_news | html | allowed (crawl-delay 10) | unknown | n/a | homepage HTTP 403 | **unreachable** | needs_permission |
| 10 | ingersoll_rand_news | Ingersoll Rand | competitor | html | unknown (HTTP 429) | unknown | n/a | robots and homepage HTTP 429 | **unreachable** | needs_permission |
| 11 | businesswire_releases | Business Wire | trade_news | html | disallow-all (HTTP 403) | unknown | n/a | robots and homepage HTTP 403 | **unreachable** | needs_permission |
| 12 | atlas_copco_group_press | Atlas Copco Group press releases | competitor (client) | html | allowed (crawl-delay 1) | ok | yes | homepage lists 4 recent releases | working, **reserve** | not in register |
| 13 | elgi_usa | ELGi US | competitor | rss | allowed | unknown | yes | feed 10 entries (mostly product pages) | working, **reserve** | not in register |

| 14 | quincy_compressor_blog | Quincy Compressor blog | competitor | rss | allowed | ok | yes | feed 10 dated entries, post 200 | **working** | proposed |
| 15 | pumps_systems_news | Pumps & Systems news | trade_news | rss | allowed | ok | yes | feed 12 dated entries, article 200 | **working** | proposed |

The proposed five are rows 1, 3, 5, 14 and 15. The register `config/sources.yaml` holds those five plus the six blocked or unreachable sources (rows 6-11). Rows 2, 4, 12 and 13 are vetted but not in the register; copy a row back if Atlas Copco wants one.

## Proposed five and why

Mix of 2 trade news sources, 2 competitors and 1 government page, as the spec asks.

- **Compressed Air Best Practices:** the strongest source; RSS feed, current industry news (newest entry 28 Oct 2026), entirely about compressed air.
- **Quincy Compressor:** a US compressor maker (Alabama) with a dated RSS feed; mostly educational posts, so mostly `claim` items.
- **Sullair US:** a major US compressor brand (Hitachi Global Air Power) with a news section and dated press releases.
- **Pumps & Systems:** US trade publication with a current dated feed (newest 27 Oct 2026) covering company appointments and acquisitions, including Atlas Copco items. It covers pumps and rotating equipment generally, so the filter drops most items; in a 6-item sample none passed.
- **DOE newsroom:** government source; general energy news, so the filter drops nearly everything. It shows the relevance filter working on a real feed. Optional by the spec.

Expect the useful results to come mainly from the first three. The last two are included for variety and to show the filter, not for volume.

## Details per candidate

### 1. Compressed Air Best Practices (airbestpractices_news)
- Checked on: 2026-10-29
- robots.txt: https://www.airbestpractices.com/robots.txt -> allowed for `*` (blocks only `/media/oembed`; separate rules exist for AI-training bots, not for our agent); crawl-delay: none
- Terms: https://www.airbestpractices.com/terms-conditions -> read in full (about 12,000 characters); no sentence on scraping, robots or automated access -> ok
- Feed/API: https://www.airbestpractices.com/rss.xml (25 entries, valid)
- Public, logged-out: yes
- Test fetch: RSS 200; one article (Atlas Copco Group expands U.S. operations, 28 Oct 2026) 200, about 51,000 characters of HTML, held in memory only
- Status: **working** — reason: RSS available, no restriction found

### 2. Atlas Copco USA (atlas_copco_usa_news)
- Checked on: 2026-10-29
- robots.txt: https://www.atlascopco.com/robots.txt -> allowed for `*` (restricts only some parts pages); crawl-delay: 1 s (we use at least 3 s)
- Terms: https://www.atlascopco.com/en-us/privacy-policy ("Legal & Privacy Notices") -> no sentence on automated access found -> ok
- Feed/API: none found (listing is an HTML page with paging)
- Public, logged-out: yes
- Test fetch: listing https://www.atlascopco.com/en-us/news/latest-news 200 (7 article links on page 1); one article 200
- Status: **working**, but **not used**: it is the client's own newsroom, which adds nothing to a study of what others are building. Removed from the register after the first live run.

### 3. Sullair US (sullair_america_news)
- Checked on: 2026-10-29
- robots.txt: https://america.sullair.com/robots.txt -> allowed for `*` (blocks only `/media/oembed`); crawl-delay: none
- Terms: https://america.sullair.com/en/terms-and-conditions-use (same text as the global site) -> read in full (about 17,000 characters); no sentence on scraping, robots or automated access -> ok
- Feed/API: none found. The global site www.sullair.com has no news section; the US site does
- Public, logged-out: yes
- Test fetch: https://america.sullair.com/en/news 200 (10 article links); one article 200
- Status: **working**

### 4. Kaeser USA blog (kaeser_usa_blog)
- Checked on: 2026-10-29
- robots.txt: https://us.kaeser.com/robots.txt -> allowed for `*`; crawl-delay: none
- Terms: no terms-of-use page found; the footer has only "Legal notice" (https://us.kaeser.com/company-information.aspx, an imprint) and privacy pages. No sentence on automated access in the legal notice -> **unknown** (flag for Atlas Copco Legal)
- Feed/API: none found. https://us.kaeser.com/about-us/press/press-releases/ lists no individual release links in its HTML, so the "Kaeser Talks Shop" blog is used instead
- Public, logged-out: yes
- Test fetch: blog index 200 (11 post links after excluding category and year pages); one post 200
- Status: **working**, but **not used**: in the first live run none of its posts showed a publication date, so none could pass the 12-month "recent" check. Removed from the register. Terms are also `unknown`.

### 5. US DOE newsroom (doe_newsroom)
- Checked on: 2026-10-29
- robots.txt: https://www.energy.gov/robots.txt -> allowed for `*` (blocks only `/media/oembed`); crawl-delay: none
- Terms: https://www.energy.gov/about-us/web-policies -> read in full; no sentence on automated access -> ok (US government site)
- Feed/API: none found for the newsroom
- Public, logged-out: yes
- Test fetch: https://www.energy.gov/newsroom 200 (14 article links); one article 200
- Status: **working** — caveat: general energy news, few items mention compressors

### 6. CAGI (cagi_news)
- Checked on: 2026-10-29
- robots.txt: https://www.cagi.org/robots.txt -> 200, no restrictions
- Terms: https://www.cagi.org/cagi-terms-of-use -> "use any data mining, robots, or similar automated data gathering and extraction tools to access the CAGI website" -> **forbids_automation**
- Feed/API: none found
- Public, logged-out: yes
- Test fetch: none beyond the homepage and terms page (the terms ban automated access)
- Status: **blocked** — reason: terms forbid automated access. Route: ask CAGI for written permission.

### 7. PR Newswire (prnewswire_releases)
- Checked on: 2026-10-29
- robots.txt: https://www.prnewswire.com/robots.txt -> 200, allowed for `*`
- Terms: https://www.prnewswire.com/terms-of-use/ -> "use any robot, spider, site search/retrieval application, or other manual or automatic device or process to access, search, download, retrieve" and a separate ban on scraping -> **forbids_automation**
- Feed/API: none for public use (paid distribution products exist)
- Public, logged-out: yes
- Test fetch: none beyond the homepage and terms page
- Status: **blocked** — reason: terms forbid scraping and robots. Route: a licensed feed, or take the same releases from each company's own newsroom.

### 8. Plant Services (plant_services_news)
- Checked on: 2026-10-29
- robots.txt: https://www.plantservices.com/robots.txt -> 200, allowed for `*`
- Terms: https://www.endeavorbusinessmedia.com/endeavor-terms (Endeavor Business Media, linked from the footer) -> "use robots, spiders, scripts, service, software or any manual or automatic device, tool, or process designed to data mine or scrape the Content" -> **forbids_automation**
- Feed/API: RSS exists (`__rss/website-scheduled-content.xml`), but the terms still apply to automated collection
- Public, logged-out: yes
- Test fetch: none beyond the homepage and terms page
- Status: **blocked** — reason: terms forbid automated collection even though a feed exists. Route: ask Endeavor for permission. (A first keyword pass over this page missed the clause because the page is very long; a second whole-page search found it.)

### 9. Plant Engineering (plant_engineering_news)
- Checked on: 2026-10-29
- robots.txt: https://www.plantengineering.com/robots.txt -> 200, `Crawl-delay: 10`, allowed for `*`
- Terms: not read (site blocked us first) -> unknown
- Feed/API: not checked
- Public, logged-out: could not confirm
- Test fetch: homepage returned **HTTP 403** to our identified agent. Not retried, no other agent tried
- Status: **unreachable** — reason: the site refuses our agent. Register status `needs_permission`: ask the publisher.

### 10. Ingersoll Rand (ingersoll_rand_news)
- Checked on: 2026-10-29
- robots.txt: https://www.irco.com/robots.txt -> **HTTP 429** (too many requests) on the first request
- Terms: not read -> unknown
- Feed/API: not checked
- Public, logged-out: could not confirm
- Test fetch: homepage also **HTTP 429** on the first request. Not retried
- Status: **unreachable** — reason: the site rate-limits or blocks our agent before any content. Register status `needs_permission`: ask Ingersoll Rand, or use a licensed feed.

### 11. Business Wire (businesswire_releases)
- Checked on: 2026-10-29
- robots.txt: https://www.businesswire.com/robots.txt -> **HTTP 403** (a 403 on robots.txt is treated as disallow-all)
- Terms: not read -> unknown
- Feed/API: not checked
- Public, logged-out: could not confirm
- Test fetch: homepage **HTTP 403**
- Status: **unreachable** — reason: refuses our agent. Register status `needs_permission`.

### 12. Atlas Copco Group press releases (atlas_copco_group_press) — reserve, not in register
- Checked on: 2026-10-29
- robots.txt: https://www.atlascopcogroup.com/robots.txt -> allowed for `*`; crawl-delay: 1 s
- Terms: https://www.atlascopcogroup.com/en/privacy ("Legal and Privacy Notices") -> no sentence on automated access -> ok
- Feed/API: none found. The press-release list page builds its list with scripts (no article links in the page HTML); only the 4 most recent releases are linked from the homepage
- Public, logged-out: yes
- Test fetch: pages 200
- Status: **working (limited)** — held in reserve: the group site is global, mostly financial releases, and only a few recent ones are reachable without scripts.

### 13. ELGi US (elgi_usa) — reserve, not in register
- Checked on: 2026-10-29
- robots.txt: https://www.elgi.com/robots.txt -> allowed for `*` (a 300 s crawl-delay applies to one other named bot only)
- Terms: no terms-of-use page found (privacy policy only) -> unknown
- Feed/API: https://www.elgi.com/us/feed/ (10 entries; mostly product pages, newest 28 Oct 2026, others 2024-2025)
- Public, logged-out: yes
- Test fetch: feed 200
- Status: **working (limited)** — held in reserve: the feed carries product pages, not news.

### 14. Quincy Compressor blog (quincy_compressor_blog)
- Checked on: 2026-10-29
- robots.txt: https://www.quincycompressor.com/robots.txt -> allowed for `*`; crawl-delay: none
- Terms: Website Terms of Use and Privacy Notice, Terms & Conditions and Legal Notice (https://www.quincycompressor.com/about-us/website-terms-of-use-and-privacy-notice/, /terms-conditions/, /about-us/legal-notice/) -> all three read in full (23,000 to 60,000 characters each); no sentence on scraping, robots or automated access -> ok
- Feed/API: https://www.quincycompressor.com/feed/ (10 entries with dates, newest 19 Oct 2026)
- Public, logged-out: yes
- Test fetch: feed 200; posts 200
- Status: **working**

### 15. Pumps & Systems (pumps_systems_news)
- Checked on: 2026-10-29
- robots.txt: https://www.pumpsandsystems.com/robots.txt -> allowed for `*`; crawl-delay: none
- Terms: "Terms of Use" link in the footer leads to https://www.pumpsandsystems.com/data-privacy/; with the Privacy Policy (https://www.pumpsandsystems.com/privacy-policy/) read in full -> no sentence on scraping, robots or automated access -> ok
- Feed/API: https://www.pumpsandsystems.com/feed/ (12 entries with dates, newest 27 Oct 2026). The compressors-only category feed is stale (newest Dec 2025), so the main feed is used
- Public, logged-out: yes
- Test fetch: feed 200; articles 200
- Status: **working** — caveat: most items are about pumps, not compressors

Also looked at and dropped before full vetting: FS-Elliott (feed carries product brochures, not news), Powerex (feed stale, newest Feb 2024), Kaishan USA (feed returned HTTP 403, not retried), ELGi US (its `/news/` page redirects to a resources page with no news list), and several trade-magazine feeds that returned HTTP 403 (IEN, Power Engineering, Chemical Engineering, Manufacturing.net; not retried).

## Findings for the meeting

- **Blocked by their own terms:** CAGI, PR Newswire, Plant Services (Endeavor). These need written permission or a licensed feed.
- **Refuse our agent without stating a ban (HTTP 403 / 429):** Plant Engineering, Ingersoll Rand, Business Wire. We did not retry or change our agent. These need a conversation with the owners (or Atlas Copco's own access).
- **Ingersoll Rand is Atlas Copco's largest US competitor and is not reachable;** worth raising with Atlas Copco: do they have a data licence or a preferred route?
- **Open for Atlas Copco Legal:** Kaeser's terms (`unknown`), and the whole list before go-live.


## Phase 2: automatic-vetter findings (2026-11-15, NOT yet hand-checked)

Produced by `atlas/scout/vet.py` through the Compliance Gate (same identified agent, at least 3 s between requests, metadata only). These are the code's verdicts, not the hand procedure above. Nothing here is in `config/sources.yaml` yet: a row is added only after a person has read the site's terms page and robots.txt and confirmed the verdict. "robots disallow" is the gate's verdict (an explicit rule, or HTTP 401/403 on robots.txt, which the gate treats as disallow-all).

**Passed every automatic rule (`usable`), to be hand-checked first**

| Site | Scope it adds | Terms | Feed | Newest item | Relevance sample | Trust |
|---|---|---|---|---|---|---|
| fs-elliott.com | US competitor, oil-free centrifugal | ok | RSS | 2026-11-05 | 0.9 | 95 |
| burckhardtcompression.com | gas and hydrogen compression | ok | RSS | 2026-11-03 | 0.1 | 85 |
| sundyne.com | hydrogen and process-gas compressors | ok | RSS | 2026-03-09 | 0.33 | 80 |
| powerexinc.com | US competitor (vacuum, scroll) | ok | RSS | 2024-02-28 (stale) | 0.1 | 70 |

**Refused by robots.txt (never fetched further):** canadianmanufacturing.com, plant.ca, mromagazine.com, automationmag.com, cme-mec.ca (all Canadian), tuthill.com, kaishanusa.com, fuelcellsworks.com. No usable Canadian English source has been found yet; Canada needs another route (government pages, company sites, or asking a publisher for permission).

**Unreachable for our agent (not retried or bypassed):** fscurtis.com and hankisonintl.com (TLS certificate does not match the host name), zeks.com (HTTP 429 on robots.txt), aerzenusa.com (robots.txt unreadable), howden.com (now redirects to chartindustries.com, another domain), buschusa.com and westport.com (redirect to another domain), rogers-machinery.com (homepage over the 3 MB limit).

**Needs review (terms `unknown` or no usable feed):** gascompressionmagazine.com (dated feed, newest 2026-11-12, no terms page found), fluidpowerjournal.com (dated feed, no terms page found), cganet.com (terms ok, listing without article links), compressortech2.com, compressedairchallenge.org, chfca.ca (feed has no entries), hydropac.com.

**Where the automatic verdict looks wrong**
- canada.ca (found as `natural-resources.canada.ca`) was marked `forbids_automation`. The quoted sentence is a CAPTCHA notice ("...an automated program (also known as a "robot" or a "bot")"), not a ban on our use. The terms scan is deliberately strict (see `decisions.md`); a person has to read that terms page before rejecting it.
- Domains under `canada.ca` are treated as one site (registered domain `canada.ca`); only `gc.ca` is in the two-label suffix list.


## Phase 2: hand-check of the scout's finds (2026-11-16)

Method: for each candidate the website terms were located through the site footer and read in full (whole page
searched for robot, spider, scrape, crawl, bot, harvest, data mining, automated, machine learning, artificial
intelligence). Robots.txt and the feed were read through the Compliance Gate, 3 s between requests.

| Site | Hand verdict | Evidence | In register |
|---|---|---|---|
| fs-elliott.com | ok | Terms of Use, about 19,700 characters, no automation clause; robots allow; RSS newest 5 Nov 2026 | `fs_elliott_news`, proposed |
| burckhardtcompression.com | ok | Terms of use page (about 2,700 characters), no automation clause; robots allow; RSS newest 3 Nov 2026 | `burckhardt_compression_news`, proposed, region CH |
| sundyne.com | **forbids automation** | Footer links to Honeywell's website terms: "use any robot, spider, or other automatic device, process, or means to access the Site for any purpose, including monitoring or copying any of the material on the Site"; also bans use for AI training | `sundyne_news`, blocked |
| powerexinc.com | unknown, not used | Only sales terms found, no website terms; newest feed item 28 Feb 2024 (stale) | no |
| mikropor.com | ok, not promoted | Legal notice and terms of use (about 4,600 characters) has no automation clause, but the server drops our connection about one time in three (RemoteProtocolError) | no (stays a scout candidate) |
| gascompressionmagazine.com, nwpump.com, sullivan-palatek.com | unknown, not used | Robots allow and a dated RSS feed exists, but the site shows no terms page at all (only a privacy policy). Needs the owner's written permission | no |
| Canadian English-language sources | none found | Every Canadian seed was refused by robots.txt (canadianmanufacturing.com, plant.ca, mromagazine.com, automationmag.com, cme-mec.ca) or forbids automation (canada.ca) | no |

**Where the automatic verdict was wrong, and the fix (`atlas/scout/vet.py`)**
- **Sundyne: said ok, actually forbidden.** It read Sundyne's purchase conditions instead of the website terms, which are Honeywell's. Fix: purchase, sales and supplier conditions never count as "terms ok"; a parent company's footer "Terms" link is followed (but not third-party platforms such as Google or Facebook).
- **Powerex: said ok, actually unknown.** Same cause (sales terms only).
- **Burckhardt: right answer, wrong page.** It read the sales terms; the website Terms of use is now read first.
- **Mikropor: briefly marked forbidden.** The first version of the fix followed a Google "Terms" link from a footer widget. Third-party platforms are now excluded.
- A redirect inside the host of a page we asked for (a parent's terms page) is now followed; a redirect to any other site is still refused.

The scout's earlier demo run (run 20261115T192521Z) had read 3 pages from sundyne.com before this fix. None reached the output (0 passed the filter), but the run should be repeated with the corrected vetter; see `docs/decisions.md`.


## Phase 2: search for a Canadian English-language source (2026-11-16)

Ten more Canadian seeds were run through the scout (Compliance Gate, 3 s between requests, at most 8 requests per site;
metadata only, nothing saved). Result: **no usable Canadian source.**

| Site | Verdict | Reason |
|---|---|---|
| theenergymix.com | needs review | Terms ok, robots allow, feed found (score 65), but the listing answered HTTP 304 so no dated item was read; content is climate and energy policy, weak fit for compressors |
| cer-rec.gc.ca, canada.ca, hydrogen-expo.com | needs review | Terms ok, robots allow, but no feed and no article links to read |
| cga.ca | rejected by rules | robots.txt disallows the feed or listing |
| albertainnovates.ca | rejected by rules | robots.txt disallows the homepage |
| canadianenergycentre.ca | not read | redirects to another host (refused) |
| canadianmetalworking.com | not read | HTTP 403 |
| pipelinenews.ca | not read | robots.txt could not be read |
| ballard.com | needs review | No terms page, no feed |

Together with the first round (canadianmanufacturing.com, plant.ca, mromagazine.com, automationmag.com, cme-mec.ca refused by
robots.txt; canada.ca forbids automation in a different section), 16 Canadian sites were tried. Canadian trade publishers
mostly block automated readers or publish no feed. **Finding:** Canada is in the default region scope, but no Canadian source
can be read without permission. See question 11 in `docs/questions_for_atlas_copco.md`.
