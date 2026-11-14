# Keyword Suggestions for Industrial Compressor Relevance Filter

**Author:** Parth (Quality Assurance & Domain Analyst)  
**Target:** Suggestions for review and selective merge by Nikhil into `config/keywords.yaml`  
**Status:** Proposal ready for maintainer review (Do NOT edit `config/keywords.yaml` directly)  

Terms already present in `config/keywords.yaml` are intentionally omitted from the proposed lists below. Matching is case-insensitive, whole word or whole phrase.

---

## 1. Proposed Additions: `compressor`

The following terms identify specific compressor architectures, core compression components, drive and efficiency technologies, air treatment equipment, and formal industry standards.

### A. Compressor Types & Architectures
- `oil-injected` — Primary industry designation for lubricated rotary screw compressors (the largest industrial volume category).
- `oil-flooded` — Alternative engineering term for oil-injected screw compressors; frequent in technical announcements.
- `two-stage` — Dual-stage compression yields 10–15% energy savings over single-stage units; key technology indicator.
- `two-stage compression` — Explicit phrase used in high-efficiency product launch releases.
- `booster compressor` — Specialized secondary compressor elevating standard plant air (100–150 PSI) to high pressures (up to 500–6000 PSI).
- `rotary vane` — Alternative positive displacement technology competing directly with rotary screw in industrial shops.
- `water-injected` — Oil-free screw variant using water as sealing and cooling fluid; high-value niche technology.

### B. Drive, Motor & Efficiency Technologies
- `permanent magnet motor` — High-efficiency motor technology widely adopted in modern VSD compressors.
- `IE4` — Super Premium Efficiency motor class mandated or promoted in new European and US energy regulations.
- `IE5` — Ultra Premium Efficiency class emerging in next-generation compressor drives.
- `variable frequency drive` — Synonym for variable speed drive (VSD); commonly used in electrical and trade publications.
- `VFD` — Widely used electrical engineering acronym for Variable Frequency Drive.
- `heat recovery` — Energy recovery modules capturing up to 90% of compressor heat for water/facility heating.
- `energy recovery` — Alternative term for thermal capture systems integrated into compressor packages.

### C. Air Treatment & System Auxiliaries
- `aftercooler` — Essential heat exchanger immediately downstream of the compressor to condense moisture.
- `desiccant dryer` — Regenerative adsorption dryer achieving extreme dew points (-40°F / -70°F) for critical industries.
- `refrigerated dryer` — Standard industrial air dryer condensing moisture via refrigeration cycle (dew points ~38°F).
- `membrane dryer` — Specialized hollow-fiber air treatment technology used in point-of-use or rail/transit applications.
- `nitrogen generator` — On-site gas generation systems powered by compressed air; core product line for compressor OEMs.
- `compressed air system` — Whole-facility system context; common in trade engineering articles.
- `air leak` — Primary source of compressed air energy waste (20–30% of plant capacity); key topic in audits.
- `leak detection` — Ultrasonic testing and audit programs frequently highlighted in trade press.
- `dew point` — Critical specification measuring compressed air dryness and air treatment performance.

### D. Standards, Ratings & Technical Units
- `ISO 8573` — Foundational international standard for compressed air quality (purity classes for oil, water, particles).
- `ISO 8573-1` — Part 1 of the standard defining purity classes (e.g., Class 0).
- `Class 0` — Highest purity rating under ISO 8573-1, certifying 100% oil-free air; key competitive selling point.
- `ISO 1217` — International standard governing acceptance and displacement performance testing of displacement compressors.
- `CAGI data sheet` — Standardized performance verification sheet created by the Compressed Air and Gas Institute.
- `SCFM` — Standard Cubic Feet per Minute; standard US measurement of air flow adjusted for temperature and pressure.
- `psig` — Pounds per square inch gauge; precise engineering pressure specification in US literature.

---

## 2. Proposed Additions: `industrial`

