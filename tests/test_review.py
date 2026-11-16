import pytest

from atlas import review


@pytest.fixture
def volume(monkeypatch):
    files: dict = {}
    monkeypatch.setattr(review.storage, "read_json_or_none", lambda p: files.get(p))
    monkeypatch.setattr(review.storage, "write_json", lambda p, o: files.__setitem__(p, o))
    return files


def test_fact_decisions_round_trip_and_default_empty(volume):
    assert review.load_fact_decisions() == {}
    review.save_fact_decisions({"a": "approved", "b": "denied"})
    assert review.load_fact_decisions() == {"a": "approved", "b": "denied"}


def test_invalid_decision_value_is_refused(volume):
    with pytest.raises(ValueError):
        review.save_fact_decisions({"a": "maybe"})
    assert volume == {}


def test_source_confirmations_keep_only_confirmed(volume):
    review.save_source_confirmations({"s1": "confirmed", "s2": "pending"})
    assert review.load_source_confirmations() == {"s1": "confirmed"}


def test_corrupt_file_raises(volume):
    volume[review.FACT_DECISIONS] = ["not", "a", "dict"]
    with pytest.raises(ValueError):
        review.load_fact_decisions()


def test_without_denied_keeps_approved_and_undecided():
    class I:
        def __init__(self, i): self.id = i
    items = [I("a"), I("b"), I("c")]
    kept = review.without_denied(items, {"a": "denied", "b": "approved"})
    assert [i.id for i in kept] == ["b", "c"]
