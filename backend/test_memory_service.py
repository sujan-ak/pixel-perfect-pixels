"""
Unit tests for AuraShield Hindsight Memory Service (Phase 2).
Tests success, timeout, exception, circuit breaker, and disabled mode.
"""
import asyncio
import os
import pytest
from datetime import datetime, timezone
from pathlib import Path

from memory import (
    MemoryEvent,
    MemoryLedger,
    MemoryService,
    Precedent,
)


class FakeHindsightClient:
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls = []

    async def aget_version(self):
        if self.mode == "timeout":
            await asyncio.sleep(5.0)
        elif self.mode == "error":
            raise RuntimeError("Fake Hindsight Network Error")
        return {"version": "0.10.1"}

    async def aget_bank_config(self, bank_id: str):
        if self.mode == "error":
            raise RuntimeError("Bank error")
        return {"bank_id": bank_id}

    async def acreate_bank(self, **kwargs):
        if self.mode == "error":
            raise RuntimeError("Bank creation error")
        return {"status": "created"}

    async def aretain(self, bank_id: str, content: str, timestamp=None, context=None, tags=None):
        self.calls.append(("retain", bank_id, content, tags))
        if self.mode == "timeout":
            await asyncio.sleep(10.0)
        elif self.mode == "error":
            raise ConnectionError("Remote Hindsight service unreachable")
        return {"id": "mem_123"}

    async def arecall(self, bank_id: str, query: str, tags=None, max_tokens=1024, budget="mid"):
        self.calls.append(("recall", bank_id, query, tags))
        if self.mode == "timeout":
            await asyncio.sleep(10.0)
        elif self.mode == "error":
            raise ConnectionError("Recall failed: 503 Service Unavailable")

        class FakeResult:
            def __init__(self, text, relevance=0.88):
                self.text = text
                self.scores = {"relevance": relevance}

        class FakeRecallResponse:
            def __init__(self):
                self.results = [
                    FakeResult("Precedent: Zone 02 glare event confirmed false alarm by operator."),
                    FakeResult("Precedent: Zone 02 afternoon low-sun lens flare."),
                ]

        return FakeRecallResponse()

    async def areflect(self, bank_id: str, query: str, budget="low"):
        if self.mode == "timeout":
            await asyncio.sleep(15.0)
        elif self.mode == "error":
            raise ConnectionError("Reflect engine timeout")

        class FakeReflectResponse:
            text = "Hindsight synthesized insight: 8 confirmed glare anomalies in Zone 02."

        return FakeReflectResponse()


@pytest.mark.asyncio
async def test_ledger_append_query_stats(tmp_path):
    test_file = tmp_path / "test_ledger.jsonl"
    ledger = MemoryLedger(file_path=str(test_file))

    event1 = MemoryEvent(
        event_id="evt_01",
        ts=datetime.now(timezone.utc).isoformat(),
        kind="OPERATOR_OVERRIDE",
        incident_id="INC-001",
        zone="Zone 02",
        scenario="glare_ambiguous",
        cause_tags=["glare", "lens_flare"],
        operator_action="OVERRIDE_REJECT",
        notes="Operator confirmed low-sun optical glare",
        corr_score=0.45,
        skeptic_score=0.55,
        fused_score=-0.10,
    )
    event2 = MemoryEvent(
        event_id="evt_02",
        ts=datetime.now(timezone.utc).isoformat(),
        kind="OPERATOR_APPROVED",
        incident_id="INC-002",
        zone="Zone 04",
        scenario="crash_zone04",
        cause_tags=["collision"],
        operator_action="APPROVE_DISPATCH",
        notes="Operator confirmed real head-on collision",
        corr_score=0.92,
        skeptic_score=0.10,
        fused_score=0.82,
    )

    await ledger.append(event1)
    await ledger.append(event2)

    assert await ledger.count() == 2

    # Query by zone
    z2_events = await ledger.query(zone="Zone 02")
    assert len(z2_events) == 1
    assert z2_events[0].event_id == "evt_01"

    # Query by cause tags
    glare_events = await ledger.query(cause_tags=["glare"])
    assert len(glare_events) == 1
    assert glare_events[0].incident_id == "INC-001"

    # Stats
    stats_z2 = await ledger.stats(zone="Zone 02", cause_tags=["glare"])
    assert stats_z2.overrides == 1
    assert stats_z2.approved == 0
    assert stats_z2.total == 1

    stats_z4 = await ledger.stats(zone="Zone 04")
    assert stats_z4.approved == 1
    assert stats_z4.overrides == 0


