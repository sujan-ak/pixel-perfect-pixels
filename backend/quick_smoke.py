import time
import requests
import json
import sqlite3
import sys

BASE_URL = "http://localhost:8000"

print("=========================================================")
print("RUNNING SMOKE TEST: crash_zone04 through to CLOSED")
print("=========================================================")

# 1. Trigger crash_zone04
print("\n[1] Triggering crash_zone04 ...")
resp = requests.post(f"{BASE_URL}/incidents/trigger", json={"scenario": "crash_zone04"})
if resp.status_code != 202:
    print(f"Trigger failed with status {resp.status_code}: {resp.text}")
    sys.exit(1)

incident_id = resp.json()["incident_id"]
print(f" -> Assigned Incident ID: {incident_id}")

# 2. Wait for RESPONSE_PROPOSED
print("\n[2] Waiting for dual-agent adjudication (RESPONSE_PROPOSED) ...")
t0 = time.time()
reached_proposed = False
while time.time() - t0 < 20.0:
    con = sqlite3.connect("aurashield.db")
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
    con.close()
    if row:
        st = row["state"]
        print(f"    State: {st} | Corr: {row['corroborator_score']} | Skep: {row['skeptic_score']} | Conf: {row['confidence']}")
        if st == "RESPONSE_PROPOSED":
            reached_proposed = True
            break
        elif st == "REJECTED":
            print("ERROR: Incident was rejected instead of RESPONSE_PROPOSED!")
            sys.exit(1)
    time.sleep(1.0)

if not reached_proposed:
    print("ERROR: Timed out waiting for RESPONSE_PROPOSED.")
    sys.exit(1)

# 3. Approve Dispatch
print(f"\n[3] Approving dispatch for {incident_id} ...")
app_resp = requests.post(f"{BASE_URL}/incidents/{incident_id}/approve")
print(f" -> Approve status: {app_resp.status_code}")
if app_resp.status_code != 200:
    print(f"Approve failed: {app_resp.text}")
    sys.exit(1)

# 4. Wait for post-approval pipeline to reach CLOSED
print("\n[4] Waiting for post-approval pipeline to reach CLOSED ...")
t1 = time.time()
reached_closed = False
while time.time() - t1 < 20.0:
    con = sqlite3.connect("aurashield.db")
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
    con.close()
    if row:
        st = row["state"]
        print(f"    Post-approval state: {st}")
        if st == "CLOSED":
            reached_closed = True
            break
    time.sleep(1.0)

if not reached_closed:
    print("ERROR: Timed out waiting for CLOSED.")
    sys.exit(1)

print("\n=========================================================")
print(f">>> SMOKE TEST SUCCESS: {incident_id} reached CLOSED successfully! <<<")
print("=========================================================")