In the pipeline architecture, `industrial_hint` is a metadata signal rather than an exclusionary filter gate. Adding specific manufacturing contexts improves signal clarity.

### A. Facility & Operational Context
- `facility` — Plant, service center, or headquarters expansions and commissioning news.
- `production line` — Factory-floor automation and pneumatic tool integration.
- `manufacturing plant` — High-confidence industrial production indicator.
- `compressor room` — Specific physical installation site within manufacturing facilities.
- `utility room` — Centralized plant services infrastructure.

### B. High-Demand Compressor End-User Industries
- `heavy industry` — Core customer segment for large centrifugal and oil-free units (steel, chemicals).
- `oil and gas` — Dominant industrial user of high-pressure and gas compression packages.
- `food and beverage` — High-growth customer segment driving mandatory oil-free / Class 0 compressor demand.
- `pharmaceutical` — Strictly regulated clean-manufacturing sector requiring validated dry, oil-free compressed air.
- `semiconductor` — High-tech fabrication requiring ultra-clean, continuous compressed air and nitrogen generation.
- `automotive assembly` — High-volume pneumatic tool and robotic paint application sector.

---

## 3. Proposed Additions: `us_locations`

The following states and cities represent major manufacturing hubs, corporate headquarters, and regional assembly centers for compressor OEMs and tier-1 distributors in the United States.

### A. Additional States
- `Virginia` — US Headquarters for Kaeser Compressors.
- `Kentucky` — Dense manufacturing corridor with high industrial air demand.
- `Tennessee` — High manufacturing growth state with automotive and appliance assembly.
- `Minnesota` — Headquarters and manufacturing facilities for numerous pneumatic and filtration brands.
- `Missouri` — Midwestern industrial manufacturing and distribution center.
- `Oklahoma` — Center for oil, gas, and energy compression fabrication.
- `Louisiana` — Heavy chemical processing and refinery compression installations.

### B. Specific Cities & Compressor Manufacturing Centers
- `Rock Hill` (SC) — Atlas Copco Compressors North American corporate headquarters and production facilities.
- `Fredericksburg` (VA) — Kaeser Compressors USA national headquarters and assembly facility.
- `Michigan City` (IN) — Sullair (Hitachi Global Air Power) national headquarters and 500,000+ sq ft manufacturing plant.
- `Bay Minette` (AL) — Quincy Compressor's primary US manufacturing plant and foundry.
- `Quincy` (IL) — Founding location, technical center, and reciprocating compressor manufacturing for Quincy Compressor.
- `Davidson` (NC) — Corporate headquarters campus for Ingersoll Rand.
- `Michigan City` (IN) — Sullair US major facility (note: already listed in seed, retained for verification).

---

## 4. Evaluation of False-Positive Risks & Ambiguous Terms

Certain candidate keywords carry significant ambiguity because they have homonyms or common meanings outside industrial manufacturing. The table below analyzes these terms and provides concrete mitigation advice.

