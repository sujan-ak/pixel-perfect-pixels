"""
Unit and integration tests for AuraShield Phase 7 Memory API endpoints and glare_ambiguous scenario.
"""
import asyncio
import os
import pytest
from httpx import ASGITransport, AsyncClient

# Ensure backend root is on path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import app, orchestrator, db
from memory import memory


@pytest.mark.asyncio
async def test_memory_status_endpoint():
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/memory/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "hindsight_reachable" in data
        assert "bank_id" in data
        assert "events_in_ledger" in data


@pytest.mark.asyncio
async def test_memory_toggle_endpoint():
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Toggle off
        resp = await client.post("/memory/toggle", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        assert memory.enabled is False

        # Toggle on
        resp = await client.post("/memory/toggle", json={"enabled": True})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True
        assert memory.enabled is True


@pytest.mark.asyncio
async def test_memory_recall_endpoint():
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/memory/recall?q=glare&zone=Zone%2002&limit=3")
        assert resp.status_code == 200
        precedents = resp.json()
        assert isinstance(precedents, list)
        if len(precedents) > 0:
            assert "text" in precedents[0]
            assert "source" in precedents[0]


@pytest.mark.asyncio
async def test_memory_insights_endpoint():
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/memory/insights")
        assert resp.status_code == 200
        data = resp.json()
        assert "insights" in data
        assert len(data["insights"]) > 0
        assert "cached" in data

        # Second call should hit the 60s cache
        resp2 = await client.get("/memory/insights")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["cached"] is True


@pytest.mark.asyncio
async def test_memory_timeline_endpoint():
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/memory/timeline?limit=10")
        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)
        if len(events) > 0:
            assert "event_id" in events[0]
            assert "kind" in events[0]


@pytest.mark.asyncio
async def test_memory_learning_curve_endpoint():
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/memory/learning-curve")
        assert resp.status_code == 200
        curve = resp.json()
        assert isinstance(curve, list)
        if len(curve) > 0:
            assert "run" in curve[0]
            assert "pre_memory_fused" in curve[0]
            assert "post_memory_fused" in curve[0]
            assert "verdict" in curve[0]
            assert "precedents" in curve[0]


@pytest.mark.asyncio
async def test_glare_ambiguous_memory_off_vs_on():
    await db.init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Memory OFF: glare_ambiguous reaches VERIFIED / RESPONSE_PROPOSED
        await client.post("/memory/toggle", json={"enabled": False})
        t_resp = await client.post("/incidents/trigger", json={"scenario": "glare_ambiguous"})
        assert t_resp.status_code == 202
        inc_id = t_resp.json()["incident_id"]

        # Wait for pipeline to finish
        for _ in range(40):
            await asyncio.sleep(0.3)
            task = orchestrator.active_tasks.get(inc_id)
            if task is None or task.done():
                break

        inc_off = await db.get_incident_by_id(inc_id)
        assert inc_off is not None
        # With memory off, raw fused is 0.46 > 0.35, so it reaches RESPONSE_PROPOSED or VERIFIED
        assert inc_off.state in ("RESPONSE_PROPOSED", "VERIFIED")
        assert inc_off.fused_score >= 0.40

        # Wait cooldown (3.1s)
        await asyncio.sleep(3.2)

        # 2. Memory ON: glare_ambiguous flips to REJECTED due to >=3 Zone 02 glare overrides
        await client.post("/memory/toggle", json={"enabled": True})
        t_resp2 = await client.post("/incidents/trigger", json={"scenario": "glare_ambiguous"})
        assert t_resp2.status_code == 202
        inc_id2 = t_resp2.json()["incident_id"]

        for _ in range(40):
            await asyncio.sleep(0.3)
            task = orchestrator.active_tasks.get(inc_id2)
            if task is None or task.done():
                break

        inc_on = await db.get_incident_by_id(inc_id2)
        assert inc_on is not None
        # With memory on, prior suppresses it to REJECTED!
        assert inc_on.state == "REJECTED"
        assert "Suppressed by memory" in inc_on.reasoning
        assert inc_on.memory is not None
        assert inc_on.memory.get("suppressed_by_memory") is True
