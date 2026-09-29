import pytest
from memory.schemas import MemoryStats
from memory.prior import compute_memory_prior


def test_prior_insufficient_precedents():
    # Only 2 precedents, below default min_precedents=3
    stats = MemoryStats(zone="Zone 02", cause_tags=["glare"], approved=0, overrides=2)
    res = compute_memory_prior(stats, raw_corr=0.60, raw_skep=0.20, min_precedents=3)
    assert not res.applied
    assert res.delta == 0.0
    assert "minimum required" in res.reason


def test_prior_mixed_ratio_no_adjustment():
    # 3 overrides and 2 approvals = 5 total, but 3/5 = 60% < 75%
    stats = MemoryStats(zone="Zone 02", cause_tags=["glare"], approved=2, overrides=3)
    res = compute_memory_prior(stats, raw_corr=0.60, raw_skep=0.20, min_precedents=3)
    assert not res.applied
    assert "< 75% threshold" in res.reason


def test_prior_false_dominant_adjustment():
    # 5 overrides, 0 approvals => 100% false alarms, count=5
    # delta = min(0.25, 0.05 * 5) = 0.25
    # corr -= delta / 2 = -0.12 or -0.13
    # skep += delta = +0.25
    stats = MemoryStats(zone="Zone 02", cause_tags=["glare"], approved=0, overrides=5)
    res = compute_memory_prior(stats, raw_corr=0.60, raw_skep=0.20, min_precedents=3, max_adjust=0.25)
    assert res.applied
    assert res.dominant == "false_alarm"
    assert res.dominant_count == 5
    assert res.delta == 0.25
    assert res.skep_delta == 0.25
    assert res.corr_delta == -0.12 or res.corr_delta == -0.13
    assert res.post_memory_scores["skep"] == 0.45
    assert res.post_memory_scores["corr"] in (0.47, 0.48)
    assert res.post_memory_scores["fused"] < 0.10


def test_prior_real_dominant_adjustment():
    # 4 approvals, 0 overrides => 100% real collisions
    # delta = min(0.25, 0.05 * 4) = 0.20
    # corr += delta / 2 = +0.10
    # skep -= delta = -0.20
    stats = MemoryStats(zone="Zone 04", cause_tags=["collision"], approved=4, overrides=0)
    res = compute_memory_prior(stats, raw_corr=0.70, raw_skep=0.30, min_precedents=3, max_adjust=0.25)
    assert res.applied
    assert res.dominant == "real_collision"
    assert res.dominant_count == 4
    assert res.delta == 0.20
    assert res.corr_delta == 0.10
    assert res.skep_delta == -0.20
    assert res.post_memory_scores["corr"] == 0.80
    assert res.post_memory_scores["skep"] == 0.10
    assert res.post_memory_scores["fused"] == 0.70


def test_safety_asymmetry_clear_cut_collision():
    # Crucial safety rule: Even if 10 false alarms exist in memory,
    # a clear-cut high-confidence collision (raw_corr >= 0.85) can NEVER be suppressed!
    stats = MemoryStats(zone="Zone 02", cause_tags=["glare"], approved=0, overrides=10)
    res = compute_memory_prior(stats, raw_corr=0.88, raw_skep=0.10, min_precedents=3)
    assert not res.applied
    assert "Safety guard" in res.reason
    assert res.post_memory_scores["corr"] == 0.88
    assert res.post_memory_scores["skep"] == 0.10


def test_prior_memory_disabled():
    stats = MemoryStats(zone="Zone 02", cause_tags=["glare"], approved=0, overrides=5)
    res = compute_memory_prior(stats, raw_corr=0.60, raw_skep=0.20, memory_enabled=False)
    assert not res.applied
    assert res.reason == "Memory subsystem is disabled"