| Ambiguous Term | Non-Industrial / Confounding Meanings | Risk Severity | Recommended Mitigation / Treatment |
|---|---|---|---|
| `plant` | Living botanical organism; verb "to plant". Already in `config/keywords.yaml`. | Medium | Keep in `industrial` because "plant" is ubiquitous in "power plant", "manufacturing plant", "cement plant". Do not promote to exclusionary gate. |
| `process` | Generic noun ("legal process", "interview process", "sales process"). | High | Recommend **removing** or refining `process` in `config/keywords.yaml` to `process air` or `industrial process`. In isolation, `process` triggers false hints in corporate HR/legal news. |
| `blower` | Leaf blowers, snow blowers, residential hair dryers, automotive superchargers. | High | Do **not** add bare `blower` to `compressor`. If needed, use compound phrases: `industrial blower`, `rotary lobe blower`, or `aeration blower`. |
| `booster` | Vaccine booster shots, rocket booster stages, cellular signal boosters, child car seats. | High | Do **not** add bare `booster`. Use only `booster compressor` or `pressure booster`. |
| `mining` | Cryptocurrency mining, data mining, process mining in IT. | Medium | Do not use bare `mining` as a compressor keyword. Safe to use in `industrial` as a user sector flag, but exclude phrases containing `data mining` or `crypto`. |
| `Georgia` | Sovereign nation in the Caucasus region. | Low | Retain in `us_locations`, but consider checking for US state context if international trade sources are introduced. |
| `Charlotte`, `Houston`, `Davidson` | Common first names and family surnames. | Medium | Maintain case-sensitive or capitalised whole-word matching to avoid matching arbitrary text occurrences. |
| `Washington` | First president, surnames, federal capital shorthand ("Washington announced..."). | High | Exclude bare `Washington` unless qualified as `Washington State` or `WA`. |
| `American` / `America` | Corporate legal titles ("American Airlines", "Bank of America") unrelated to local operational footprint. | Medium | Retain in `us_locations` for now, but note that multinational company names may trigger false US flags. |
| `oil-free` | Skincare cosmetics, food cooking recipes ("oil-free salad dressing"). | Low-Medium | In compressor trade news, `oil-free` is 99% domain-specific. Safe in `compressor`, especially when paired with equipment context. |
| `compressor` | Audio signal processors (music production plugins), domestic refrigerators, automotive AC units. | Low | In our vetted trade news sources, false audio matches are virtually non-existent. The 4-check filter correctly isolates domain context. |

---

## 5. Structured Recommendations for Nikhil (Maintainer Merge Guide)

To expedite Nikhil's review and update of `config/keywords.yaml`, the table below categorizes the priority recommendations:

| Keyword / Phrase | Recommended Category | Action | Technical Justification |
|---|---|---|---|
| `oil-injected` | `compressor` | **Merge** | Standard terminology for lubricated rotary screw compressors. Zero risk of false positives. |
| `oil-flooded` | `compressor` | **Merge** | Technical synonym for oil-injected screw compressors. High industry relevance. |
| `two-stage` | `compressor` | **Merge** | Industry standard efficiency metric for industrial air ends. |
| `permanent magnet motor` | `compressor` | **Merge** | Key technology differentiator in modern variable speed compressors. |
| `IE4` | `compressor` | **Merge** | Motor efficiency classification directly tied to premium compressor product launches. |
| `desiccant dryer` | `compressor` | **Merge** | Essential compressed air treatment equipment; distinguishes industrial systems. |
| `refrigerated dryer` | `compressor` | **Merge** | Most common industrial air dryer type. |
| `heat recovery` | `compressor` | **Merge** | Major sustainability and energy savings focus for industrial compressor installations. |
| `ISO 8573` | `compressor` | **Merge** | The global standard for compressed air quality. Zero ambiguity. |
| `Class 0` | `compressor` | **Merge** | Commercial hallmark of certified oil-free compressors. |
| `ISO 1217` | `compressor` | **Merge** | Displacement compressor performance testing standard. |
| `SCFM` | `compressor` | **Merge** | Universal US flow metric for commercial and industrial compressors. |
| `booster compressor` | `compressor` | **Merge as Phrase** | Captures high-pressure auxiliary systems without false matches from bare `booster`. |
| `process` | `industrial` | **Refine / Replace** | Recommend replacing bare `process` with `process air` or `manufacturing process` to avoid HR/legal noise. |
| `facility` | `industrial` | **Merge** | Standard indicator of manufacturing plant expansions and capital investments. |
| `Virginia` | `us_locations` | **Merge** | Location of Kaeser Compressors US operations. |
| `Fredericksburg` | `us_locations` | **Merge** | City headquarters of Kaeser Compressors USA. |
| `Quincy` | `us_locations` | **Merge** | Historic founding city and manufacturing base for Quincy Compressor in Illinois. |
