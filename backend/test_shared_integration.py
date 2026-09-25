import asyncio
import time
from fastapi.testclient import TestClient
from main import app

def run_integration_test():
    with TestClient(app) as client:
        print("\n========================================================")
        print(">>> STARTING FULL SHARED BACKEND INTEGRATION TEST <<<")
        print("========================================================")

        # 1. Health & assets check
        print("\n[STEP 1] Testing /health and /api/assets...")
        r = client.get("/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        print(f" Health OK: {r.json()}")

        r = client.get("/api/assets")
        assert r.status_code == 200, f"Assets check failed: {r.text}"
        assets = r.json()
        print(f" Assets response: {assets}")

        # 2. Put responder on duty
        print("\n[STEP 2] Setting responder device ON DUTY...")
        r = client.post("/api/responder_device", json={"enabled": True})
        assert r.status_code == 200, f"Failed to enable responder device: {r.text}"
        resp_state = r.json()
        assert resp_state.get("responder_device", {}).get("enabled") is True
        print(f" Responder on duty confirmed: {resp_state['responder_device']}")

        # 3. Trigger crash_zone04
        print("\n[STEP 3] Triggering crash_zone04 incident...")
        r = client.post("/incidents/trigger", json={"scenario": "crash_zone04"})
        assert r.status_code == 202, f"Failed to trigger incident: {r.text}"
        inc_data = r.json()
        incident_id = inc_data["incident_id"]
        print(f" Incident triggered -> id: {incident_id}")

        # Wait for verification pipeline
        print(" Waiting for LLM verification and response plan generation (polling)...")
        current_state = None
        for _ in range(20):
            time.sleep(1.0)
            r = client.get("/api/state?client=responder")
            s = r.json()
            if s.get("incident"):
                current_state = s["incident"]["state"]
                print(f"   Poll state: {current_state}")
                if current_state == "RESPONSE_PROPOSED":
                    break

        # 4. Check state before approval
        print("\n[STEP 4] Mobile polls state before approval...")
        assert current_state in ("VERIFIED", "RESPONSE_PROPOSED"), f"Unexpected pre-approval state: {current_state}"

        # 5. Operator approves incident
        print("\n[STEP 5] Control Room Operator approves incident...")
        r = client.post(f"/incidents/{incident_id}/approve")
        assert r.status_code == 200, f"Approve failed: {r.text}"
        approve_data = r.json()
        print(f" Operator approval result: {approve_data['status']}")

        # Give 0.5s for broadcast and async notification
        time.sleep(0.5)

        # 6. Mobile polls incoming dispatch packet
        print("\n[STEP 6] Mobile receives COORDINATION_IN_PROGRESS dispatch packet...")
        r = client.get("/api/state?client=responder")
        assert r.status_code == 200
        s = r.json()
        inc = s["incident"]
        assert inc["state"] == "COORDINATION_IN_PROGRESS", f"Expected COORDINATION_IN_PROGRESS, got {inc['state']}"
        assert inc["active_plan"] is not None, "active_plan should be populated for responder"
        print(f" Mobile received dispatch to: {inc['active_plan']['hospital_name']}")
        print(f" Severity: {inc['active_plan']['severity']}, Priority junctions: {inc['active_plan']['junction_ids']}")
        print(f" Ack deadline: {s.get('ack_deadline_ms')}")

        # 7. Mobile acknowledges dispatch
        print("\n[STEP 7] Mobile driver slides to ACKNOWLEDGE...")
        r = client.post("/api/ack", json={"source": "responder_iphone", "channel": "responder_device"})
        assert r.status_code == 200, f"Ack failed: {r.text}"
        ack_res = r.json()
        assert ack_res["incident"]["state"] == "ACKNOWLEDGED", f"Expected ACKNOWLEDGED, got {ack_res['incident']['state']}"
        print(f" State updated to ACKNOWLEDGED in shared database!")

        # 8. Mobile reports EN_ROUTE
        print("\n[STEP 8] Mobile reports status: EN_ROUTE...")
        r = client.post("/api/field_status", json={"source": "responder_iphone", "status": "EN_ROUTE"})
        assert r.status_code == 200, f"Field status EN_ROUTE failed: {r.text}"
        s = r.json()
        assert s["incident"]["field_status"] == "EN_ROUTE"
        print(f" Shared database field_status updated to EN_ROUTE")

        # 9. Mobile reports ON_SCENE
        print("\n[STEP 9] Mobile reports status: ON_SCENE...")
        r = client.post("/api/field_status", json={"source": "responder_iphone", "status": "ON_SCENE"})
        assert r.status_code == 200, f"Field status ON_SCENE failed: {r.text}"
        s = r.json()
        assert s["incident"]["field_status"] == "ON_SCENE"
        print(f" Shared database field_status updated to ON_SCENE")

        # 10. Mobile reports HANDED_OVER
        print("\n[STEP 10] Mobile reports status: HANDED_OVER...")
        r = client.post("/api/field_status", json={"source": "responder_iphone", "status": "HANDED_OVER"})
        assert r.status_code == 200, f"Field status HANDED_OVER failed: {r.text}"
        s = r.json()
        assert s["incident"]["field_status"] == "HANDED_OVER"
        print(f" Shared database field_status updated to HANDED_OVER")

        # 11. Verify Audit Ledger records all key events
        print("\n[STEP 11] Verifying Audit Ledger entries and cryptographic integrity...")
        r = client.get("/audit/history")
        assert r.status_code == 200
        audit_entries = r.json()
        actions = [e["action"] for e in audit_entries]
        print(f" Total audit log entries recorded: {len(actions)}")

        # Check notification entries
        has_police = any("POLICE_NOTIFICATION_SENT" in a for a in actions)
        has_hospital = any("HOSPITAL_NOTIFICATION_SENT" in a for a in actions)
        has_ack = any("RESPONDER_ACKNOWLEDGED" in a for a in actions)
        has_en_route = any("RESPONDER_EN_ROUTE" in a for a in actions)
        has_on_scene = any("RESPONDER_ON_SCENE" in a for a in actions)
        has_handed_over = any("RESPONDER_HANDED_OVER" in a for a in actions)

        print(f" POLICE_NOTIFICATION_SENT recorded: {has_police}")
        print(f" HOSPITAL_NOTIFICATION_SENT recorded: {has_hospital}")
        print(f" RESPONDER_ACKNOWLEDGED recorded: {has_ack}")
        print(f" RESPONDER_EN_ROUTE recorded: {has_en_route}")
        print(f" RESPONDER_ON_SCENE recorded: {has_on_scene}")
        print(f" RESPONDER_HANDED_OVER recorded: {has_handed_over}")

        assert has_police, "Missing POLICE_NOTIFICATION_SENT in audit ledger!"
        assert has_hospital, "Missing HOSPITAL_NOTIFICATION_SENT in audit ledger!"
        assert has_ack, "Missing RESPONDER_ACKNOWLEDGED in audit ledger!"
        assert has_en_route, "Missing RESPONDER_EN_ROUTE in audit ledger!"
        assert has_on_scene, "Missing RESPONDER_ON_SCENE in audit ledger!"
        assert has_handed_over, "Missing RESPONDER_HANDED_OVER in audit ledger!"

        # 12. Verify Hash Chain
        r = client.get("/audit/verify")
        assert r.status_code == 200
        verify = r.json()
        print(f" Ledger cryptographic integrity: {verify}")
        assert verify["valid"] is True, "Audit hash chain verification failed!"

        print("\n==================================================================")
        print(">>> ALL 12 INTEGRATION CRITERIA PASSED WITH ZERO ERRORS! <<<")
        print("==================================================================")

if __name__ == "__main__":
    run_integration_test()
