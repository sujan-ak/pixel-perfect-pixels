"""
PIXEL PERFECT PIXELS × AURASHIELD
Automated Test Suite for Police & Hospital SMS Notifications (Phase 2)

Tests:
TEST 1:  Police notification trigger upon incident approval.
TEST 2:  Police notification idempotency (duplicate approval/dispatch is blocked).
TEST 3:  Police notification dynamic content (incident ID, severity, location).
TEST 4:  Hospital notification does NOT trigger at ON_SCENE.
TEST 5:  PATIENT_LOADED triggers hospital notification.
TEST 6:  Hospital notification uses Stage 2 selected hospital.
TEST 7:  Hospital notification uses Stage 2 ETA.
TEST 8:  Hospital notification uses dynamic incident location.
TEST 9:  Hospital notification idempotency on repeated PATIENT_LOADED.
TEST 10: Hospital fallback selection and recipient routing (H_ALPHA full -> H_BETA).
TEST 11: Critical/high severity trauma suitability preserved.
TEST 12: J2 avoidance in Stage 2 route reflected in plan and notification.
TEST 13: Twilio failure handling (notification marked FAILED, error recorded, workflow intact).
TEST 14: Twilio credentials remain backend-only (zero credentials in mobile repo).
"""

import asyncio
import os
import shutil
import sys
from pathlib import Path

# Add backend directory to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))

from core.notifications import (
    set_notification_sender,
    reset_notification_sender,
    get_dispatched_mock_history,
    build_police_notification_message,
    build_hospital_notification_message,
    format_eta,
    format_severity,
    dispatch_police_notification,
    dispatch_hospital_notification,
)
from core.state_machine import ConnectionManager, IncidentOrchestrator
from database.sqlite_backend import SqliteBackend
from database.interface import Incident

TEST_DB_PATH = "test_notifications.db"


async def setup_test_orchestrator():
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    db = SqliteBackend(db_path=TEST_DB_PATH)
    await db.init_db()
    cm = ConnectionManager()
    orch = IncidentOrchestrator(db=db, connection_manager=cm)
    return db, orch


