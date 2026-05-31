"""Tests for triage checkpoint state."""

from __future__ import annotations

from pathlib import Path

from tools.corpus.state import TriageState, load_state, save_state, state_path_for


def _state(**overrides) -> TriageState:
    base = TriageState(
        session_id="s1",
        candidates_path="cands.jsonl",
        output_path="out.jsonl",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_save_and_load_round_trip(tmp_path: Path):
    s = _state(next_index=7, accepted=3, rejected=1)
    save_state(tmp_path, s)
    loaded = load_state(tmp_path)
    assert loaded == s


def test_load_returns_none_when_no_state_file(tmp_path: Path):
    assert load_state(tmp_path) is None


def test_record_advances_counters():
    s = _state()
    s.record("accept")
    s.record("accept")
    s.record("edit")
    s.record("reject")
    s.record("skip")
    assert s.accepted == 3  # accept x2 + edit
    assert s.edited == 1
    assert s.rejected == 1
    assert s.skipped == 1
    assert s.next_index == 5


def test_progress_string_includes_counts():
    s = _state(next_index=10, accepted=5, rejected=2, skipped=2, edited=1)
    p = s.progress(total=50)
    assert "[10/50]" in p
    assert "accepted=5" in p
    assert "rejected=2" in p
    assert "skipped=2" in p


def test_state_path_for_locates_file(tmp_path: Path):
    assert state_path_for(tmp_path) == tmp_path / "state.json"


def test_save_is_atomic(tmp_path: Path):
    """Confirm that no `.tmp-*` leftovers stick around after save."""
    save_state(tmp_path, _state(next_index=1))
    leftovers = list(tmp_path.glob(".tmp-*"))
    assert leftovers == []
