"""
Deterministic, capped, auditable memory prior calculation.
Guarantees reliable demo behaviour based on historical precedents.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .schemas import MemoryStats


class MemoryPriorResult(BaseModel):
    applied: bool = False
    dominant: Optional[str] = None  # "false_alarm" | "real_collision" | None
    dominant_count: int = 0
    total_precedents: int = 0
    delta: float = 0.0
    corr_delta: float = 0.0
    skep_delta: float = 0.0
    pre_memory_scores: Dict[str, float] = Field(default_factory=dict)
    post_memory_scores: Dict[str, float] = Field(default_factory=dict)
    reason: str = "Insufficient precedents for memory prior adjustment"


def compute_memory_prior(
    stats: Optional[MemoryStats],
    raw_corr: float,
    raw_skep: float,
    min_precedents: Optional[int] = None,
    max_adjust: Optional[float] = None,
    memory_enabled: bool = True,
) -> MemoryPriorResult:
    """
    Computes deterministic memory prior adjustment according to Phase 5 rules:
    - Min precedents threshold (default 3)
    - Dominant side >= 75%
    - delta = min(max_adjust, 0.05 * dominant_count)
    - False-dominant: skeptic += delta, corroborator -= delta/2
    - Real-dominant: corroborator += delta/2, skeptic -= delta
    - Safety asymmetry: memory-driven REJECT requires raw_corr < 0.85
    """
    pre_scores = {"corr": round(raw_corr, 2), "skep": round(raw_skep, 2), "fused": round(raw_corr - raw_skep, 2)}

    if not memory_enabled:
        return MemoryPriorResult(
            applied=False,
            pre_memory_scores=pre_scores,
            post_memory_scores=pre_scores,
            reason="Memory subsystem is disabled",
        )

    if stats is None:
        return MemoryPriorResult(
            applied=False,
            pre_memory_scores=pre_scores,
            post_memory_scores=pre_scores,
            reason="No memory statistics available",
        )

    min_p = min_precedents if min_precedents is not None else int(os.getenv("MEMORY_MIN_PRECEDENTS", "3"))
    max_a = max_adjust if max_adjust is not None else float(os.getenv("MEMORY_MAX_ADJUST", "0.25"))

    confirmed_false = stats.overrides
    confirmed_real = stats.approved
    total = confirmed_false + confirmed_real

    if total < min_p:
        return MemoryPriorResult(
            applied=False,
            total_precedents=total,
            pre_memory_scores=pre_scores,
            post_memory_scores=pre_scores,
            reason=f"Total confirmed precedents ({total}) < minimum required ({min_p})",
        )

    dominant_count = max(confirmed_false, confirmed_real)
    dominant_ratio = dominant_count / total if total > 0 else 0.0

    if dominant_ratio < 0.75:
        return MemoryPriorResult(
            applied=False,
            total_precedents=total,
            dominant_count=dominant_count,
            pre_memory_scores=pre_scores,
            post_memory_scores=pre_scores,
            reason=f"Dominant precedent ratio ({dominant_ratio:.1%}) < 75% threshold",
        )

    delta = min(max_a, round(0.05 * dominant_count, 2))

    if confirmed_false > confirmed_real:
        # False alarm dominant
        # Phase 5.2 safety asymmetry rule:
        # High confidence raw corroborator >= 0.85 is NEVER suppressed by memory!
        if raw_corr >= 0.85:
            return MemoryPriorResult(
                applied=False,
                dominant="false_alarm",
                dominant_count=confirmed_false,
                total_precedents=total,
                pre_memory_scores=pre_scores,
                post_memory_scores=pre_scores,
                reason="Safety guard: clear-cut high-confidence collision (corr >= 0.85) cannot be suppressed by memory",
            )

        corr_delta = -round(delta / 2.0, 2)
        skep_delta = delta
        dominant_type = "false_alarm"
        reason = f"Memory prior: {confirmed_false} operator-confirmed false alarms dominate ({dominant_ratio:.0%}); skeptic boosted +{skep_delta:.2f}"
    else:
        # Real collision dominant
        corr_delta = round(delta / 2.0, 2)
        skep_delta = -delta
        dominant_type = "real_collision"
        reason = f"Memory prior: {confirmed_real} operator-confirmed collisions dominate ({dominant_ratio:.0%}); corroborator boosted +{corr_delta:.2f}"

    post_corr = max(0.0, min(1.0, round(raw_corr + corr_delta, 2)))
    post_skep = max(0.0, min(1.0, round(raw_skep + skep_delta, 2)))
    post_scores = {"corr": post_corr, "skep": post_skep, "fused": round(post_corr - post_skep, 2)}

    return MemoryPriorResult(
        applied=True,
        dominant=dominant_type,
        dominant_count=dominant_count,
        total_precedents=total,
        delta=delta,
        corr_delta=corr_delta,
        skep_delta=skep_delta,
        pre_memory_scores=pre_scores,
        post_memory_scores=post_scores,
        reason=reason,
    )
