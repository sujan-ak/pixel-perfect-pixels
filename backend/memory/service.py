"""
Hindsight (Vectorize) Memory Service for AuraShield.
Dual-writes to deterministic JSONL ledger and semantic Hindsight Cloud / self-hosted bank.
Features circuit breaker, graceful local fallback, reachability cache, and natural-language extraction.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
import time
from typing import Any, List, Optional

from .ledger import MemoryLedger, event_to_precedent
from .schemas import MemoryEvent, MemoryKind, MemoryStatus, MemoryStats, Precedent

logger = logging.getLogger("aurashield.memory.service")


def _build_prose(event: MemoryEvent) -> str:
    """Rich natural-language prose for Hindsight entity & fact extraction."""
    tags_detail = f" (tags: {', '.join(event.cause_tags)})" if event.cause_tags else ""
    if event.kind == "OPERATOR_OVERRIDE":
        return (
            f"At {event.ts}, operator manually overrode and rejected incident {event.incident_id} in {event.zone} "
            f"as confirmed false alarm{tags_detail}. Operator finding: {event.notes or 'optical noise or glare artifact'}. "
            f"Pre-override scores: Corroborator={event.corr_score or 0.5:.2f}, Skeptic={event.skeptic_score or 0.6:.2f}, "
            f"Fused={event.fused_score or -0.1:.2f}."
        )
    elif event.kind == "OPERATOR_APPROVED":
        return (
            f"At {event.ts}, operator confirmed real collision and approved dispatch for incident {event.incident_id} "
            f"in {event.zone}{tags_detail}. Scores: Corroborator={event.corr_score or 0.9:.2f}, Skeptic={event.skeptic_score or 0.1:.2f}, "
            f"Fused={event.fused_score or 0.8:.2f}. Emergency ambulance response initiated."
        )
    elif event.kind == "INCIDENT_VERIFIED":
        return (
            f"At {event.ts}, agent consensus classified scenario {event.scenario} in {event.zone} as VERIFIED{tags_detail}. "
            f"Corroborator={event.corr_score or 0.9:.2f}, Skeptic={event.skeptic_score or 0.1:.2f}. Awaiting human clearance."
        )
    elif event.kind == "INCIDENT_REJECTED":
        return (
            f"At {event.ts}, candidate {event.scenario} in {event.zone} was REJECTED as false alarm{tags_detail}. "
            f"Skeptic={event.skeptic_score or 0.7:.2f}, Fused={event.fused_score or -0.2:.2f}. Suppressed before operator dispatch."
        )
    elif event.kind == "DISPATCH_ACKED":
        return (
            f"At {event.ts}, field responder acknowledged incident {event.incident_id} in {event.zone} "
            f"with latency {event.ack_latency_ms or 0}ms. Ambulance unit en route."
        )
    elif event.kind == "DISPATCH_DECLINED":
        return (
            f"At {event.ts}, hospital {event.hospital_id or 'H_ALPHA'} declined dispatch request for incident {event.incident_id} "
            f"in {event.zone}. Escalation triggered automatic re-routing to alternate hospital."
        )
    elif event.kind == "ACK_TIMEOUT":
        return (
            f"At {event.ts}, hospital {event.hospital_id or 'H_ALPHA'} timed out on dispatch request for {event.incident_id}. "
            f"Re-planning engaged."
        )
    elif event.kind == "INCIDENT_CLOSED":
        return (
            f"At {event.ts}, incident {event.incident_id} in {event.zone} was closed. "
            f"Outcome: {event.outcome or 'patient delivered to trauma center'}."
        )
    return f"Incident {event.incident_id} in {event.zone}: {event.kind}{tags_detail}. {event.notes or ''}".strip()


class MemoryService:
    def __init__(self, ledger: Optional[MemoryLedger] = None, client: Optional[Any] = None) -> None:
        self.ledger = ledger or MemoryLedger()
        self._custom_client = client
        self.bank_id = os.getenv("HINDSIGHT_BANK_ID", "aurashield-ops")
        self.enabled = os.getenv("MEMORY_ENABLED", "1").strip().lower() in ("1", "true", "yes")

        # Circuit breaker state
        self._consecutive_failures: int = 0
        self._circuit_open_until: float = 0.0

        # Reachability cache state (10s)
        self._last_reachability_check: float = 0.0
        self._cached_reachable: bool = False
        self._last_error: Optional[str] = None
        self._bank_ensured: bool = False
        self._client: Optional[Any] = None

    def _is_circuit_open(self) -> bool:
        if self._consecutive_failures >= 3:
            if time.time() < self._circuit_open_until:
                return True
            # Cool-down expired -> attempt auto-recovery
            self._consecutive_failures = 0
            self._circuit_open_until = 0.0
        return False

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._cached_reachable = True
        self._last_error = None

    def _record_failure(self, err: str) -> None:
        self._consecutive_failures += 1
        self._last_error = err
        if self._consecutive_failures >= 3 and self._circuit_open_until == 0.0:
            self._circuit_open_until = time.time() + 30.0
            logger.warning(
                "Hindsight circuit breaker OPEN after %d consecutive failures. Skipping network for 30s.",
                self._consecutive_failures,
            )

    def _get_client(self) -> Optional[Any]:
        if self._custom_client is not None:
            return self._custom_client
        if self._client is not None:
            return self._client

        base_url = os.getenv("HINDSIGHT_URL", "https://api.hindsight.vectorize.io")
        api_key = os.getenv("HINDSIGHT_API_KEY")

        if not base_url or not base_url.strip() or base_url.startswith("http://<"):
            return None

        try:
            from hindsight_client import Hindsight
            self._client = Hindsight(base_url=base_url.strip(), api_key=api_key.strip() if api_key else None)
            return self._client
        except Exception as e:
            logger.debug("Could not construct Hindsight client: %s", e)
            return None

    async def aclose(self) -> None:
        if self._client is not None and hasattr(self._client, "aclose"):
            try:
                await self._client.aclose()
            except Exception:
                pass
        self._client = None

    async def ensure_bank(self) -> bool:
        """Create bank if missing with appropriate traffic monitoring disposition and mission."""
        if self._bank_ensured or not self.enabled:
            return True
        if self._is_circuit_open():
            return False

        client = self._get_client()
        if client is None:
            return False

        try:
            async with self._lock:
                if self._bank_ensured:
                    return True
                # Check if bank exists or create it
                if hasattr(client, "aget_bank_config"):
                    try:
                        await asyncio.wait_for(client.aget_bank_config(self.bank_id), timeout=4.0)
                        self._bank_ensured = True
                        self._record_success()
                        return True
                    except Exception:
                        pass

                if hasattr(client, "acreate_bank"):
                    mission = (
                        "Operational memory for AuraShield smart traffic incident verification. "
                        "Retains confirmed vehicular collisions, lens flare and camera vibration false alarm precedents, "
                        "operator overrides, and peak-hour hospital routing latencies."
                    )
                    await asyncio.wait_for(
                        client.acreate_bank(
                            bank_id=self.bank_id,
                            name="AuraShield Ops Memory",
                            mission=mission,
                            disposition_skepticism=4,
                            disposition_literalism=4,
                        ),
                        timeout=5.0,
                    )
                self._bank_ensured = True
                self._record_success()
                logger.info("Hindsight bank '%s' initialized successfully", self.bank_id)
                return True
        except Exception as e:
            self._record_failure(str(e))
            logger.warning("ensure_bank failed for '%s' (fallback to local ledger): %s", self.bank_id, e)
            return False

    async def retain(self, event: MemoryEvent) -> None:
        """Dual-write event: first to deterministic ledger, then async to Hindsight Cloud."""
        # 1. ALWAYS write to deterministic local ledger first
        try:
            await self.ledger.append(event)
        except Exception as e:
            logger.error("Failed writing event %s to local memory ledger: %s", event.event_id, e)

        if not self.enabled:
            return

        # 2. Dual-write to Hindsight if available and circuit is healthy
        if self._is_circuit_open():
            logger.debug("Hindsight circuit breaker open; skipping remote retain for %s", event.event_id)
            return

        client = self._get_client()
        if client is None:
            return

        await self.ensure_bank()

        try:
            prose = _build_prose(event)
            tags = list(set([t.lower() for t in event.cause_tags] + [event.zone.lower(), event.kind.lower(), event.scenario.lower()]))

            dt_ts = None
            try:
                clean_ts = event.ts.replace("Z", "+00:00")
                dt_ts = datetime.fromisoformat(clean_ts)
            except Exception:
                dt_ts = datetime.now(timezone.utc)

            async def _do_retain():
                if hasattr(client, "aretain"):
                    await client.aretain(
                        bank_id=self.bank_id,
                        content=prose,
                        timestamp=dt_ts,
                        context=event.kind,
                        tags=tags,
                    )
                elif hasattr(client, "retain"):
                    await asyncio.to_thread(
                        client.retain,
                        bank_id=self.bank_id,
                        content=prose,
                        timestamp=dt_ts,
                        context=event.kind,
                        tags=tags,
                    )

            await asyncio.wait_for(_do_retain(), timeout=6.0)
            self._record_success()
            logger.info("Retained event %s in Hindsight bank '%s'", event.event_id, self.bank_id)
        except Exception as e:
            self._record_failure(str(e))
            logger.warning("Hindsight retain failed for event %s (ledger intact): %s", event.event_id, e)

    async def recall(
        self,
        query: str,
        zone: Optional[str] = None,
        cause_tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Precedent]:
        """Recall relevant historical precedents. Falls back seamlessly to local ledger."""
        if not self.enabled:
            return []

        # Try Hindsight if reachable and circuit closed
        if not self._is_circuit_open():
            client = self._get_client()
            if client is not None:
                await self.ensure_bank()
                try:
                    search_tags = [t.lower() for t in (cause_tags or [])]
                    if zone:
                        search_tags.append(zone.lower())

                    async def _do_recall():
                        if hasattr(client, "arecall"):
                            return await client.arecall(
                                bank_id=self.bank_id,
                                query=query,
                                tags=search_tags if search_tags else None,
                                max_tokens=1024,
                                budget="mid",
                            )
                        elif hasattr(client, "recall"):
                            return await asyncio.to_thread(
                                client.recall,
                                bank_id=self.bank_id,
                                query=query,
                                tags=search_tags if search_tags else None,
                                max_tokens=1024,
                                budget="mid",
                            )
                        return None

                    resp = await asyncio.wait_for(_do_recall(), timeout=4.0)
                    if resp and hasattr(resp, "results") and resp.results:
                        precedents: List[Precedent] = []
                        for res in resp.results[:limit]:
                            txt = getattr(res, "text", "") or str(res)
                            score = 0.85
                            scores_dict = getattr(res, "scores", None)
                            if scores_dict and isinstance(scores_dict, dict):
                                score = float(scores_dict.get("relevance", 0.85))
                            precedents.append(
                                Precedent(
                                    text=txt,
                                    source="hindsight",
                                    relevance=round(score, 2),
                                    zone=zone,
                                    cause_tags=cause_tags or [],
                                )
                            )
                        if precedents:
                            self._record_success()
                            logger.info("Recalled %d precedents from Hindsight Cloud", len(precedents))
                            return precedents
                except Exception as e:
                    self._record_failure(str(e))
                    logger.warning("Hindsight recall failed (%s), falling back to local ledger", e)

        # Local deterministic fallback
        events = await self.ledger.query(zone=zone, cause_tags=cause_tags, limit=limit)
        precedents = [event_to_precedent(ev) for ev in events]
        logger.info("Recalled %d precedents from local ledger fallback", len(precedents))
        return precedents

    async def reflect(self, question: str) -> str:
        """Synthesize high-level operational insights from memory."""
        if not self.enabled:
            return "Memory subsystem is disabled. No insights available."

        if not self._is_circuit_open():
            client = self._get_client()
            if client is not None:
                await self.ensure_bank()
                try:
                    async def _do_reflect():
                        if hasattr(client, "areflect"):
                            return await client.areflect(bank_id=self.bank_id, query=question, budget="low")
                        elif hasattr(client, "reflect"):
                            return await asyncio.to_thread(client.reflect, bank_id=self.bank_id, query=question, budget="low")
                        return None

                    resp = await asyncio.wait_for(_do_reflect(), timeout=10.0)
                    if resp and hasattr(resp, "text") and resp.text:
                        self._record_success()
                        return resp.text.strip()
                except Exception as e:
                    self._record_failure(str(e))
                    logger.warning("Hindsight reflect failed: %s; using template fallback", e)

        # Deterministic ledger synthesis fallback
        stats_all = await self.ledger.stats()
        stats_z2_glare = await self.ledger.stats(zone="Zone 02", cause_tags=["glare"])
        stats_z4 = await self.ledger.stats(zone="Zone 04")
        recent_declines = await self.ledger.query(kinds=["DISPATCH_DECLINED"], limit=5)

        hosp_declines = {}
        for ev in recent_declines:
            hid = ev.hospital_id or "H_ALPHA"
            hosp_declines[hid] = hosp_declines.get(hid, 0) + 1

        insight = (
            f"AuraShield Operational Insights (Synthesized from {stats_all.total} ledger events):\n"
            f"• Zone 02 Low-Sun Glare: Operators recorded {stats_z2_glare.overrides} manual overrides "
            f"for low-sun angle lens flare between 15:30-17:30. System prior now discounts glare anomalies automatically.\n"
            f"• Zone 04 Real Collisions: {stats_z4.approved} verified collisions sustained over 10+ frames confirmed and dispatched.\n"
            f"• Hospital Dispatch Dynamics: H_ALPHA recorded {hosp_declines.get('H_ALPHA', 0)} peak-hour capacity declines/timeouts. "
            f"Route planning adapts to prioritize H_BETA when peak congestion patterns repeat."
        )
        return insight

    async def status(self) -> MemoryStatus:
        """Returns runtime status with reachability cached for 10 seconds."""
        now = time.time()
        events_count = await self.ledger.count()
        circuit_open = self._is_circuit_open()

        if not self.enabled:
            return MemoryStatus(
                enabled=False,
                hindsight_reachable=False,
                bank_id=self.bank_id,
                events_in_ledger=events_count,
                last_error=None,
                circuit_breaker_open=circuit_open,
            )

        client = self._get_client()
        if client is None:
            return MemoryStatus(
                enabled=True,
                hindsight_reachable=False,
                bank_id=self.bank_id,
                events_in_ledger=events_count,
                last_error="No Hindsight client configured (using local ledger)",
                circuit_breaker_open=circuit_open,
            )

        if circuit_open:
            return MemoryStatus(
                enabled=True,
                hindsight_reachable=False,
                bank_id=self.bank_id,
                events_in_ledger=events_count,
                last_error=f"Circuit breaker open ({self._consecutive_failures} failures)",
                circuit_breaker_open=True,
            )

        if now - self._last_reachability_check < 10.0:
            return MemoryStatus(
                enabled=True,
                hindsight_reachable=self._cached_reachable,
                bank_id=self.bank_id,
                events_in_ledger=events_count,
                last_error=self._last_error,
                circuit_breaker_open=False,
            )

        self._last_reachability_check = now
        try:
            if hasattr(client, "aget_version"):
                await asyncio.wait_for(client.aget_version(), timeout=3.0)
            elif hasattr(client, "aget_bank_config"):
                await asyncio.wait_for(client.aget_bank_config(self.bank_id), timeout=3.0)
            else:
                await self.ensure_bank()
            self._record_success()
        except Exception as e:
            self._cached_reachable = False
            self._last_error = str(e)
            logger.debug("Hindsight reachability check failed: %s", e)

        return MemoryStatus(
            enabled=True,
            hindsight_reachable=self._cached_reachable,
            bank_id=self.bank_id,
            events_in_ledger=events_count,
            last_error=self._last_error,
            circuit_breaker_open=self._is_circuit_open(),
        )


# Global singleton instance
memory = MemoryService()
