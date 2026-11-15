"""The synthetic sample output that the frontend and the report are built against must stay valid."""
import json
from pathlib import Path

from atlas.models import OutputEnvelope

SAMPLE = Path(__file__).parent / "fixtures" / "sample_output.json"


def load() -> OutputEnvelope:
    return OutputEnvelope.model_validate(json.loads(SAMPLE.read_text(encoding="utf-8")))


def test_sample_validates_and_covers_every_phase_2_feature():
    env = load()
    assert 8 <= len(env.items) <= 10
    assert len(env.stories) >= 2 and any(len(s.source_ids) >= 2 for s in env.stories)
    assert any(i.via_fallback for i in env.items)
    assert any(s.kind == "fallback" for s in env.sources)
    assert any(s.kind == "discovered" for s in env.sources)
    assert any(s.status == "blocked" for s in env.sources)
    assert all(i.region and i.story_id for i in env.items)
    assert {i.event_type for i in env.items} >= {"product_launch", "acquisition", "event", "appointment"}
    assert any(i.event_type is None for i in env.items) and any(i.published_at is None for i in env.items)
    assert env.settings_used is not None


def test_sample_stories_are_consistent_with_items():
    env = load()
    ids = {i.id for i in env.items}
    assert all(set(s.item_ids) <= ids for s in env.stories)
    assert sum(len(s.item_ids) for s in env.stories) == len(env.items)
