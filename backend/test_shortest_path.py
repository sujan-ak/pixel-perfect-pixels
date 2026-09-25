import time
from fastapi.testclient import TestClient
from core.city import CityTwin, plan_route, choose_hospital
from database.interface import Incident
from main import app, orchestrator

def test_dijkstra_direct():
    print("\n--- TEST 1: Direct CityTwin Dijkstra Shortest Path ---")
    twin = CityTwin()

    # 1. Standard path to H_ALPHA
    path = twin.shortest_path(twin.ambulance_node, "H_ALPHA")
    cost = twin.path_cost(path)
    juncs = [j for j in twin.junctions_on(path) if twin.junctions[j].controller_online]
    eta = int(round(cost / 8.0))

    print(f"Standard path to H_ALPHA: {path}")
    print(f"Path cost: {cost}m (expected ~1840m)")
    print(f"ETA: {eta}s (expected ~230s)")
    print(f"Junctions: {juncs} (expected ['J1', 'J2', 'J3', 'J4'])")

    assert path[0] == "D_AMB", "Route must start at ambulance node D_AMB"
    assert path[-1] == "H_ALPHA", "Route must terminate at destination H_ALPHA"
    assert path == ["D_AMB", "N_CAM4", "J1", "J2", "J3", "J4", "H_ALPHA"]
    assert cost == 1840, f"Expected 1840m, got {cost}"
    assert eta == 230, f"Expected 230s, got {eta}"
    assert juncs == ["J1", "J2", "J3", "J4"]
    print(" Direct Dijkstra Test 1: PASSED")

    # 2. Dynamic rerouting avoiding J2
    print("\n--- TEST 2: Dynamic Dijkstra Recalculation (Avoid J2) ---")
    twin.set_controller_online("J2", False)
    avoid = twin.offline_junctions()
    print(f"Offline junctions to avoid: {avoid}")
    assert "J2" in avoid

    path_avoid = twin.shortest_path(twin.ambulance_node, "H_ALPHA", avoid=avoid)
    cost_avoid = twin.path_cost(path_avoid)
    juncs_avoid = [j for j in twin.junctions_on(path_avoid) if twin.junctions[j].controller_online]
    eta_avoid = int(round(cost_avoid / 8.0))

    print(f"Avoidance path to H_ALPHA: {path_avoid}")
    print(f"Avoidance cost: {cost_avoid}m")
    print(f"Avoidance junctions: {juncs_avoid}")

    assert "J2" not in path_avoid, "Route must NOT contain offline junction J2"
    assert path_avoid == ["D_AMB", "N_CAM4", "J1", "J5", "J3", "J4", "H_ALPHA"]
    assert cost_avoid == 2785, f"Expected 2785m, got {cost_avoid}"
    assert eta_avoid == 348
    print(" Dynamic Dijkstra Avoidance Test 2: PASSED")

    # 3. Dynamic hospital fallback when trauma bays full
    print("\n--- TEST 3: Dynamic Hospital Fallback ---")
    twin.reset()
    twin.hospitals["H_ALPHA"].bays_free = 0
    selected_hosp = choose_hospital(twin, "CRITICAL")
    print(f"Hospital selected when H_ALPHA full: {selected_hosp}")
    assert selected_hosp == "H_BETA"

    route_beta = plan_route(twin, selected_hosp)
    print(f"Path to fallback hospital H_BETA: {route_beta['path']}")
    assert route_beta["path"][-1] == "H_BETA"
    assert route_beta["path"] == ["D_AMB", "N_CAM4", "J1", "J5", "J6", "H_BETA"]
    print(" Dynamic Hospital Fallback Test 3: PASSED")


def test_orchestrator_build_dispatch_plan():
    print("\n--- TEST 4: Orchestrator build_dispatch_plan() Dynamic Calculation ---")
    orchestrator.twin.reset()
    mock_inc = Incident(
        id="inc_test_99",
        state="VERIFIED",
        zone="Zone 04",
        scenario="crash_zone04",
        corroborator_score=0.92,
        skeptic_score=0.15,
        fused_score=0.77,
        confidence=0.95,
        reasoning="Test crash",
        media_file="scenario_a_collision.mp4",
        timestamp="2026-09-25T12:00:00Z",
    )

    plan = orchestrator.build_dispatch_plan(mock_inc)
    print(f"Generated Dispatch Plan: {plan}")

    assert plan["route_node_ids"] == ["D_AMB", "N_CAM4", "J1", "J2", "J3", "J4", "H_ALPHA"]
    assert plan["junction_ids"] == ["J1", "J2", "J3", "J4"]
    assert plan["eta_seconds"] == 230
    assert plan["hospital_id"] == "H_ALPHA"
    assert plan["severity"] == "CRITICAL"
    print(" Orchestrator build_dispatch_plan() Test 4: PASSED")


def test_api_state_exposes_dijkstra_route():
    print("\n--- TEST 5: API /api/state Exposes Dijkstra Route to Mobile ---")
    with TestClient(app) as client:
        # Put responder on duty
        client.post("/api/responder_device", json={"enabled": True})

        # Trigger incident
        r = client.post("/incidents/trigger", json={"scenario": "crash_zone04"})
        assert r.status_code == 202
        inc_id = r.json()["incident_id"]

        # Wait for verification
        for _ in range(15):
            time.sleep(1.0)
            st = client.get("/api/state?client=responder").json()
            if st.get("incident") and st["incident"]["state"] == "RESPONSE_PROPOSED":
                break

        # Approve incident to trigger dispatch packet
        r = client.post(f"/incidents/{inc_id}/approve")
        assert r.status_code == 200

        # Poll mobile state
        res = client.get("/api/state?client=responder")
        assert res.status_code == 200
        state = res.json()
        inc = state["incident"]
        assert inc is not None
        plan = inc["active_plan"]
        assert plan is not None

        print(f"Mobile received route_node_ids: {plan['route_node_ids']}")
        print(f"Mobile received junction_ids: {plan['junction_ids']}")
        print(f"Mobile received eta_seconds: {plan['eta_seconds']}")

        assert plan["route_node_ids"] == ["D_AMB", "N_CAM4", "J1", "J2", "J3", "J4", "H_ALPHA"]
        assert plan["junction_ids"] == ["J1", "J2", "J3", "J4"]
        assert plan["eta_seconds"] == 230

        # Verify all node IDs exist in twin.nodes so mobile IncidentMap.tsx can resolve coordinates
        twin_node_ids = {n["id"] for n in state["twin"]["nodes"]}
        twin_node_ids.update(j["id"] for j in state["twin"]["junctions"])
        twin_node_ids.update(h["id"] for h in state["twin"]["hospitals"])

        for nid in plan["route_node_ids"]:
            assert nid in twin_node_ids, f"Node {nid} missing in digital twin nodes!"

        print(" All route node IDs successfully verified in digital twin coordinates!")
        print(" Mobile API State Exposure Test 5: PASSED")


if __name__ == "__main__":
    test_dijkstra_direct()
    test_orchestrator_build_dispatch_plan()
    test_api_state_exposes_dijkstra_route()
    print("\n==============================================================")
    print(">>> ALL 5 SHORTEST-PATH VERIFICATION TESTS PASSED CLEANLY! <<<")
    print("==============================================================")
