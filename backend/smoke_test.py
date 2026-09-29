import urllib.request
import json
import time
import sys

API = "http://localhost:8000"

def run_smoke():
    print("[1] Health check...")
    req = urllib.request.Request(f"{API}/health")
    health = json.loads(urllib.request.urlopen(req).read().decode())
    print(f"    Health: {health}")

    print("[2] Triggering crash_zone04...")
    req = urllib.request.Request(
        f"{API}/incidents/trigger",
        data=json.dumps({"scenario": "crash_zone04"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    res = json.loads(urllib.request.urlopen(req).read().decode())
    inc_id = res["incident_id"]
    print(f"    Assigned Incident ID: {inc_id}")

    print("[3] Polling for state progression...")
    incident = None
    for i in range(30):
        time.sleep(1.0)
        req = urllib.request.Request(f"{API}/incidents/{inc_id}")
        try:
            incident = json.loads(urllib.request.urlopen(req).read().decode())
            state = incident.get("state")
            corr = incident.get("corroborator_score")
            skep = incident.get("skeptic_score")
            print(f"    [{i+1}s] State: {state} | Corroborator: {corr} | Skeptic: {skep}")
            if state in ("RESPONSE_PROPOSED", "REJECTED"):
                break
        except Exception as e:
            print(f"    Poll error: {e}")

    if not incident or incident.get("state") != "RESPONSE_PROPOSED":
        print(f"FAILED: Incident reached {incident.get('state')} instead of RESPONSE_PROPOSED")
        sys.exit(1)

    print("[4] Calling /approve dispatch...")
    req = urllib.request.Request(
        f"{API}/incidents/{inc_id}/approve",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    app_res = json.loads(urllib.request.urlopen(req).read().decode())
    print(f"    Approve response: {app_res.get('status')}")

    print("[5] Polling through to CLOSED...")
    for i in range(15):
        time.sleep(1.0)
        req = urllib.request.Request(f"{API}/incidents/{inc_id}")
        incident = json.loads(urllib.request.urlopen(req).read().decode())
        state = incident.get("state")
        print(f"    [{i+1}s] Post-approval state: {state}")
        if state == "CLOSED":
            print("\n>>> SMOKE TEST PASSED: Core pipeline reached CLOSED successfully! <<<")
            sys.exit(0)

    print(f"Timed out waiting for CLOSED (final state: {incident.get('state')})")
    sys.exit(1)

if __name__ == "__main__":
    run_smoke()
