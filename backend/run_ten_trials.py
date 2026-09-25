import asyncio
import time
import sqlite3
from fastapi.testclient import TestClient
from main import app
from database import get_database

async def run_trials():
    db = get_database()
    await db.init_db()

    results = []

    print("=========================================================================")
    print("STARTING 10-TRIAL ADJUDICATION VALIDATION SUITE (5x Crash, 5x False Alarm)")
    print("=========================================================================\n")

    with TestClient(app) as client:
        # 5 runs of crash_zone04
        for i in range(1, 6):
            print(f"[Run {i}/5] Triggering scenario: crash_zone04 ...")
            resp = client.post("/incidents/trigger", json={"scenario": "crash_zone04"})
            assert resp.status_code == 202, f"Trigger failed: {resp.text}"
            inc_id = resp.json()["incident_id"]

            # Poll until terminal / awaiting clearance state is reached
            start_t = time.time()
            final_row = None
            while time.time() - start_t < 14.0:
                con = sqlite3.connect("aurashield.db")
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                row = cur.execute("SELECT * FROM incidents WHERE id=?", (inc_id,)).fetchone()
                con.close()
                if row and row["state"] in ("RESPONSE_PROPOSED", "REJECTED"):
                    final_row = dict(row)
                    break
                time.sleep(0.5)

            if not final_row and row:
                final_row = dict(row)

            corr = final_row.get("corroborator_score") if final_row else None
            skep = final_row.get("skeptic_score") if final_row else None
            conf = final_row.get("confidence") if final_row else None
            fused = final_row.get("fused_score") if final_row else None
            state = final_row.get("state", "UNKNOWN") if final_row else "UNKNOWN"

            # Check audit log to find provider used
            con = sqlite3.connect("aurashield.db")
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            audit_corr = cur.execute(
                "SELECT action FROM audit_log WHERE actor='corroborator_agent' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            con.close()
            prov_text = audit_corr["action"] if audit_corr else ""

            verdict = "VERIFIED" if state in ("VERIFIED", "RESPONSE_PROPOSED", "DISPATCH_APPROVED", "RESOLVED") else "REJECTED"
            results.append({
                "trial": f"crash_zone04 #{i}",
                "corr": corr,
                "skep": skep,
                "fused": fused,
                "conf": conf,
                "state": state,
                "verdict": verdict,
                "prov": prov_text[:40] if prov_text else "N/A",
            })
            print(f" -> Result #{i}: corr={corr}, skep={skep}, fused={fused}, conf={conf}, state={state} => VERDICT: {verdict}")
            time.sleep(3.5)  # Cooldown between runs

        # 5 runs of false_alarm
        for i in range(1, 6):
            print(f"\n[Run {i}/5] Triggering scenario: false_alarm ...")
            resp = client.post("/incidents/trigger", json={"scenario": "false_alarm"})
            assert resp.status_code == 202, f"Trigger failed: {resp.text}"
            inc_id = resp.json()["incident_id"]

            start_t = time.time()
            final_row = None
            while time.time() - start_t < 14.0:
                con = sqlite3.connect("aurashield.db")
                con.row_factory = sqlite3.Row
                cur = con.cursor()
                row = cur.execute("SELECT * FROM incidents WHERE id=?", (inc_id,)).fetchone()
                con.close()
                if row and row["state"] in ("RESPONSE_PROPOSED", "REJECTED"):
                    final_row = dict(row)
                    break
                time.sleep(0.5)

            if not final_row and row:
                final_row = dict(row)

            corr = final_row.get("corroborator_score") if final_row else None
            skep = final_row.get("skeptic_score") if final_row else None
            conf = final_row.get("confidence") if final_row else None
            fused = final_row.get("fused_score") if final_row else None
            state = final_row.get("state", "UNKNOWN") if final_row else "UNKNOWN"

            con = sqlite3.connect("aurashield.db")
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            audit_corr = cur.execute(
                "SELECT action FROM audit_log WHERE actor='corroborator_agent' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            con.close()
            prov_text = audit_corr["action"] if audit_corr else ""

            verdict = "VERIFIED" if state in ("VERIFIED", "RESPONSE_PROPOSED", "DISPATCH_APPROVED", "RESOLVED") else "REJECTED"
            results.append({
                "trial": f"false_alarm #{i}",
                "corr": corr,
                "skep": skep,
                "fused": fused,
                "conf": conf,
                "state": state,
                "verdict": verdict,
                "prov": prov_text[:40] if prov_text else "N/A",
            })
            print(f" -> Result #{i}: corr={corr}, skep={skep}, fused={fused}, conf={conf}, state={state} => VERDICT: {verdict}")
            time.sleep(3.5)  # Cooldown between runs

    print("\n" + "="*85)
    print("SUMMARY OF ALL 10 TRIALS")
    print("="*85)
    print(f"{'Trial':<18} | {'Corr':<5} | {'Skep':<5} | {'Fused':<6} | {'Conf':<5} | {'State':<18} | {'Verdict'}")
    print("-" * 85)
    for r in results:
        print(f"{r['trial']:<18} | {r['corr']:<5} | {r['skep']:<5} | {r['fused']:<6} | {r['conf']:<5} | {r['state']:<18} | {r['verdict']}")
    print("="*85)

if __name__ == "__main__":
    asyncio.run(run_trials())