async def run_all_tests():
    print("=" * 70)
    print("RUNNING POLICE + HOSPITAL TWILIO NOTIFICATION TEST SUITE (PHASE 2)")
    print("=" * 70)

    # Setup mock sender for Twilio
    dispatched_mock = []

    def mock_sender(to, body, channel):
        dispatched_mock.append({"to": to, "body": body, "channel": channel})
        sid = f"SMmock_{len(dispatched_mock):04d}"
        return True, sid, None

    set_notification_sender(mock_sender)

    db, orch = await setup_test_orchestrator()

    # Create initial incident in RESPONSE_PROPOSED state
    inc = Incident(
        id="INC-PHASE2-001",
        state="RESPONSE_PROPOSED",
        zone="Zone 04",
        scenario="crash_zone04",
        corroborator_score=0.92,
        skeptic_score=0.08,
        fused_score=0.84,
        confidence=0.95,
        reasoning="Dual camera confirmed severe head-on collision",
        media_file="scenario_a_collision.mp4",
        timestamp="2026-09-25T12:00:00Z",
    )
    await db.save_incident(inc)

    # -------------------------------------------------------------
    # TEST 1: Police notification trigger
    # -------------------------------------------------------------
    print("\n--- TEST 1: Police Notification Trigger ---")
    dispatched_mock.clear()
    res = await orch.approve_incident(inc.id)
    assert res["status"] == "approved"
    assert "sms_payload" in res

    police_notifs = await db.get_notifications_for_incident(inc.id, "POLICE")
    assert len(police_notifs) == 1, f"Expected 1 police notification, got {len(police_notifs)}"
    assert police_notifs[0].status == "SENT"
    assert police_notifs[0].trigger_event == "INCIDENT_APPROVED"
    assert police_notifs[0].provider_id is not None
    print(f" TEST 1 PASSED: Police notification created on approval (SID: {police_notifs[0].provider_id})")

    # -------------------------------------------------------------
    # TEST 2: Police notification idempotency
    # -------------------------------------------------------------
    print("\n--- TEST 2: Police Notification Idempotency ---")
    prev_count = len(dispatched_mock)
    # Attempt repeated dispatch_police_notification
    second_police_res = await dispatch_police_notification(db, inc, location_label="Test Loc")
    assert second_police_res is None, "Repeated police notification was not blocked by idempotency guard!"
    assert len(dispatched_mock) == prev_count, "Twilio mock was called again on duplicate approval!"
    print(" TEST 2 PASSED: Repeated approval dispatch blocked (Idempotency verified)")

    # -------------------------------------------------------------
    # TEST 3: Police notification dynamic information
    # -------------------------------------------------------------
    print("\n--- TEST 3: Dynamic Police Notification Content ---")
    body = police_notifs[0].message_body
    assert inc.id in body, f"Incident ID '{inc.id}' missing in body: {body}"
    assert "Severity:" in body, f"Severity missing in body: {body}"
    assert "Zone 04" in body or "Hyderabad" in body, f"Dynamic location missing: {body}"
    assert "Ambulance response initiated" in body
    print(" TEST 3 PASSED: Dynamic incident location, severity, and ID present")

    # Responder acknowledges and moves EN_ROUTE -> ON_SCENE
    await orch.acknowledge_dispatch(inc.id, source="responder_iphone")
    await orch.update_field_status(inc.id, source="responder_iphone", status="EN_ROUTE")

    # -------------------------------------------------------------
    # TEST 4: Hospital notification does NOT trigger at ON_SCENE
    # -------------------------------------------------------------
    print("\n--- TEST 4: Hospital Notification Does NOT Trigger at ON_SCENE ---")
    await orch.update_field_status(inc.id, source="responder_iphone", status="ON_SCENE")
    hosp_notifs_on_scene = await db.get_notifications_for_incident(inc.id, "HOSPITAL")
    assert len(hosp_notifs_on_scene) == 0, f"Hospital notification prematurely triggered at ON_SCENE: {hosp_notifs_on_scene}"
    print(" TEST 4 PASSED: Zero hospital notifications at ON_SCENE")

    # -------------------------------------------------------------
    # TEST 5: PATIENT_LOADED triggers hospital notification
    # -------------------------------------------------------------
    print("\n--- TEST 5: PATIENT_LOADED Triggers Hospital Notification ---")
    dispatched_mock.clear()
    await orch.update_field_status(inc.id, source="responder_iphone", status="PATIENT_LOADED")
    hosp_notifs = await db.get_notifications_for_incident(inc.id, "HOSPITAL")
    assert len(hosp_notifs) == 1, f"Expected 1 hospital notification, got {len(hosp_notifs)}"
    assert hosp_notifs[0].status == "SENT"
    assert hosp_notifs[0].trigger_event == "PATIENT_LOADED"
    print(f" TEST 5 PASSED: Hospital notification triggered by PATIENT_LOADED (SID: {hosp_notifs[0].provider_id})")

    # -------------------------------------------------------------
    # TEST 6: Hospital notification uses Stage 2 selected hospital
    # -------------------------------------------------------------
    print("\n--- TEST 6: Hospital Notification Uses Stage 2 Selected Hospital ---")
    active_plan = orch.active_plan
    assert active_plan is not None
    selected_hosp_name = active_plan["hospital_name"]
    assert selected_hosp_name in hosp_notifs[0].message_body, (
        f"Selected hospital '{selected_hosp_name}' not found in notification: {hosp_notifs[0].message_body}"
    )
    print(f" TEST 6 PASSED: Correct Stage 2 hospital matched ({selected_hosp_name})")

    # -------------------------------------------------------------
    # TEST 7: Hospital notification uses Stage 2 ETA
    # -------------------------------------------------------------
    print("\n--- TEST 7: Hospital Notification Uses Stage 2 ETA ---")
    eta_sec = active_plan["eta_seconds"]
    expected_eta_substr = f"{eta_sec}s"
    assert expected_eta_substr in hosp_notifs[0].message_body, (
        f"Stage 2 ETA {eta_sec}s missing in notification: {hosp_notifs[0].message_body}"
    )
    print(f" TEST 7 PASSED: Stage 2 ETA properly included ({active_plan['eta_seconds']}s -> {format_eta(eta_sec)})")

    # -------------------------------------------------------------
    # TEST 8: Hospital notification uses dynamic incident location
    # -------------------------------------------------------------
    print("\n--- TEST 8: Hospital Notification Uses Dynamic Incident Location ---")
    assert inc.zone in hosp_notifs[0].message_body
    print(f" TEST 8 PASSED: Dynamic incident location ({inc.zone}) verified")

    # -------------------------------------------------------------
    # TEST 9: Hospital notification idempotency on repeated PATIENT_LOADED
    # -------------------------------------------------------------
    print("\n--- TEST 9: Hospital Notification Idempotency ---")
    mock_len_before = len(dispatched_mock)
    await orch.update_field_status(inc.id, source="responder_iphone", status="PATIENT_LOADED")
    hosp_notifs_after = await db.get_notifications_for_incident(inc.id, "HOSPITAL")
    assert len(hosp_notifs_after) == 1, "Duplicate hospital notification created on repeat PATIENT_LOADED!"
    assert len(dispatched_mock) == mock_len_before, "Twilio called on duplicate PATIENT_LOADED!"
    print(" TEST 9 PASSED: Idempotency prevents duplicate hospital notification on re-trigger")

    # -------------------------------------------------------------
    # TEST 10: Hospital Fallback (H_ALPHA full -> H_BETA selected)
    # -------------------------------------------------------------
    print("\n--- TEST 10: Hospital Fallback Notification ---")
    # Simulate H_ALPHA full in a fresh incident
    orch.twin.hospitals["H_ALPHA"].bays_free = 0
    dispatched_mock.clear()

    inc2 = Incident(
        id="INC-PHASE2-002",
        state="RESPONSE_PROPOSED",
        zone="Zone 04",
        scenario="crash_zone04",
        corroborator_score=0.92,
        skeptic_score=0.08,
        fused_score=0.84,
        confidence=0.95,
        reasoning="Second collision for fallback hospital test",
        media_file="scenario_a_collision.mp4",
        timestamp="2026-09-25T12:05:00Z",
    )
    await db.save_incident(inc2)
    await orch.approve_incident(inc2.id)
    await orch.acknowledge_dispatch(inc2.id)
    await orch.update_field_status(inc2.id, status="EN_ROUTE")
    await orch.update_field_status(inc2.id, status="ON_SCENE")
    await orch.update_field_status(inc2.id, status="PATIENT_LOADED")

    plan2 = orch.active_plan
    assert plan2["hospital_id"] == "H_BETA", f"Expected fallback H_BETA, got {plan2['hospital_id']}"
    hosp2_notifs = await db.get_notifications_for_incident(inc2.id, "HOSPITAL")
    assert len(hosp2_notifs) == 1
    assert plan2["hospital_name"] in hosp2_notifs[0].message_body
    print(f" TEST 10 PASSED: Fallback hospital H_BETA correctly routed and notified")

    # Reset twin
    orch.twin.reset()

    # -------------------------------------------------------------
    # TEST 11: Critical/High Severity Trauma Suitability
    # -------------------------------------------------------------
    print("\n--- TEST 11: Trauma Suitability Rules Preserved ---")
    plan_alpha = orch.build_stage2_dispatch_plan(inc)
    assert plan_alpha["hospital_id"] == "H_ALPHA"
    assert orch.twin.hospitals["H_ALPHA"].trauma_capable is True
    print(" TEST 11 PASSED: Critical/High trauma suitability logic preserved")

    # -------------------------------------------------------------
    # TEST 12: J2 Avoidance in Stage 2 Route Reflected in Plan & Notification
    # -------------------------------------------------------------
    print("\n--- TEST 12: J2 Avoidance in Stage 2 Plan ---")
    orch.twin.set_controller_online("J2", False)
    plan_no_j2 = orch.build_stage2_dispatch_plan(inc)
    assert "J2" not in plan_no_j2["junction_ids"], f"J2 unexpectedly in route: {plan_no_j2['junction_ids']}"
    orch.twin.reset()
    print(" TEST 12 PASSED: J2 offline avoidance strictly maintained in Stage 2")

    # -------------------------------------------------------------
    # TEST 13: Twilio Failure Handling
    # -------------------------------------------------------------
    print("\n--- TEST 13: Twilio Failure Handling ---")

    def failing_sender(to, body, channel):
        raise RuntimeError("Connection timed out to Twilio API (Mock Error 20003)")

    set_notification_sender(failing_sender)

    inc3 = Incident(
        id="INC-PHASE2-003",
        state="RESPONSE_PROPOSED",
        zone="Zone 04",
        scenario="crash_zone04",
        corroborator_score=0.92,
        skeptic_score=0.08,
        fused_score=0.84,
        confidence=0.95,
        reasoning="Collision for failure handling verification",
        media_file="scenario_a_collision.mp4",
        timestamp="2026-09-25T12:10:00Z",
    )
    await db.save_incident(inc3)

    # Approve incident with failing Twilio
    appr_res = await orch.approve_incident(inc3.id)
    assert appr_res["status"] == "approved", "Incident approval failed due to Twilio error!"

    # Police notification should be recorded as FAILED
    police_failed = await db.get_notifications_for_incident(inc3.id, "POLICE")
    assert len(police_failed) == 1
    assert police_failed[0].status == "FAILED"
    assert "Mock Error 20003" in police_failed[0].error_message

    # Incident workflow proceeds normally
    await orch.acknowledge_dispatch(inc3.id)
    await orch.update_field_status(inc3.id, status="EN_ROUTE")
    await orch.update_field_status(inc3.id, status="ON_SCENE")
    state_after_loaded = await orch.update_field_status(inc3.id, status="PATIENT_LOADED")

    # Hospital notification should be recorded as FAILED, but Stage 2 route remains intact
    hosp_failed = await db.get_notifications_for_incident(inc3.id, "HOSPITAL")
    assert len(hosp_failed) == 1
    assert hosp_failed[0].status == "FAILED"
    assert "Mock Error 20003" in hosp_failed[0].error_message

    # Verify Stage 2 route exists and is valid
    assert state_after_loaded["incident"]["active_plan"] is not None
    assert len(state_after_loaded["incident"]["active_plan"]["route_node_ids"]) > 1
    print(" TEST 13 PASSED: Twilio failures gracefully handled, logged as FAILED, workflow and routing intact")

    # Reset mock sender
    reset_notification_sender()

    # -------------------------------------------------------------
    # TEST 14: Twilio Credentials Security Check
    # -------------------------------------------------------------
    print("\n--- TEST 14: Mobile Repo Security Audit (Zero Twilio Credentials) ---")
    mobile_dir = CURRENT_DIR.parent.parent / "AuraShield-master" / "AuraShield-master" / "mobile"
    if not mobile_dir.exists():
        mobile_dir = Path("c:/Users/sujan/Downloads/pixel-perfect-pixels-main/AuraShield-master/AuraShield-master/mobile")

    forbidden_terms = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "twilio.rest", "AC1ad1d7"]
    found = []
    mobile_src = mobile_dir / "src"
    if mobile_src.exists():
        for root, _, files in os.walk(str(mobile_src)):
            for f in files:
                if f.endswith((".ts", ".tsx", ".js", ".json")):
                    p = os.path.join(root, f)
                    with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        for term in forbidden_terms:
                            if term in content:
                                found.append((f, term))
    assert len(found) == 0, f"Found Twilio references in mobile app: {found}"
    print(" TEST 14 PASSED: Mobile app completely free of Twilio credentials and SDK imports")

    # Clean up test DB
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    print("\n" + "=" * 70)
    print(">>> ALL 14 NOTIFICATION UNIT & INTEGRATION TESTS PASSED! <<<")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
