import asyncio
import os
import pytest
from unittest.mock import AsyncMock

from database.sqlite_backend import SqliteBackend
from database.interface import Incident
from core.state_machine import ConnectionManager, IncidentOrchestrator
from memory.service import memory
from memory.schemas import MemoryEvent


@pytest.mark.asyncio
async def test_learning_loop_full_flow(tmp_path):
    # Setup clean isolated DB and Ledger
    test_db_path = str(tmp_path / "test_aurashield.db")
    test_ledger_path = str(tmp_path / "test_ledger.jsonl")

    db = SqliteBackend(db_path=test_db_path)
    await db.init_db()

    conn_mgr = ConnectionManager()
    orch = IncidentOrchestrator(db=db, connection_manager=conn_mgr)

    # Re-point memory ledger to temp path
    orig_file = memory.ledger.file_path
    memory.ledger.file_path = tmp_path / "test_ledger.jsonl"
    await memory.ledger.clear()

    try:
        # Create an incident in VERIFIED state
        now_iso = "2026-09-29T12:00:00Z"
        inc = Incident(
            id="inc_999",
            state="VERIFIED",
            zone="Zone 04",
            scenario="crash_zone04",
            corroborator_score=0.88,
            skeptic_score=0.10,
            fused_score=0.78,
            confidence=0.95,
            reasoning="Severe collision detected",
            media_file="traffic_crash_zone04.mp4",
            timestamp=now_iso,
        )
        await db.save_incident(inc)

        # 1. Operator approves incident -> should retain OPERATOR_APPROVED
        res_app = await orch.approve_incident("inc_999")
        assert res_app["status"] == "approved"
        await asyncio.sleep(0.1)  # allow background retain task to execute

        events = await memory.ledger.read_all()
        app_events = [e for e in events if e.kind == "OPERATOR_APPROVED"]
        assert len(app_events) == 1
        assert app_events[0].incident_id == "inc_999"
        assert app_events[0].zone == "Zone 04"

        # 2. Responder acknowledges dispatch -> should retain DISPATCH_ACKED
        res_ack = await orch.acknowledge_dispatch("inc_999", source="unit_117", channel="mobile_app")
        await asyncio.sleep(0.1)

        events = await memory.ledger.read_all()
        ack_events = [e for e in events if e.kind == "DISPATCH_ACKED"]
        assert len(ack_events) == 1
        assert ack_events[0].incident_id == "inc_999"
        assert ack_events[0].ack_latency_ms is not None

        # 3. Update field status to PATIENT_LOADED -> Stage 2 plan
        await orch.update_field_status("inc_999", status="PATIENT_LOADED")
        assert orch.active_plan["stage"] == 2

        # 4. Update field status to HANDED_OVER -> should retain INCIDENT_CLOSED
        await orch.update_field_status("inc_999", status="HANDED_OVER")
        await asyncio.sleep(0.1)

        events = await memory.ledger.read_all()
        closed_events = [e for e in events if e.kind == "INCIDENT_CLOSED"]
        assert len(closed_events) == 1
        assert closed_events[0].incident_id == "inc_999"

        # 5. Operator override reject on a new incident -> should retain OPERATOR_OVERRIDE with cause_tag
        inc_false = Incident(
            id="inc_998",
            state="CANDIDATE",
            zone="Zone 02",
            scenario="false_alarm",
            corroborator_score=0.45,
            skeptic_score=0.35,
            fused_score=0.10,
            confidence=0.80,
            reasoning="Candidate flare",
            media_file="traffic_false_alarm.mp4",
            timestamp=now_iso,
        )
        await db.save_incident(inc_false)
        await orch.override_reject_incident("inc_998", reason="Glare from setting sun", cause_tag="glare")
        await asyncio.sleep(0.1)

        events = await memory.ledger.read_all()
        override_events = [e for e in events if e.kind == "OPERATOR_OVERRIDE"]
        assert len(override_events) == 1
        assert "glare" in override_events[0].cause_tags

        # 6. Test Hospital Learning:
        # Add 3 declines for H_ALPHA
        for i in range(3):
            await memory.retain(
                MemoryEvent(
                    event_id=f"evt_hosp_dec_{i}",
                    ts=now_iso,
                    kind="DISPATCH_DECLINED",
                    incident_id=f"inc_old_{i}",
                    zone="Zone 04",
                    scenario="crash_zone04",
                    hospital_id="H_ALPHA",
                    operator_action="DECLINE",
                )
            )
        await asyncio.sleep(0.1)

        # Plan build should now prefer H_BETA due to >=3 declines at H_ALPHA
        new_plan = orch.build_dispatch_plan(inc)
        assert new_plan["hospital_id"] == "H_BETA"
        assert "Preferring H_BETA" in new_plan["memory_note"]

    finally:
        # Restore ledger path
        memory.ledger.file_path = orig_file
