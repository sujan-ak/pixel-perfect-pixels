import asyncio
import time
from fastapi.testclient import TestClient
from main import app

def run_tests():
    with TestClient(app) as client:
        print("--- Test 1: Health Check ---")
        resp = client.get("/health")
        assert resp.status_code == 200, resp.text
        print("Health:", resp.json())

        print("\n--- Test 2: Governor Sensitivity & Pause ---")
        resp = client.post("/governor/sensitivity", json={"sensitivity": 0.85})
        assert resp.status_code == 200, resp.text
        print("Sensitivity updated:", resp.json())

        resp = client.post("/governor/pause", json={"paused": True})
        assert resp.status_code == 200, resp.text
        print("Pause updated:", resp.json())

        resp = client.post("/governor/pause", json={"paused": False})
        assert resp.status_code == 200, resp.text
        print("Unpause updated:", resp.json())

        print("\n--- Test 3: Trigger crash_zone04 ---")
        resp = client.post("/incidents/trigger", json={"scenario": "crash_zone04"})
        assert resp.status_code == 202, resp.text
        data = resp.json()
        incident_id = data.get("incident_id")
        print(f"Triggered scenario -> assigned incident_id: {incident_id}")
        time.sleep(3)

        print("\n--- Test 4: Operator Override Reject ---")
        resp = client.post(f"/incidents/{incident_id}/override-reject", json={"reason": "Live operator veto"})
        assert resp.status_code == 200, resp.text
        rejected_data = resp.json()
        print("Override reject result:", rejected_data)
        assert rejected_data.get("status").lower() == "rejected"

        print("\n--- Test 5: Verify Hash Chain Integrity ---")
        resp = client.get("/audit/verify")
        assert resp.status_code == 200, resp.text
        verify_res = resp.json()
        print("Ledger verification:", verify_res)
        assert verify_res.get("valid") is True

        print("\n--- Test 6: Check History contains incident ---")
        resp = client.get("/incidents/history")
        assert resp.status_code == 200, resp.text
        history = resp.json()
        print(f"Incident history count: {len(history)}")
        assert len(history) >= 1

        print("\n==============================================")
        print(">>> ALL E2E INTEGRATION TESTS PASSED CLEANLY! <<<")
        print("==============================================")

if __name__ == "__main__":
    run_tests()
