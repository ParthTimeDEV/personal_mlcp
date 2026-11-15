"""Generates tests/fixtures/sample_output.json: a SYNTHETIC OutputEnvelope (invented companies and text).

Parth builds the frontend and Sachi the report against it before any real run exists. Regenerate with:
    python tests/fixtures/make_sample_output.py
Everything here is invented; nothing was scraped.
"""
import json
from pathlib import Path

from atlas.models import (
    Item, OutputEnvelope, Scope, ScoutSettings, SourceSummary, WatchEntry, FilterResult, make_item_id,
)
from atlas.scout.stories import build_stories

OUT = Path(__file__).with_name("sample_output.json")
PASSED = FilterResult(compressor_related=True, north_america=True, credible_source=True, recent=True, passed=True)

SOURCES = {
    "demo_trade_news": ("Demo Compressed Air Weekly", "trade_news", "https://demo-trade.example/news"),
    "demo_maker_news": ("Borealis Air Newsroom", "competitor", "https://borealis-air.example/news"),
    "demo_energy_gov": ("Demo Energy Department", "government", "https://demo-energy.example/press"),
    "disc_0a1b2c3d4e5f": ("Northern Vacuum Review", "trade_news", "https://northern-vacuum.example/news"),
}


def item(source_id, slug, title, published, company, event, facts, *, technology="rotary screw compressors",
         product=None, region="US", label="claim", via_fallback=False, fallback_for=None, watch=(),
         industrial=True) -> Item:
    name, source_type, base = SOURCES[source_id]
    url = f"{base.rsplit('/', 1)[0]}/{slug}"
    return Item(
        id=make_item_id(url), source_id=source_id, source_name=name, source_type=source_type, source_url=url,
        licence_note="Public web page; facts and links only", collected_at="2026-10-29T10:15:00Z",
        published_at=published, title=title, company=company, product=product, technology=technology,
        key_facts=facts, label=label, filter=PASSED, page_fingerprint=make_item_id(url) * 5 + "0000",
        personal_data_removed=True, matched_keywords=["compressor"], mentions_us_location=region == "US",
        industrial_hint=industrial, region=region, event_type=event, via_fallback=via_fallback,
        fallback_for=fallback_for, watch_matches=list(watch),
    )


ITEMS = [
    item("demo_trade_news", "borealis-bx200", "Borealis Air launches BX-200 oil-free compressor", "2026-10-12",
         "Borealis Air", "product_launch", ["The BX-200 delivers 250 kW at 8 bar.", "Shipping starts in January."],
         product="BX-200", label="claim"),
    item("demo_maker_news", "bx200-release", "Introducing the BX-200: oil-free compression for food plants",
         "2026-10-13", "Borealis Air", "product_launch",
         ["The BX-200 is certified to ISO 8573-1 Class 0."], product="BX-200", label="fact"),
    item("demo_energy_gov", "efficiency-rule", "Department proposes new compressor efficiency standard",
         "2026-10-08", "Demo Energy Department", "regulation_standard",
         ["The proposed rule covers rotary compressors from 15 to 200 hp."], label="fact", technology=None),
    item("demo_trade_news", "cedar-acquires-delta", "Cedar Pumps acquires Delta Vacuum", "2026-09-30",
         "Cedar Pumps", "acquisition", ["The deal adds dry screw vacuum pumps to Cedar's range."],
         technology="vacuum pumps"),
    item("disc_0a1b2c3d4e5f", "cedar-delta-deal", "Cedar Pumps buys Delta Vacuum in all-cash deal", "2026-10-01",
         "Cedar Pumps", "acquisition", ["Delta Vacuum has 120 employees in Ohio."], technology="vacuum pumps"),
    item("demo_trade_news", "harbor-plant", "Harbor Blowers opens second plant in Ontario", "2026-10-15",
         "Harbor Blowers", "investment_expansion", ["The 40,000 sq ft plant is in Hamilton, Ontario."],
         technology="blowers", region="CA", industrial=False),
    item("demo_trade_news", "granite-webinar", "Granite Gas hosts hydrogen compression webinar", "2026-10-20",
         "Granite Gas", "event", ["The webinar is on 12 November."], technology="hydrogen compression"),
    item("demo_trade_news", "summit-ir-plant", "Summit Compressors opens a new plant in Texas", "2026-10-22",
         "Summit Compressors", "investment_expansion",
         ["Summit Compressors said the plant adds 80 jobs."], via_fallback=True,
         fallback_for="demo_summit_news", watch=["Summit Compressors"]),
    item("demo_trade_news", "pine-dryer", "Pine Air names new head of dryer business", "2026-10-02",
         "Pine Air", "appointment", ["The new head joins from a rival dryer maker."], technology="air treatment"),
    item("demo_energy_gov", "no-date-note", "Demo Energy Department posts compressed-air guide", None,
         "Demo Energy Department", None, ["The guide lists 12 efficiency measures."], label="fact", technology=None),
]


def main() -> None:
    items, stories = build_stories(ITEMS)
    sources = [
        SourceSummary(source_id="demo_trade_news", name=SOURCES["demo_trade_news"][0], status="working",
                      items_collected=12, items_passed=6),
        SourceSummary(source_id="demo_maker_news", name=SOURCES["demo_maker_news"][0], status="working",
                      items_collected=5, items_passed=1),
        SourceSummary(source_id="demo_energy_gov", name=SOURCES["demo_energy_gov"][0], status="working",
                      items_collected=4, items_passed=2),
        SourceSummary(source_id="disc_0a1b2c3d4e5f", name=SOURCES["disc_0a1b2c3d4e5f"][0], status="working",
                      items_collected=6, items_passed=1, kind="discovered",
                      note="discovered by the scout, trust score 82; not approved by Atlas Copco"),
        SourceSummary(source_id="demo_summit_news", name="Summit Compressors Newsroom", status="blocked",
                      note="refused by compliance gate: terms_forbid_automation, vetting_blocked"),
        SourceSummary(source_id="fallback_demo_summit_news", name="Coverage of Summit Compressors Newsroom (switched)",
                      status="working", items_collected=1, items_passed=1, kind="fallback",
                      fallback_for="demo_summit_news",
                      note="switched because refused by the compliance gate; followed Summit Compressors; "
                           "1 item(s) from 1 other source(s): Demo Compressed Air Weekly"),
    ]
    envelope = OutputEnvelope(
        run_id="20261029T101500Z", generated_at="2026-10-29T10:30:00Z",
        scope=Scope(technology="industrial compressors", region="US+CA"), sources=sources, items=items,
        stories=stories,
        settings_used=ScoutSettings(regions=["US", "CA"], watchlist=[WatchEntry(name="Summit Compressors")]),
        candidates_considered=4,
    )
    OUT.write_text(json.dumps(envelope.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(items)} items, {len(stories)} stories)")


if __name__ == "__main__":
    main()
