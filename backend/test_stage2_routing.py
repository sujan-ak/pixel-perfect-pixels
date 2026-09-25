"""
Comprehensive Stage 2 Ambulance Routing & Mobile Map Compatibility Test Suite
Tests 1 through 16 as required by the integration audit specification.
"""
import asyncio
import os
import json
import time
from fastapi.testclient import TestClient
from core.city import CityTwin, plan_route, choose_hospital
from core.state_machine import IncidentOrchestrator, ConnectionManager, LEGAL_TRANSITIONS
from database.interface import Incident
from database.sqlite_backend import SqliteBackend
from main import app, orchestrator, db

def run_all_tests():
    print("==================================================================")
    print(">>> RUNNING COMPREHENSIVE STAGE 2 ROUTING & MOBILE UX TESTS <<<")
    print("==================================================================")

    twin = CityTwin()

    # TEST 1: Existing Stage 1 route still works (D_AMB -> N_CAM4 -> ... -> hospital)
    print("\n--- TEST 1: Stage 1 Route Structure ---")
    st1 = plan_route(twin, "H_ALPHA", src_node=twin.ambulance_node)
    print(f"Stage 1 path: {st1['path']}")
    assert st1["path"][0] == "D_AMB", "Stage 1 must start at D_AMB"
    assert "N_CAM4" in st1["path"], "Stage 1 must pass through accident scene N_CAM4"
    assert st1["path"][-1] == "H_ALPHA", "Stage 1 must terminate at H_ALPHA"
    assert st1["path"] == ["D_AMB", "N_CAM4", "J1", "J2", "J3", "J4", "H_ALPHA"]
    assert st1["cost_m"] == 1840
    assert st1["eta_seconds"] == 230
    print(" TEST 1: PASSED (Stage 1 route intact)")

    # TEST 2: PATIENT_LOADED triggers Stage 2 (N_CAM4 -> ... -> selected hospital)
    print("\n--- TEST 2: Stage 2 Route Structure (Patient Loaded) ---")
    st2 = plan_route(twin, "H_ALPHA", src_node="N_CAM4")
    print(f"Stage 2 path: {st2['path']}")
    assert st2["path"][0] == "N_CAM4", "Stage 2 must start at N_CAM4"
    assert "D_AMB" not in st2["path"], "Stage 2 must NOT route back to depot D_AMB"
    assert st2["path"][-1] == "H_ALPHA", "Stage 2 must terminate at hospital"
    assert st2["path"] == ["N_CAM4", "J1", "J2", "J3", "J4", "H_ALPHA"]
    assert st2["cost_m"] == 750, f"Expected 750m from N_CAM4 to H_ALPHA, got {st2['cost_m']}"
    assert st2["eta_seconds"] == 94
    print(" TEST 2: PASSED (Stage 2 route starts from N_CAM4)")

    # Async lifecycle tests for Orchestrator
    async def async_tests():
        test_db_path = "test_stage2_suite.db"
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except OSError:
                pass
        test_db = SqliteBackend(db_path=test_db_path)
        await test_db.init_db()
        cm = ConnectionManager()
        orch = IncidentOrchestrator(db=test_db, connection_manager=cm)

        mock_inc = Incident(
            id="inc_test_stage",
            state="ACKNOWLEDGED",
            zone="Zone 04",
            scenario="crash_zone04",
            corroborator_score=0.9,
            skeptic_score=0.1,
            fused_score=0.8,
            confidence=0.9,
            reasoning="Test crash",
            media_file="scene.mp4",
            timestamp="2026-09-25T12:00:00Z",
        )
        await test_db.save_incident(mock_inc)
        orch.active_plan = orch.build_dispatch_plan(mock_inc)
        assert orch.active_plan["stage"] == 1
        assert orch.active_plan["stage_label"] == "DISPATCH_TO_SCENE"

        # TEST 3: ON_SCENE alone does NOT trigger Stage 2
        print("\n--- TEST 3: ON_SCENE alone does NOT trigger Stage 2 ---")
        await orch.update_field_status(mock_inc.id, "responder_iphone", "EN_ROUTE")
        assert orch.active_plan["stage"] == 1, "EN_ROUTE must keep Stage 1"

        await orch.update_field_status(mock_inc.id, "responder_iphone", "ON_SCENE")
        assert orch.active_plan["stage"] == 1, "ON_SCENE must NOT trigger Stage 2"
        assert orch.active_plan["route_node_ids"][0] == "D_AMB", "ON_SCENE route must remain Stage 1"
        assert orch.active_plan["distance_meters"] == 1840
        print(" TEST 3: PASSED (ON_SCENE does NOT trigger Stage 2)")

        # TEST 4: PATIENT_LOADED triggers Stage 2, and duplicate call is idempotent
        print("\n--- TEST 4: PATIENT_LOADED triggers Stage 2 & Idempotency ---")
        await orch.update_field_status(mock_inc.id, "responder_iphone", "PATIENT_LOADED")
        assert orch.active_plan["stage"] == 2, "PATIENT_LOADED must trigger Stage 2"
        assert orch.active_plan["version"] == 2
        assert orch.active_plan["stage_label"] == "PICKUP_TO_HOSPITAL"
        assert orch.active_plan["route_node_ids"][0] == "N_CAM4"
        assert orch.active_plan["distance_meters"] == 750
        assert orch.active_plan["eta_seconds"] == 94
        st2_plan_id = orch.active_plan["plan_id"]
        field_updates_len = len(orch.field_updates)

        # Submit duplicate PATIENT_LOADED
        await orch.update_field_status(mock_inc.id, "responder_iphone", "PATIENT_LOADED")
        assert orch.active_plan["plan_id"] == st2_plan_id, "Duplicate PATIENT_LOADED must not change plan_id"
        assert len(orch.field_updates) == field_updates_len, "Duplicate PATIENT_LOADED must not append extra field update"
        print(" TEST 4: PASSED (PATIENT_LOADED triggers Stage 2 with strict idempotency)")

        # TEST 10: Incident coordinate equals twin.nodes["N_CAM4"].lat/lon
        print("\n--- TEST 10: Authoritative Incident Coordinate Fix ---")
        mobile_state = await orch.build_mobile_state()
        inc_state = mobile_state["incident"]
        snap = orch.twin.snapshot()
        twin_nodes = {n["id"]: n for n in snap["nodes"]}
        for h in snap["hospitals"]:
            twin_nodes[h["id"]] = h
        for j in snap["junctions"]:
            twin_nodes[j["id"]] = j
        ncam4_node = twin_nodes["N_CAM4"]
        print(f"CityTwin N_CAM4: lat={ncam4_node['lat']}, lon={ncam4_node['lon']}")
        print(f"Mobile incident: lat={inc_state['lat']}, lon={inc_state['lon']}")
        assert inc_state["lat"] == ncam4_node["lat"], f"Expected {ncam4_node['lat']}, got {inc_state['lat']}"
        assert inc_state["lon"] == ncam4_node["lon"], f"Expected {ncam4_node['lon']}, got {inc_state['lon']}"
        print(" TEST 10: PASSED (Incident coords exactly match CityTwin N_CAM4)")

        # TEST 11: Mobile receives stage=2, route_node_ids, junction_ids, eta_seconds, hospital_id, hospital_name
        print("\n--- TEST 11: Mobile Contract Verification for Stage 2 ---")
        active_plan = inc_state["active_plan"]
        assert active_plan["stage"] == 2
        assert active_plan["stage_label"] == "PICKUP_TO_HOSPITAL"
        assert active_plan["hospital_id"] == "H_ALPHA"
        assert active_plan["hospital_name"] == "Sunshine Hospital, Gachibowli"
        assert active_plan["route_node_ids"] == ["N_CAM4", "J1", "J2", "J3", "J4", "H_ALPHA"]
        assert active_plan["junction_ids"] == ["J1", "J2", "J3", "J4"]
        assert active_plan["eta_seconds"] == 94
        assert active_plan["distance_meters"] == 750
        print(" TEST 11: PASSED (Mobile contract fields complete and accurate)")

        # TEST 12: Mobile route redraws using updated route_node_ids
        print("\n--- TEST 12: Mobile Route Redraw Feasibility ---")
        coords = [
            {"latitude": twin_nodes[nid]["lat"], "longitude": twin_nodes[nid]["lon"]}
            for nid in active_plan["route_node_ids"]
        ]
        assert len(coords) == 6
        assert coords[0]["latitude"] == ncam4_node["lat"]
        assert coords[0]["longitude"] == ncam4_node["lon"]
        assert coords[-1]["latitude"] == twin_nodes["H_ALPHA"]["lat"]
        print(" TEST 12: PASSED (Route resolves to valid mobile polyline coordinates)")

        # TEST 13: "To hospital" uses dynamic selected hospital coordinates
        print("\n--- TEST 13: Dynamic 'To Hospital' Coordinates ---")
        dest_id = active_plan["hospital_id"]
        dest_node = twin_nodes[dest_id]
        hosp_list = {h["id"]: h for h in mobile_state["twin"]["hospitals"]}
        assert dest_id in hosp_list
        assert hosp_list[dest_id]["lat"] == dest_node["lat"]
        assert hosp_list[dest_id]["lon"] == dest_node["lon"]
        print(f" Dynamic hospital destination: {hosp_list[dest_id]['name']} at ({dest_node['lat']}, {dest_node['lon']})")
        print(" TEST 13: PASSED ('To hospital' coordinates are dynamic)")

        # TEST 14: Existing mobile scenarios continue working
        print("\n--- TEST 14: Mobile Scenarios in Mobile State ---")
        assert "scenarios" in mobile_state
        assert "crash_zone04" in mobile_state["scenarios"]
        print(" TEST 14: PASSED (Scenarios available for mobile)")

        # TEST 16: Legal field status transitions sequence
        print("\n--- TEST 16: Legal Field Status Transitions in LEGAL_TRANSITIONS ---")
        assert "PATIENT_LOADED" in LEGAL_TRANSITIONS["ON_SCENE"], "ON_SCENE -> PATIENT_LOADED must be legal"
        assert "HANDED_OVER" in LEGAL_TRANSITIONS["PATIENT_LOADED"], "PATIENT_LOADED -> HANDED_OVER must be legal"
        assert "CLOSED" in LEGAL_TRANSITIONS["HANDED_OVER"], "HANDED_OVER -> CLOSED must be legal"

        # Advance to HANDED_OVER
        await orch.update_field_status(mock_inc.id, "responder_iphone", "HANDED_OVER")
        assert orch.active_plan["stage"] == 2
        print(" TEST 16: PASSED (Full legal field status progression verified)")

    asyncio.run(async_tests())

    # TEST 5: Critical/high severity preserves existing trauma suitability rules
    print("\n--- TEST 5: Trauma Suitability Rules Preserved ---")
    twin.reset()
    hosp_crit = choose_hospital(twin, "CRITICAL", src_node="N_CAM4")
    assert hosp_crit == "H_ALPHA", "Critical incident must choose trauma-capable H_ALPHA"
    hosp_high = choose_hospital(twin, "HIGH", src_node="N_CAM4")
    assert hosp_high == "H_ALPHA", "High severity must choose trauma-capable H_ALPHA"
    print(" TEST 5: PASSED (Trauma suitability preserved)")

    # TEST 6: Hospital with zero available bays is excluded
    print("\n--- TEST 6: Zero Available Bays Exclusion ---")
    twin.reset()
    twin.hospitals["H_ALPHA"].bays_free = 0
    hosp_full = choose_hospital(twin, "CRITICAL", src_node="N_CAM4")
    assert hosp_full != "H_ALPHA", "Hospital with 0 bays must be excluded"
    assert hosp_full == "H_BETA", "Fallback to H_BETA when H_ALPHA has 0 bays"
    print(" TEST 6: PASSED (Full hospital excluded)")

    # TEST 7: Suitable fallback hospital selection and reachability
    print("\n--- TEST 7: Suitable Fallback Hospital Selection ---")
    twin.reset()
    twin.hospitals["H_ALPHA"].bays_free = 0
    plan_fallback = plan_route(twin, "H_BETA", src_node="N_CAM4")
    print(f"Fallback Stage 2 path to H_BETA: {plan_fallback['path']}")
    assert plan_fallback["path"][0] == "N_CAM4"
    assert plan_fallback["path"][-1] == "H_BETA"
    assert plan_fallback["path"] == ["N_CAM4", "J1", "J5", "J6", "H_BETA"]
    assert plan_fallback["cost_m"] == 1835
    print(" TEST 7: PASSED (Fallback hospital path verified)")

    # TEST 8: J2 avoidance works during Stage 2
    print("\n--- TEST 8: J2 Avoidance Detour during Stage 2 ---")
    twin.reset()
    twin.set_controller_online("J2", False)
    avoid = twin.offline_junctions()
    assert "J2" in avoid
    detour = plan_route(twin, "H_ALPHA", src_node="N_CAM4")
    print(f"Stage 2 detour path avoiding J2: {detour['path']}")
    assert "J2" not in detour["path"], "Stage 2 detour must NOT contain offline J2"
    assert detour["path"] == ["N_CAM4", "J1", "J5", "J3", "J4", "H_ALPHA"]
    assert detour["cost_m"] == 1695
    assert detour["eta_seconds"] == 212
    print(" TEST 8: PASSED (Stage 2 J2 avoidance detour verified: N_CAM4 -> J1 -> J5 -> J3 -> J4 -> H_ALPHA)")

    # TEST 9: Every Stage 2 route node exists in twin.nodes with valid lat/lon
    print("\n--- TEST 9: All Stage 2 Route Nodes Exist in Twin Nodes ---")
    twin.reset()
    snap2 = twin.snapshot()
    nodes_dict = {n["id"]: n for n in snap2["nodes"]}
    for h in snap2["hospitals"]:
        nodes_dict[h["id"]] = h
    for j in snap2["junctions"]:
        nodes_dict[j["id"]] = j
    for node_id in st2["path"]:
        assert node_id in nodes_dict, f"Node {node_id} missing from twin.nodes"
        n = nodes_dict[node_id]
        assert "lat" in n and "lon" in n, f"Node {node_id} missing lat/lon"
        assert 17.0 < n["lat"] < 18.0, f"Node {node_id} lat out of bounds"
        assert 78.0 < n["lon"] < 79.0, f"Node {node_id} lon out of bounds"
    print(" TEST 9: PASSED (All route nodes have valid coordinates)")

    # TEST 15: No Twilio credentials exist in mobile
    print("\n--- TEST 15: Security Check - No Twilio Credentials in Mobile ---")
    mobile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "AuraShield-master", "AuraShield-master", "mobile"))
    mobile_src = os.path.join(mobile_dir, "src")
    forbidden = ["AC1ad1d7", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"]
    found_violations = []
    for root, _, files in os.walk(mobile_src):
        for f in files:
            if f.endswith((".ts", ".tsx", ".js", ".json")):
                p = os.path.join(root, f)
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                    for term in forbidden:
                        if term in content:
                            found_violations.append((p, term))
    assert len(found_violations) == 0, f"Found Twilio references in mobile: {found_violations}"
    print(" TEST 15: PASSED (Zero Twilio credentials in mobile)")

    print("\n==================================================================")
    print(">>> ALL 16 AUDIT SPECIFICATION TESTS PASSED SUCCESSFULLY! <<<")
    print("==================================================================")

if __name__ == "__main__":
    run_all_tests()
