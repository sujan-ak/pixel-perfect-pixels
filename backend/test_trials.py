import asyncio
import time
import sqlite3
from fastapi.testclient import TestClient
from main import app, orchestrator

def run_ten_trials():
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

            # Wait for pipeline to finish
            start_t = time.time()
            final_row = None
            while time.time() - start_t < 15.0:
                if inc_id not in orchestrator.active_tasks and "crash_zone04" not in orchestrator.running_scenarios:
                    break
                time.sleep(0.4)

            con = sqlite3.connect("aurashield.db")
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            row = cur.execute("SELECT * FROM incidents WHERE id=?", (inc_id,)).fetchone()
            con.close()
            final_row = dict(row) if row else {}

            corr = final_row.get("corroborator_score")
            skep = final_row.get("skeptic_score")
            conf = final_row.get("confidence")
            fused = final_row.get("fused_score")
            state = final_row.get("state", "UNKNOWN")

            verdict = "VERIFIED" if state in ("VERIFIED", "RESPONSE_PROPOSED", "DISPATCH_APPROVED", "RESOLVED") else "REJECTED"
            results.append({
                "trial": f"crash_zone04 #{i}",
                "id": inc_id,
                "corr": corr,
                "skep": skep,
                "fused": fused,
                "conf": conf,
                "state": state,
                "verdict": verdict,
            })
            print(f" -> Result #{i} ({inc_id}): corr={corr}, skep={skep}, fused={fused}, conf={conf}, state={state} => VERDICT: {verdict}")
            time.sleep(3.5)  # Cooldown

        # 5 runs of false_alarm
        for i in range(1, 6):
            print(f"\n[Run {i}/5] Triggering scenario: false_alarm ...")
            resp = client.post("/incidents/trigger", json={"scenario": "false_alarm"})
            assert resp.status_code == 202, f"Trigger failed: {resp.text}"
            inc_id = resp.json()["incident_id"]

            start_t = time.time()
            final_row = None
            while time.time() - start_t < 15.0:
                if inc_id not in orchestrator.active_tasks and "false_alarm" not in orchestrator.running_scenarios:
                    break
                time.sleep(0.4)

            con = sqlite3.connect("aurashield.db")
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            row = cur.execute("SELECT * FROM incidents WHERE id=?", (inc_id,)).fetchone()
            con.close()
            final_row = dict(row) if row else {}

            corr = final_row.get("corroborator_score")
            skep = final_row.get("skeptic_score")
            conf = final_row.get("confidence")
            fused = final_row.get("fused_score")
            state = final_row.get("state", "UNKNOWN")

            verdict = "VERIFIED" if state in ("VERIFIED", "RESPONSE_PROPOSED", "DISPATCH_APPROVED", "RESOLVED") else "REJECTED"
            results.append({
                "trial": f"false_alarm #{i}",
                "id": inc_id,
                "corr": corr,
                "skep": skep,
                "fused": fused,
                "conf": conf,
                "state": state,
                "verdict": verdict,
            })
            print(f" -> Result #{i} ({inc_id}): corr={corr}, skep={skep}, fused={fused}, conf={conf}, state={state} => VERDICT: {verdict}")
            time.sleep(3.5)  # Cooldown

    print("\n" + "="*88)
    print("FINAL 10-TRIAL ADJUDICATION VALIDATION TABLE")
    print("="*88)
    print(f"{'Trial':<18} | {'ID':<8} | {'Corr':<5} | {'Skep':<5} | {'Fused':<6} | {'Conf':<5} | {'State':<18} | {'Verdict'}")
    print("-" * 88)
    for r in results:
        print(f"{r['trial']:<18} | {r['id']:<8} | {r['corr']:<5} | {r['skep']:<5} | {r['fused']:<6} | {r['conf']:<5} | {r['state']:<18} | {r['verdict']}")
    print("="*88)

if __name__ == "__main__":
    run_ten_trials()
