"""
Tests for Phase 4: Verification agent memory context injection and evidence generation.
"""
import pytest
from agents.verification import (
    format_precedents_block,
    get_real_scores,
)
from memory import Precedent


@pytest.mark.asyncio
async def test_format_precedents_block():
    precedents = [
        Precedent(text="Operator Ravi overrode glare in Zone 02", source="hindsight"),
        Precedent(text="Operator Priya confirmed collision in Zone 04", source="local-fallback"),
    ]
    block = format_precedents_block(precedents)
    assert "[HISTORICAL OPERATIONAL PRECEDENTS" in block
    assert "Operator Ravi overrode glare in Zone 02" in block
    assert "Operator Priya confirmed collision in Zone 04" in block
    assert "[END PRECEDENTS" in block
    assert len(block) <= 600


@pytest.mark.asyncio
async def test_get_real_scores_without_memory():
    corr, skep, conf, deg, corr_ev, skep_ev, prov, precs, mem_used = await get_real_scores(
        scenario="crash_zone04",
        fallback_corr=0.91,
        fallback_skep=0.14,
        memory_context=None,
    )
    assert mem_used is False
    assert len(precs) == 0
    assert corr > 0.8
    assert skep < 0.3


@pytest.mark.asyncio
async def test_get_real_scores_with_memory_cites_precedents():
    precedents = [
        Precedent(text="6 prior Zone 02 glare events were operator-confirmed false alarms", source="hindsight"),
        Precedent(text="Camera mount vibration at 16:30", source="local-fallback"),
    ]
    corr, skep, conf, deg, corr_ev, skep_ev, prov, precs, mem_used = await get_real_scores(
        scenario="false_alarm",
        fallback_corr=0.55,
        fallback_skep=0.65,
        memory_context=precedents,
    )
    assert mem_used is True
    assert len(precs) == 2
    # Check that Memory: citation is in evidence
    assert any(ev.startswith("Memory:") for ev in corr_ev), f"No Memory: prefix in corr_ev: {corr_ev}"
    assert any(ev.startswith("Memory:") for ev in skep_ev), f"No Memory: prefix in skep_ev: {skep_ev}"
