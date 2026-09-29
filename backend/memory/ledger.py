"""
Append-only JSONL structured ledger for deterministic memory storage.
Thread/async-safe with an asyncio lock.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from .schemas import MemoryEvent, MemoryStats, Precedent

logger = logging.getLogger("aurashield.memory.ledger")

DEFAULT_LEDGER_PATH = "data/memory_ledger.jsonl"


class MemoryLedger:
    def __init__(self, file_path: Optional[str] = None) -> None:
        raw_path = file_path or os.getenv("MEMORY_LOCAL_LEDGER", DEFAULT_LEDGER_PATH)
        # If relative, resolve relative to backend dir or current working dir
        self.file_path = Path(raw_path).resolve()
        self._lock = asyncio.Lock()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.file_path.exists():
                self.file_path.touch(exist_ok=True)
        except Exception as e:
            logger.warning("Could not initialize ledger file/directory at %s: %s", self.file_path, e)

    async def append(self, event: MemoryEvent) -> None:
        line = json.dumps(event.model_dump(), ensure_ascii=False) + "\n"
        async with self._lock:
            def _write():
                self._ensure_dir()
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(line)
            await asyncio.to_thread(_write)

    async def read_all(self) -> List[MemoryEvent]:
        async with self._lock:
            def _read() -> List[MemoryEvent]:
                if not self.file_path.exists():
                    return []
                events: List[MemoryEvent] = []
                with open(self.file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            events.append(MemoryEvent.model_validate(data))
                        except Exception as e:
                            logger.warning("Corrupt line in memory ledger: %s (%s)", line[:60], e)
                return events
            return await asyncio.to_thread(_read)

    async def count(self) -> int:
        async with self._lock:
            def _cnt() -> int:
                if not self.file_path.exists():
                    return 0
                count = 0
                with open(self.file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            count += 1
                return count
            return await asyncio.to_thread(_cnt)

    async def query(
        self,
        zone: Optional[str] = None,
        cause_tags: Optional[List[str]] = None,
        kinds: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[MemoryEvent]:
        all_events = await self.read_all()
        filtered: List[MemoryEvent] = []

        target_tags = set(t.lower() for t in cause_tags) if cause_tags else None
        target_kinds = set(kinds) if kinds else None

        # Return latest events first
        for event in reversed(all_events):
            if zone and event.zone.strip().lower() != zone.strip().lower():
                continue
            if target_kinds and event.kind not in target_kinds:
                continue
            if target_tags:
                ev_tags = set(t.lower() for t in event.cause_tags)
                if not (ev_tags & target_tags):
                    continue
            filtered.append(event)
            if len(filtered) >= limit:
                break

        return filtered

    async def stats(
        self,
        zone: Optional[str] = None,
        cause_tags: Optional[List[str]] = None,
    ) -> MemoryStats:
        all_events = await self.read_all()
        target_tags = set(t.lower() for t in cause_tags) if cause_tags else None

        approved = 0
        overrides = 0
        verified = 0
        rejected = 0
        declines = 0
        timeouts = 0
        total = 0

        for event in all_events:
            if zone and event.zone.strip().lower() != zone.strip().lower():
                continue
            if target_tags:
                ev_tags = set(t.lower() for t in event.cause_tags)
                if not (ev_tags & target_tags):
                    continue

            total += 1
            if event.kind == "OPERATOR_APPROVED":
                approved += 1
            elif event.kind == "OPERATOR_OVERRIDE":
                overrides += 1
            elif event.kind == "INCIDENT_VERIFIED":
                verified += 1
            elif event.kind == "INCIDENT_REJECTED":
                rejected += 1
            elif event.kind == "DISPATCH_DECLINED":
                declines += 1
            elif event.kind == "ACK_TIMEOUT":
                timeouts += 1

        return MemoryStats(
            zone=zone,
            cause_tags=cause_tags or [],
            approved=approved,
            overrides=overrides,
            verified=verified,
            rejected=rejected,
            declines=declines,
            timeouts=timeouts,
            total=total,
        )

    async def clear(self) -> None:
        async with self._lock:
            def _clr():
                self._ensure_dir()
                with open(self.file_path, "w", encoding="utf-8") as f:
                    pass
            await asyncio.to_thread(_clr)


def event_to_precedent(event: MemoryEvent, relevance: float = 0.85) -> Precedent:
    """Format a stored MemoryEvent into a clean, informative Precedent string."""
    tags_str = f" [{', '.join(event.cause_tags)}]" if event.cause_tags else ""
    if event.kind == "OPERATOR_OVERRIDE":
        text = (
            f"Precedent ({event.zone}): Operator manually rejected candidate as false alarm{tags_str}. "
            f"Notes: {event.notes or 'optical noise / flare artifact'}."
        )
    elif event.kind == "OPERATOR_APPROVED":
        text = (
            f"Precedent ({event.zone}): Operator confirmed real collision{tags_str}. "
            f"Scores: corr={event.corr_score or 0.9:.2f}, skeptic={event.skeptic_score or 0.1:.2f}. Dispatched."
        )
    elif event.kind == "INCIDENT_REJECTED":
        text = (
            f"Precedent ({event.zone}): System rejected candidate{tags_str}. "
            f"Skeptic score={event.skeptic_score or 0.7:.2f}, fused={event.fused_score or -0.2:.2f}."
        )
    elif event.kind == "DISPATCH_DECLINED":
        text = (
            f"Precedent ({event.zone}): Hospital {event.hospital_id or 'H_ALPHA'} declined dispatch at peak hour. "
            f"Re-routed to secondary trauma unit."
        )
    else:
        text = f"Precedent ({event.zone}): Event {event.kind}{tags_str}. {event.notes or ''}".strip()

    return Precedent(
        text=text,
        source="local-fallback",
        relevance=relevance,
        ts=event.ts,
        kind=event.kind,
        zone=event.zone,
        cause_tags=event.cause_tags,
    )
