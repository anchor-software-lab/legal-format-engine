"""Tests for the response cache."""

from __future__ import annotations

from pathlib import Path

from tools.eval.cache import (
    CacheKey,
    CachedResponse,
    NullCache,
    ResponseCache,
)


def _cached() -> CachedResponse:
    return CachedResponse(
        raw_output={"canonical": "x"},
        parsed_output={"canonical": "x", "confidence": 0.9},
        input_tokens=10,
        output_tokens=5,
        cost_cents=2,
        latency_ms=750,
    )


def test_cache_key_is_deterministic():
    a = CacheKey("p@1", "m", {"x": 1, "y": 2})
    b = CacheKey("p@1", "m", {"y": 2, "x": 1})  # different dict order
    assert a.digest() == b.digest()


def test_cache_round_trip(tmp_path: Path):
    cache = ResponseCache(tmp_path)
    key = CacheKey("p@1", "m", {"raw": "X"})
    assert cache.get(key) is None
    cache.put(key, _cached())
    got = cache.get(key)
    assert got is not None
    assert got.parsed_output == {"canonical": "x", "confidence": 0.9}


def test_cache_size_and_clear(tmp_path: Path):
    cache = ResponseCache(tmp_path)
    for i in range(3):
        cache.put(CacheKey("p@1", "m", {"i": i}), _cached())
    assert cache.size() == 3
    n = cache.clear()
    assert n == 3
    assert cache.size() == 0


def test_null_cache_misses_silently(tmp_path: Path):
    cache = NullCache()
    cache.put(CacheKey("p", "m", {"x": 1}), _cached())
    assert cache.get(CacheKey("p", "m", {"x": 1})) is None
    assert cache.size() == 0


def test_cache_directories_fan_out(tmp_path: Path):
    cache = ResponseCache(tmp_path)
    cache.put(CacheKey("p", "m", {"x": 1}), _cached())
    # First-two-chars subdirectory exists.
    dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
    assert dirs, "no fan-out subdirectory created"
    assert len(dirs[0].name) == 2
