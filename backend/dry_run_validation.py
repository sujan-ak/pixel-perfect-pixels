import asyncio
import time
import requests
import json

BASE_URL = "http://localhost:8000"

def full_dry_run():
    print("==========================================================================")
    print("STARTING FULL END-TO-END DRY RUN (Crash + False Alarm + Dispatch + Audit)")
    print("==========================================================================\n")

    # 1. Health check
    h = requests.get(f"{BASE_URL}/health").json()
    print(f"[0] Backend Health: {h}")

    # 2. Trigger crash_zone04
    print("\n[1] Triggering Scenario: crash_zone04 ...")
    r1 = requests.post(f"{BASE_URL}/incidents/trigger", json={"scenario": "crash_zone04"})
    assert r1.status_code == 202, f"Trigger failed: {r1.text}"
    crash_id = r1.json()["incident_id"]
    print(f" -> Assigned Incident ID: {crash_id}")

    # Poll until RESPONSE_PROPOSED or REJECTED
    start_t = time.time()
    crash_incident = None
    while time.time() - start_t < 15.0:
        hist = requests.get(f"{BASE_URL}/incidents/history").json()
        # Also check database or current state
        # In history, it only appears after approved/rejected/resolved, or query history
        # Let's check via direct db or history
        import sqlite3
        con = sqlite3.connect("aurashield.db")
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM incidents WHERE id=?", (crash_id,)).fetchone()
        con.close()
        if row and row["state"] in ("RESPONSE_PROPOSED", "REJECTED"):
            crash_incident = dict(row)
            break
        time.sleep(0.5)

    print(f" -> Crash Scenario Adjudication Reached: {crash_incident.get('state')}")
    print(f"    Corroborator Score: {crash_incident.get('corroborator_score')}")
    print(f"    Skeptic Score:      {crash_incident.get('skeptic_score')}")
    print(f"    Fused Score:        {crash_incident.get('fused_score'):+.2f}")
    print(f"    Confidence:         {crash_incident.get('confidence'):.2f}")
    print(f"    Media File:         {crash_incident.get('media_file')}")

    # 3. Operator Approve Dispatch
    print(f"\n[2] Operator Action: Approving Dispatch for {crash_id} ...")
    app_res = requests.post(f"{BASE_URL}/incidents/{crash_id}/approve")
    print(f" -> Approve HTTP Status: {app_res.status_code}")
    approve_data = app_res.json()
    print(f" -> Approve Payload: {json.dumps(approve_data, indent=2)}")

    # Check Audit Log for Twilio dispatch records
    time.sleep(1.0)
    con = sqlite3.connect("aurashield.db")
    con.row_factory = sqlite3.Row
    audit_rows = con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 6").fetchall()
    con.close()
    print("\n -> Recent Audit Log Records post-approval:")
    for ar in reversed(audit_rows):
        print(f"    [{ar['id']}] {ar['actor']:<20} | {ar['action']}")

    # 4. Cooldown before false_alarm
    print("\nWaiting 3.5s cooldown before false_alarm trigger...")
    time.sleep(3.5)

    # 5. Trigger false_alarm
    print("\n[3] Triggering Scenario: false_alarm ...")
    r2 = requests.post(f"{BASE_URL}/incidents/trigger", json={"scenario": "false_alarm"})
    assert r2.status_code == 202, f"Trigger failed: {r2.text}"
    false_id = r2.json()["incident_id"]
    print(f" -> Assigned Incident ID: {false_id}")

    start_t = time.time()
    false_incident = None
    while time.time() - start_t < 15.0:
        con = sqlite3.connect("aurashield.db")
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM incidents WHERE id=?", (false_id,)).fetchone()
        con.close()
        if row and row["state"] in ("RESPONSE_PROPOSED", "REJECTED"):
            false_incident = dict(row)
            break
        time.sleep(0.5)

    print(f" -> False Alarm Adjudication Reached: {false_incident.get('state')}")
    print(f"    Corroborator Score: {false_incident.get('corroborator_score')}")
    print(f"    Skeptic Score:      {false_incident.get('skeptic_score')}")
    print(f"    Fused Score:        {false_incident.get('fused_score'):+.2f}")
    print(f"    Confidence:         {false_incident.get('confidence'):.2f}")
    print(f"    Media File:         {false_incident.get('media_file')}")

    # 6. Verify Full Cryptographic Ledger Chain Integrity
    print("\n[4] Cryptographic Audit Ledger Chain Integrity Verification:")
    verify_res = requests.get(f"{BASE_URL}/audit/verify").json()
    print(f" -> Result: {json.dumps(verify_res, indent=2)}")

    print("\n==========================================================================")
    print(">>> FULL END-TO-END DRY RUN COMPLETE <<<")
    print("==========================================================================")

if __name__ == "__main__":
    full_dry_run()
