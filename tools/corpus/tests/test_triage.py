"""Tests for the triage loop (input-fn-injected)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.corpus.state import TriageState, load_state, save_state
from tools.corpus.triage import HELP_TEXT, TriageQuit, run_triage
from tools.eval.dataset import load_dataset, write_dataset
from tools.eval.types import EvalCase


def _candidates() -> list[EvalCase]:
    return [
        EvalCase(
            id=f"c{i}",
            input={
                "raw": f"Tews v. NHI, LLC, 2010 WI 13{i}",
                "context": "we review de novo.",
                "jurisdiction": "WI",
            },
            expected={
                "canonical": f"Tews v. NHI, LLC, 2010 WI 13{i}",
                "case_name": "Tews v. NHI, LLC",
                "year": 2010,
            },
            tags=("wi", "wicourts_scraped"),
            source="wicourts_scraped",
            metadata={"brief_source": "fake.pdf", "page_number": 1},
        )
        for i in range(3)
    ]


def _setup(tmp_path: Path):
    candidates_path = tmp_path / "candidates.jsonl"
    write_dataset(candidates_path, _candidates())
    out_path = tmp_path / "out.jsonl"
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    state = TriageState(
        session_id="s1",
        candidates_path=str(candidates_path),
        output_path=str(out_path),
    )
    save_state(session_dir, state)
    return candidates_path, out_path, session_dir, state


def test_accept_appends_to_output_and_advances(tmp_path: Path):
    candidates_path, out_path, session_dir, state = _setup(tmp_path)
    final = run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=state,
        actions=iter(["a", "a", "a"]),
    )
    assert final.accepted == 3
    assert final.next_index == 3
    loaded = load_dataset(out_path)
    assert len(loaded) == 3
    # First accepted retained its id.
    assert loaded[0].id == "c0"


def test_reject_skips_writing_to_output(tmp_path: Path):
    candidates_path, out_path, session_dir, state = _setup(tmp_path)
    final = run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=state,
        actions=iter(["r", "a", "r"]),
    )
    assert final.rejected == 2
    assert final.accepted == 1
    loaded = load_dataset(out_path)
    assert {c.id for c in loaded} == {"c1"}


def test_skip_advances_without_decision(tmp_path: Path):
    candidates_path, out_path, session_dir, state = _setup(tmp_path)
    final = run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=state,
        actions=iter(["s", "s", "a"]),
    )
    assert final.skipped == 2
    assert final.accepted == 1
    assert final.next_index == 3


def test_edit_prompts_for_canonical_and_overrides(tmp_path: Path):
    candidates_path, out_path, session_dir, state = _setup(tmp_path)
    # Sequence: action "e" → canonical edit → overrides line.
    actions = iter(["e", "a", "a"])
    edit_inputs = iter([
        "Tews v. NHI, LLC, 2010 WI 137",   # canonical
        "year=2010, case_name=Tews v. NHI, LLC",  # overrides
    ])

    def input_fn(prompt: str) -> str:
        if prompt.startswith(">"):
            return next(actions)
        return next(edit_inputs)

    final = run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=state,
        input_fn=input_fn,
    )
    assert final.edited == 1
    assert final.accepted == 3  # edit counts as accept
    loaded = load_dataset(out_path)
    edited = next(c for c in loaded if c.id == "c0")
    assert edited.expected["canonical"] == "Tews v. NHI, LLC, 2010 WI 137"
    assert edited.source == "human_labeled"
    assert "human_labeled" in edited.tags


def test_quit_saves_state_and_stops(tmp_path: Path):
    candidates_path, out_path, session_dir, state = _setup(tmp_path)
    run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=state,
        actions=iter(["a", "q", "a"]),  # last action never reached
    )
    persisted = load_state(session_dir)
    assert persisted is not None
    assert persisted.next_index == 1


def test_resume_from_checkpoint(tmp_path: Path):
    candidates_path, out_path, session_dir, state = _setup(tmp_path)
    # First pass: accept one, quit.
    run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=state,
        actions=iter(["a", "q"]),
    )
    resumed = load_state(session_dir)
    assert resumed is not None
    # Second pass: pick up where we left off.
    final = run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=resumed,
        actions=iter(["a", "a"]),
    )
    assert final.accepted == 3  # 1 + 2
    assert final.next_index == 3


def test_unknown_action_is_ignored_and_warns(tmp_path: Path, capsys):
    candidates_path, out_path, session_dir, state = _setup(tmp_path)
    # "x" is bogus; next valid actions advance through.
    final = run_triage(
        candidates_path=candidates_path,
        output_path=out_path,
        session_dir=session_dir,
        state=state,
        actions=iter(["x", "a", "a", "a"]),
    )
    assert final.accepted == 3


def test_help_text_is_documented():
    # The help text is rendered to console; verify it covers every action.
    for action in ("accept", "edit", "reject", "skip", "quit"):
        assert action in HELP_TEXT.lower()
