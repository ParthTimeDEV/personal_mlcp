from atlas.models import Item
from atlas.scout.stories import build_stories


def item(n, source="s1", company="Acme Compressors", product=None, event="product_launch",
         published="2026-10-01", title="Acme launches the AX-200 oil-free compressor", **kw) -> Item:
    base = dict(
        id=f"item{n:08d}", source_id=source, source_name=source, source_type="trade_news",
        source_url=f"https://{source}.example/{n}", licence_note="x", collected_at="2026-10-29T10:00:00Z",
        published_at=published, title=title, company=company, product=product, event_type=event,
        page_fingerprint=str(n) * 8,
    )
    base.update(kw)
    return Item(**base)


def test_same_story_across_three_sources():
    items = [
        item(1, "s1", published="2026-10-01"),
        item(2, "s2", published="2026-10-03", title="Acme launches AX-200 oil-free compressor line"),
        item(3, "s3", published="2026-10-05", title="Acme Compressors launches new AX-200 oil-free compressor"),
    ]
    out, clusters = build_stories(items)
    assert len(clusters) == 1
    (c,) = clusters
    assert sorted(c.source_ids) == ["s1", "s2", "s3"] and len(c.item_ids) == 3
    assert {i.story_id for i in out} == {c.story_id}
    assert c.first_published == "2026-10-01" and c.last_published == "2026-10-05"
    assert c.headline == items[0].title and c.company == "Acme Compressors"


def test_different_companies_are_never_merged():
    items = [item(1, company="Acme Compressors"), item(2, "s2", company="Borealis Air")]
    _, clusters = build_stories(items)
    assert len(clusters) == 2


def test_same_product_joins_even_with_different_events():
    items = [item(1, product="AX-200", event="product_launch", title="Alpha"),
             item(2, "s2", product="AX-200", event="award", title="Zeta something else", published="2026-10-04")]
    assert len(build_stories(items)[1]) == 1


def test_date_window_separates_items():
    items = [item(1, published="2026-10-01"), item(2, "s2", published="2026-10-20")]
    assert len(build_stories(items, window_days=10)[1]) == 2
    assert len(build_stories(items, window_days=30)[1]) == 1


def test_different_event_and_unrelated_title_do_not_merge():
    items = [item(1, event="acquisition", title="Acme acquires Delta Pumps"),
             item(2, "s2", event="product_launch", title="Acme launches new dryer series")]
    assert len(build_stories(items)[1]) == 2


def test_transitive_merge():
    items = [
        item(1, "s1", published="2026-10-01", title="Acme launches the AX-200 oil-free compressor"),
        item(2, "s2", published="2026-10-09", title="Acme launches the AX-200 oil-free compressor"),
        item(3, "s3", published="2026-10-17", title="Acme launches the AX-200 oil-free compressor"),
    ]  # 1-3 are 16 days apart (outside the window) but each neighbour is within it
    (cluster,) = build_stories(items)[1]
    assert len(cluster.item_ids) == 3


def test_undated_item_joins_only_on_same_product():
    undated_event = [item(1, published="2026-10-01"), item(2, "s2", published=None)]
    assert len(build_stories(undated_event)[1]) == 2
    undated_product = [item(1, product="AX-200", published="2026-10-01"),
                       item(2, "s2", product="AX-200", published=None)]
    (cluster,) = build_stories(undated_product)[1]
    assert cluster.first_published == "2026-10-01"


def test_item_without_company_is_a_single_story():
    out, clusters = build_stories([item(1, company=None), item(2, "s2", company=None)])
    assert len(clusters) == 2 and all(c.company is None for c in clusters)


def test_ids_are_stable_and_every_item_gets_one():
    items = [item(1), item(2, "s2", published="2026-10-02"), item(3, "s3", company="Borealis Air")]
    a, ca = build_stories(items)
    b, cb = build_stories(list(reversed(items)))
    assert {i.id: i.story_id for i in a} == {i.id: i.story_id for i in b}
    assert {c.story_id for c in ca} == {c.story_id for c in cb}
    assert all(i.story_id for i in a) and len(a[0].story_id) == 12


def test_product_is_never_invented():
    # one item names a product, the other does not: the story keeps the one product that exists
    (c,) = build_stories([item(1, product="AX-200"), item(2, "s2", product=None)])[1]
    assert c.product == "AX-200"
    # two different products: the story names neither rather than picking one
    (c,) = build_stories([item(1, product="AX-200", title="x"),
                          item(2, "s2", product="BX-9", title="x", published="2026-10-02")])[1]
    assert c.product is None


def test_multi_source_stories_come_first_and_fallback_counted():
    items = [
        item(1, "s1", company="Solo Co", published="2026-10-20"),
        item(2, "s1", company="Acme Compressors", published="2026-10-01"),
        item(3, "s2", company="Acme Compressors", published="2026-10-02", via_fallback=True, fallback_for="x"),
    ]
    _, clusters = build_stories(items)
    assert len(clusters[0].source_ids) == 2 and clusters[0].via_fallback_count == 1
    assert len(clusters[1].source_ids) == 1


def test_empty_input_and_inputs_are_not_mutated():
    assert build_stories([]) == ([], [])
    original = item(1)
    out, _ = build_stories([original])
    assert original.story_id is None and out[0].story_id