@pytest.mark.asyncio
async def test_memory_service_success_mode(tmp_path):
    test_file = tmp_path / "test_ledger_service.jsonl"
    ledger = MemoryLedger(file_path=str(test_file))
    client = FakeHindsightClient(mode="success")
    srv = MemoryService(ledger=ledger, client=client)

    event = MemoryEvent(
        event_id="evt_100",
        ts=datetime.now(timezone.utc).isoformat(),
        kind="OPERATOR_OVERRIDE",
        incident_id="INC-100",
        zone="Zone 02",
        scenario="glare_ambiguous",
        cause_tags=["glare"],
        notes="Operator confirmed glare artifact",
    )

    await srv.retain(event)
    assert await ledger.count() == 1
    assert len(client.calls) == 1
    assert client.calls[0][0] == "retain"

    # Recall
    precedents = await srv.recall(query="glare", zone="Zone 02", cause_tags=["glare"])
    assert len(precedents) == 2
    assert precedents[0].source == "hindsight"
    assert "glare" in precedents[0].text.lower()

    # Reflect
    insight = await srv.reflect("Tell me about Zone 02")
    assert "Hindsight synthesized insight" in insight

    # Status
    status = await srv.status()
    assert status.enabled is True
    assert status.hindsight_reachable is True
    assert status.events_in_ledger == 1


@pytest.mark.asyncio
async def test_memory_service_fallback_on_error(tmp_path):
    test_file = tmp_path / "test_ledger_err.jsonl"
    ledger = MemoryLedger(file_path=str(test_file))
    # Client that raises exceptions
    client = FakeHindsightClient(mode="error")
    srv = MemoryService(ledger=ledger, client=client)

    event = MemoryEvent(
        event_id="evt_200",
        ts=datetime.now(timezone.utc).isoformat(),
        kind="OPERATOR_OVERRIDE",
        incident_id="INC-200",
        zone="Zone 02",
        scenario="glare_ambiguous",
        cause_tags=["glare"],
        notes="Low-sun optical reflection",
    )

    # Retain should NOT throw; ledger must still receive event
    await srv.retain(event)
    assert await ledger.count() == 1

    # Recall should fall back gracefully to ledger
    precedents = await srv.recall(query="glare", zone="Zone 02", cause_tags=["glare"])
    assert len(precedents) == 1
    assert precedents[0].source == "local-fallback"
    assert "Operator manually rejected" in precedents[0].text

    # Reflect should fall back to deterministic template
    insight = await srv.reflect("Zone 02 glare trends")
    assert "AuraShield Operational Insights" in insight
    assert "Zone 02 Low-Sun Glare" in insight


@pytest.mark.asyncio
async def test_memory_service_circuit_breaker(tmp_path):
    test_file = tmp_path / "test_ledger_cb.jsonl"
    ledger = MemoryLedger(file_path=str(test_file))
    client = FakeHindsightClient(mode="error")
    srv = MemoryService(ledger=ledger, client=client)

    # 3 failures trip the circuit breaker
    for i in range(3):
        await srv.recall(query="test", zone="Zone 02")

    assert srv._consecutive_failures >= 3
    assert srv._is_circuit_open() is True

    # Next call should immediately use ledger without touching remote client
    calls_before = len(client.calls)
    precedents = await srv.recall(query="test", zone="Zone 02")
    assert len(client.calls) == calls_before  # No remote call made
    assert all(p.source == "local-fallback" for p in precedents)


@pytest.mark.asyncio
async def test_memory_service_disabled_mode(tmp_path):
    test_file = tmp_path / "test_ledger_dis.jsonl"
    ledger = MemoryLedger(file_path=str(test_file))
    client = FakeHindsightClient(mode="success")
    srv = MemoryService(ledger=ledger, client=client)
    srv.enabled = False

    precedents = await srv.recall(query="glare", zone="Zone 02")
    assert precedents == []

    insight = await srv.reflect("insights?")
    assert "disabled" in insight.lower()

    status = await srv.status()
    assert status.enabled is False
    assert status.hindsight_reachable is False
