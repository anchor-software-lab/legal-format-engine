"""Bluebook signal detection and classification."""

from __future__ import annotations

import pytest

from legal_citations.bluebook.signal import (
    SignalKind,
    classify_signal_text,
    find_signal_before,
    order_index,
)


def test_classify_canonical_signals():
    assert classify_signal_text("see") is SignalKind.SUPPORTING
    assert classify_signal_text("See") is SignalKind.SUPPORTING
    assert classify_signal_text("see also") is SignalKind.SUPPORTING
    assert classify_signal_text("e.g.,") is SignalKind.SUPPORTING
    assert classify_signal_text("but see") is SignalKind.CONTRADICTING
    assert classify_signal_text("but cf.") is SignalKind.CONTRADICTING
    assert classify_signal_text("see generally") is SignalKind.BACKGROUND
    assert classify_signal_text("compare") is SignalKind.COMPARISON


def test_classify_rejects_unknown_signals():
    assert classify_signal_text("see, also,") is None
    assert classify_signal_text("see e.g.") is None  # missing comma
    assert classify_signal_text("cf,") is None  # comma instead of period
    assert classify_signal_text("") is None
    assert classify_signal_text("but") is None


def test_signal_family_order_matches_bluebook_rule_1_3():
    assert order_index(SignalKind.SUPPORTING) < order_index(SignalKind.COMPARISON)
    assert order_index(SignalKind.COMPARISON) < order_index(SignalKind.CONTRADICTING)
    assert order_index(SignalKind.CONTRADICTING) < order_index(SignalKind.BACKGROUND)


def test_find_signal_before_finds_simple_see():
    text = "The court reviewed the matter. See Tews v. NHI, 2010 WI 137."
    citation_start = text.index("Tews")
    result = find_signal_before(text, citation_start)
    assert result is not None
    signal, kind, start = result
    assert signal.lower() == "see"
    assert kind is SignalKind.SUPPORTING
    assert text[start : start + len(signal)] == signal


def test_find_signal_before_finds_see_also():
    text = "Foo. See also Brown v. Holiday, 2008 WI 49."
    citation_start = text.index("Brown")
    result = find_signal_before(text, citation_start)
    assert result is not None
    signal, kind, _ = result
    assert signal.lower() == "see also"
    assert kind is SignalKind.SUPPORTING


def test_find_signal_before_finds_but_see():
    text = "Foo. But see Smith v. Jones, 100 U.S. 1 (1990)."
    citation_start = text.index("Smith")
    result = find_signal_before(text, citation_start)
    assert result is not None
    signal, kind, _ = result
    assert signal.lower() == "but see"
    assert kind is SignalKind.CONTRADICTING


def test_find_signal_before_returns_none_when_no_signal():
    text = "The plaintiff filed an action. Tews v. NHI, 2010 WI 137."
    citation_start = text.index("Tews")
    assert find_signal_before(text, citation_start) is None


def test_find_signal_does_not_match_across_sentence_boundary():
    # "see" appears far back, after a period — must not match.
    text = "I see the issue. The court ruled differently. Tews v. NHI, 2010 WI 137."
    citation_start = text.index("Tews")
    assert find_signal_before(text, citation_start) is None


def test_find_signal_does_not_match_inside_word():
    # "foresee" ends with "see" but isn't the signal.
    text = "We foresee Tews v. NHI, 2010 WI 137."
    citation_start = text.index("Tews")
    assert find_signal_before(text, citation_start) is None


def test_find_signal_handles_intervening_comma():
    text = "Foo. See, Tews v. NHI, 2010 WI 137."
    citation_start = text.index("Tews")
    result = find_signal_before(text, citation_start)
    assert result is not None
    assert result[0].lower() == "see"
