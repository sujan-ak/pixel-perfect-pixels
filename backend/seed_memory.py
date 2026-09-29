"""
AuraShield Hindsight Memory Seeding Utility.
Generates realistic, backdated operational incident history for Hyderabad smart corridor.
Dual-writes through MemoryService into local deterministic ledger and Hindsight Cloud.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import sys
from pathlib import Path
from typing import List

# Ensure backend root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

from memory import (
    MemoryEvent,
    MemoryService,
    memory,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aurashield.seed_memory")

# Base date: September 2026
BASE_DATE = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

SEED_EVENTS: List[dict] = [
    # -------------------------------------------------------------------------
    # 1. ZONE 02: Low-sun angle afternoon lens-flare false alarms (8 events)
    # -------------------------------------------------------------------------
    {
        "event_id": "seed_z02_glare_01",
        "days_ago": 38,
        "hour": 16,
        "minute": 15,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0818-04",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "lens_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.48,
        "skeptic_score": 0.52,
        "fused_score": -0.04,
        "confidence": 0.90,
        "notes": "Operator Ravi noted severe low-sun glare from west-facing lens at Hitec City junction; bbox overlap 0.32 resolved in 2 frames.",
    },
    {
        "event_id": "seed_z02_glare_02",
        "days_ago": 34,
        "hour": 16,
        "minute": 42,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0822-09",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "lens_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.51,
        "skeptic_score": 0.54,
        "fused_score": -0.03,
        "confidence": 0.88,
        "notes": "Operator Priya overrode candidate: direct solar flare reflecting off Cyber Towers glass façade onto traffic lane.",
    },
    {
        "event_id": "seed_z02_glare_03",
        "days_ago": 29,
        "hour": 17,
        "minute": 5,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0827-02",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "optical_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.44,
        "skeptic_score": 0.58,
        "fused_score": -0.14,
        "confidence": 0.91,
        "notes": "Operator Ravi confirmed false positive: momentary glare occlusion during 17:00 sunset angle. No vehicle contact.",
    },
    {
        "event_id": "seed_z02_glare_04",
        "days_ago": 24,
        "hour": 16,
        "minute": 28,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0901-05",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "lens_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.49,
        "skeptic_score": 0.50,
        "fused_score": -0.01,
        "confidence": 0.89,
        "notes": "Operator Ananya overrode candidate: low-angle golden hour solar reflection triggered transient 0.38 bbox overlap.",
    },
    {
        "event_id": "seed_z02_glare_05",
        "days_ago": 19,
        "hour": 16,
        "minute": 55,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0906-08",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "lens_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.46,
        "skeptic_score": 0.56,
        "fused_score": -0.10,
        "confidence": 0.92,
        "notes": "Operator Ravi noted glare from west-facing lens after 4pm; camera sensor saturated across pixels 420-580.",
    },
    {
        "event_id": "seed_z02_glare_06",
        "days_ago": 14,
        "hour": 15,
        "minute": 48,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0911-03",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "lens_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.43,
        "skeptic_score": 0.60,
        "fused_score": -0.17,
        "confidence": 0.93,
        "notes": "Operator Kiran marked false alarm: solar specular reflection off delivery van roof confused bounding box detector.",
    },
    {
        "event_id": "seed_z02_glare_07",
        "days_ago": 9,
        "hour": 17,
        "minute": 18,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0916-07",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "lens_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.50,
        "skeptic_score": 0.53,
        "fused_score": -0.03,
        "confidence": 0.88,
        "notes": "Operator Priya overrode: 17:18 sunset glare across Lane 2; verified vehicles maintained 45 km/h steady flow.",
    },
    {
        "event_id": "seed_z02_glare_08",
        "days_ago": 4,
        "hour": 16,
        "minute": 36,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0921-04",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "lens_flare"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.47,
        "skeptic_score": 0.55,
        "fused_score": -0.08,
        "confidence": 0.91,
        "notes": "Operator Ravi noted recurring afternoon lens flare on Camera CAM2; manual override executed with glare tag.",
    },

    # -------------------------------------------------------------------------
    # 2. ZONE 02: Mast-vibration and wind-shake false alarms (4 events)
    # -------------------------------------------------------------------------
    {
        "event_id": "seed_z02_vib_01",
        "days_ago": 36,
        "hour": 19,
        "minute": 10,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0820-11",
        "zone": "Zone 02",
        "scenario": "false_alarm",
        "cause_tags": ["vibration", "wind", "mast_shake"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.35,
        "skeptic_score": 0.72,
        "fused_score": -0.37,
        "confidence": 0.94,
        "notes": "Monsoon squall gust induced high-frequency vibration on pole mount; centroid tracking jitter false alarm.",
    },
    {
        "event_id": "seed_z02_vib_02",
        "days_ago": 27,
        "hour": 14,
        "minute": 20,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0829-06",
        "zone": "Zone 02",
        "scenario": "false_alarm",
        "cause_tags": ["vibration", "mast_shake"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.38,
        "skeptic_score": 0.68,
        "fused_score": -0.30,
        "confidence": 0.90,
        "notes": "Heavy multi-axle truck crossing flyover expansion joint caused camera resonant shudder. Operator rejected.",
    },
    {
        "event_id": "seed_z02_vib_03",
        "days_ago": 18,
        "hour": 21,
        "minute": 45,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0908-12",
        "zone": "Zone 02",
        "scenario": "false_alarm",
        "cause_tags": ["vibration", "wind"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.30,
        "skeptic_score": 0.75,
        "fused_score": -0.45,
        "confidence": 0.95,
        "notes": "Night-time wind shear on Madhapur gantry arm created frame translation artifact. Operator confirmed no crash.",
    },
    {
        "event_id": "seed_z02_vib_04",
        "days_ago": 7,
        "hour": 11,
        "minute": 15,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0919-01",
        "zone": "Zone 02",
        "scenario": "false_alarm",
        "cause_tags": ["vibration", "mast_shake"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.34,
        "skeptic_score": 0.70,
        "fused_score": -0.36,
        "confidence": 0.92,
        "notes": "Metro rail pass induced ground vibration on sensor mount; transient displacement rejected by Operator Kiran.",
    },

    # -------------------------------------------------------------------------
    # 3. ZONE 02: Shadow artifacts and occlusion (3 events)
    # -------------------------------------------------------------------------
    {
        "event_id": "seed_z02_shad_01",
        "days_ago": 32,
        "hour": 13,
        "minute": 10,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0824-03",
        "zone": "Zone 02",
        "scenario": "false_alarm",
        "cause_tags": ["shadow", "occlusion"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.40,
        "skeptic_score": 0.65,
        "fused_score": -0.25,
        "confidence": 0.88,
        "notes": "Flyover bridge girder cast fast shadow over bus lane; edge detector combined shadows into phantom vehicle.",
    },
    {
        "event_id": "seed_z02_shad_02",
        "days_ago": 21,
        "hour": 12,
        "minute": 30,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0904-02",
        "zone": "Zone 02",
        "scenario": "false_alarm",
        "cause_tags": ["shadow", "occlusion"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.37,
        "skeptic_score": 0.69,
        "fused_score": -0.32,
        "confidence": 0.91,
        "notes": "Overhead advertising hoarding shadow artifact during noon sun angle. Operator Ananya confirmed false alarm.",
    },
    {
        "event_id": "seed_z02_shad_03",
        "days_ago": 11,
        "hour": 17,
        "minute": 50,
        "kind": "OPERATOR_OVERRIDE",
        "incident_id": "INC-HYD-0915-05",
        "zone": "Zone 02",
        "scenario": "false_alarm",
        "cause_tags": ["shadow", "occlusion"],
        "operator_action": "OVERRIDE_REJECT",
        "corr_score": 0.39,
        "skeptic_score": 0.64,
        "fused_score": -0.25,
        "confidence": 0.89,
        "notes": "Long sunset shadow elongation across junction crosswalk rejected by Operator Ravi as optical shadow.",
    },

    # -------------------------------------------------------------------------
    # 4. ZONE 04: Real Collisions Confirmed & Dispatched (6 events)
    # -------------------------------------------------------------------------
    {
        "event_id": "seed_z04_crash_01",
        "days_ago": 35,
        "hour": 8,
        "minute": 40,
        "kind": "OPERATOR_APPROVED",
        "incident_id": "INC-HYD-0821-01",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["collision", "rear_end"],
        "operator_action": "APPROVE_DISPATCH",
        "corr_score": 0.93,
        "skeptic_score": 0.12,
        "fused_score": 0.81,
        "confidence": 0.96,
        "hospital_id": "H_ALPHA",
        "ack_latency_ms": 7400,
        "outcome": "Patient stabilized at Apollo Jubilee Hills trauma unit; minor concussion.",
        "notes": "Operator Priya approved real collision on NH-44 Gachibowli; sustained overlap 0.82 for 16 frames.",
    },
    {
        "event_id": "seed_z04_crash_02",
        "days_ago": 28,
        "hour": 15,
        "minute": 12,
        "kind": "OPERATOR_APPROVED",
        "incident_id": "INC-HYD-0828-04",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["collision", "head_on"],
        "operator_action": "APPROVE_DISPATCH",
        "corr_score": 0.95,
        "skeptic_score": 0.09,
        "fused_score": 0.86,
        "confidence": 0.98,
        "hospital_id": "H_ALPHA",
        "ack_latency_ms": 6200,
        "outcome": "Severe front bumper deformation; 2 passengers transported to Care Gachibowli.",
        "notes": "Operator Ravi approved critical collision near Bio-Diversity junction; sudden bilateral deceleration.",
    },
    {
        "event_id": "seed_z04_crash_03",
        "days_ago": 22,
        "hour": 10,
        "minute": 25,
        "kind": "OPERATOR_APPROVED",
        "incident_id": "INC-HYD-0903-02",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["collision", "sideswipe"],
        "operator_action": "APPROVE_DISPATCH",
        "corr_score": 0.89,
        "skeptic_score": 0.15,
        "fused_score": 0.74,
        "confidence": 0.92,
        "hospital_id": "H_BETA",
        "ack_latency_ms": 9800,
        "outcome": "Ambulance team arrived within 6 mins; lane cleared in 22 mins.",
        "notes": "Operator Ananya approved multi-vehicle contact on Gachibowli flyover down-ramp.",
    },
    {
        "event_id": "seed_z04_crash_04",
        "days_ago": 16,
        "hour": 18,
        "minute": 30,
        "kind": "OPERATOR_APPROVED",
        "incident_id": "INC-HYD-0909-09",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["collision", "rear_end"],
        "operator_action": "APPROVE_DISPATCH",
        "corr_score": 0.92,
        "skeptic_score": 0.11,
        "fused_score": 0.81,
        "confidence": 0.95,
        "hospital_id": "H_BETA",
        "ack_latency_ms": 8300,
        "outcome": "Care Hospital Trauma verified patient admission; green-corridor priority activated.",
        "notes": "Operator Kiran dispatched: commercial truck rammed sedan at signal; clear physical intrusion.",
    },
    {
        "event_id": "seed_z04_crash_05",
        "days_ago": 10,
        "hour": 22,
        "minute": 15,
        "kind": "OPERATOR_APPROVED",
        "incident_id": "INC-HYD-0915-11",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["collision", "high_speed"],
        "operator_action": "APPROVE_DISPATCH",
        "corr_score": 0.96,
        "skeptic_score": 0.08,
        "fused_score": 0.88,
        "confidence": 0.97,
        "hospital_id": "H_ALPHA",
        "ack_latency_ms": 6900,
        "outcome": "Emergency responders on scene within 5m40s; patient admitted to ICU.",
        "notes": "Night-time high-speed collision on NH-44 median; zero glare detected, impact verified.",
    },
    {
        "event_id": "seed_z04_crash_06",
        "days_ago": 3,
        "hour": 14,
        "minute": 5,
        "kind": "OPERATOR_APPROVED",
        "incident_id": "INC-HYD-0923-03",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["collision", "rear_end"],
        "operator_action": "APPROVE_DISPATCH",
        "corr_score": 0.90,
        "skeptic_score": 0.14,
        "fused_score": 0.76,
        "confidence": 0.93,
        "hospital_id": "H_BETA",
        "ack_latency_ms": 11200,
        "outcome": "Paramedic triage complete; no critical injuries.",
        "notes": "Operator Ravi approved two-wheeler collision at pedestrian crossing; sustained deceleration.",
    },

    # -------------------------------------------------------------------------
    # 5. HOSPITAL ROUTING: H_ALPHA Peak-Hour Capacity Declines/Timeouts (4 events)
    # -------------------------------------------------------------------------
    {
        "event_id": "seed_hosp_decline_01",
        "days_ago": 30,
        "hour": 18,
        "minute": 15,
        "kind": "DISPATCH_DECLINED",
        "incident_id": "INC-HYD-0826-07",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["hospital_capacity", "peak_hour"],
        "hospital_id": "H_ALPHA",
        "notes": "Apollo Trauma H_ALPHA declined dispatch: peak evening emergency ward bed saturation (100% capacity). Re-routed to H_BETA.",
    },
    {
        "event_id": "seed_hosp_decline_02",
        "days_ago": 23,
        "hour": 18,
        "minute": 45,
        "kind": "ACK_TIMEOUT",
        "incident_id": "INC-HYD-0902-08",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["hospital_timeout", "peak_hour"],
        "hospital_id": "H_ALPHA",
        "notes": "H_ALPHA desk response timed out after 30s during peak shift change; automated fallback engaged to H_BETA.",
    },
    {
        "event_id": "seed_hosp_decline_03",
        "days_ago": 15,
        "hour": 19,
        "minute": 10,
        "kind": "DISPATCH_DECLINED",
        "incident_id": "INC-HYD-0910-10",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["hospital_capacity", "peak_hour"],
        "hospital_id": "H_ALPHA",
        "notes": "H_ALPHA trauma desk declined: 3 incoming critical cases from Outer Ring Road. Care Hospital H_BETA accepted immediately.",
    },
    {
        "event_id": "seed_hosp_decline_04",
        "days_ago": 8,
        "hour": 18,
        "minute": 50,
        "kind": "DISPATCH_DECLINED",
        "incident_id": "INC-HYD-0918-09",
        "zone": "Zone 04",
        "scenario": "crash_zone04",
        "cause_tags": ["hospital_capacity", "peak_hour"],
        "hospital_id": "H_ALPHA",
        "notes": "H_ALPHA declined peak hour ambulance transfer. System learned to bias toward H_BETA for 18:00-19:30 window.",
    },

    # -------------------------------------------------------------------------
    # 6. AMBIGUOUS CASES: Near-misses / parking tap / resolved scrapes (3 events)
    # -------------------------------------------------------------------------
    {
        "event_id": "seed_ambig_01",
        "days_ago": 25,
        "hour": 11,
        "minute": 40,
        "kind": "INCIDENT_REJECTED",
        "incident_id": "INC-HYD-0831-03",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["near_miss", "minor_scrape"],
        "corr_score": 0.54,
        "skeptic_score": 0.48,
        "fused_score": 0.06,
        "confidence": 0.72,
        "notes": "Slow bumper kiss at 5 km/h in Hitec City taxi stand; drivers exchanged words and departed. Evaluated as non-dispatchable.",
    },
    {
        "event_id": "seed_ambig_02",
        "days_ago": 17,
        "hour": 15,
        "minute": 20,
        "kind": "OPERATOR_APPROVED",
        "incident_id": "INC-HYD-0909-04",
        "zone": "Zone 04",
        "scenario": "glare_ambiguous",
        "cause_tags": ["ambiguous", "collision"],
        "operator_action": "APPROVE_DISPATCH",
        "corr_score": 0.62,
        "skeptic_score": 0.38,
        "fused_score": 0.24,
        "confidence": 0.81,
        "hospital_id": "H_BETA",
        "notes": "Low-speed scooter fall on oil slick; minor injury confirmed by operator monitoring CCTV pan-tilt-zoom.",
    },
    {
        "event_id": "seed_ambig_03",
        "days_ago": 5,
        "hour": 16,
        "minute": 50,
        "kind": "INCIDENT_REJECTED",
        "incident_id": "INC-HYD-0921-09",
        "zone": "Zone 02",
        "scenario": "glare_ambiguous",
        "cause_tags": ["glare", "abrupt_stop"],
        "corr_score": 0.47,
        "skeptic_score": 0.51,
        "fused_score": -0.04,
        "confidence": 0.80,
        "notes": "Sudden stop at zebra crossing under harsh backlight; vehicles never made physical contact. System rejected.",
    },
]


def create_memory_event_from_dict(item: dict) -> MemoryEvent:
    event_dt = BASE_DATE - timedelta(days=item["days_ago"], hours=(12 - item["hour"]), minutes=item["minute"])
    ts_str = event_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return MemoryEvent(
        event_id=item["event_id"],
        ts=ts_str,
        kind=item["kind"],
        incident_id=item["incident_id"],
        zone=item["zone"],
        scenario=item.get("scenario", "unknown"),
        cause_tags=item.get("cause_tags", []),
        operator_action=item.get("operator_action"),
        outcome=item.get("outcome"),
        confidence=item.get("confidence", 0.90),
        corr_score=item.get("corr_score"),
        skeptic_score=item.get("skeptic_score"),
        fused_score=item.get("fused_score"),
        hospital_id=item.get("hospital_id"),
        ack_latency_ms=item.get("ack_latency_ms"),
        notes=item.get("notes"),
    )


async def seed_memory(reset: bool = False, limit_n: int = 30) -> None:
    logger.info("Initializing AuraShield realistic memory seeding (n=%d, reset=%s)...", limit_n, reset)

    if reset:
        logger.info("Clearing local deterministic ledger...")
        await memory.ledger.clear()
        # Safe reset for Hindsight bank if bank id begins with 'aurashield-'
        if memory.bank_id.startswith("aurashield-"):
            client = memory._get_client()
            if client is not None:
                try:
                    if hasattr(client, "adelete_bank"):
                        logger.info("Calling safe Hindsight delete for demo bank '%s'...", memory.bank_id)
                        await client.adelete_bank(memory.bank_id)
                    elif hasattr(client, "areset_bank_config"):
                        logger.info("Calling safe Hindsight bank config reset...")
                        await client.areset_bank_config(memory.bank_id)
                except Exception as e:
                    logger.warning("Hindsight remote bank reset skipped/failed: %s", e)
        logger.info("Reset complete.")

    # Check already seeded event IDs for idempotency
    existing_events = await memory.ledger.read_all()
    existing_ids = set(e.event_id for e in existing_events)

    events_to_seed = SEED_EVENTS[:limit_n]
    seeded_count = 0
    skipped_count = 0

    try:
        for item in events_to_seed:
            if item["event_id"] in existing_ids:
                skipped_count += 1
                continue

            event = create_memory_event_from_dict(item)
            await memory.retain(event)
            seeded_count += 1
    finally:
        await memory.aclose()

    # Fetch stats
    stats_all = await memory.ledger.stats()
    stats_z2_glare = await memory.ledger.stats(zone="Zone 02", cause_tags=["glare"])
    stats_z2_vib = await memory.ledger.stats(zone="Zone 02", cause_tags=["vibration"])
    stats_z4 = await memory.ledger.stats(zone="Zone 04")
    total_ledger = await memory.ledger.count()

    print("\n" + "=" * 80)
    print("           AURASHIELD REALISTIC OPERATIONAL MEMORY SEED SUMMARY")
    print("=" * 80)
    print(f"Total events in ledger:               {total_ledger} (newly seeded: {seeded_count}, skipped: {skipped_count})")
    print(f"Zone 02 Low-Sun Glare Overrides:      {stats_z2_glare.overrides} confirmed false alarms (15:30-17:30 window)")
    print(f"Zone 02 Mast Vibration Overrides:     {stats_z2_vib.overrides} confirmed mechanical/wind false alarms")
    print(f"Zone 04 Real Collisions Approved:     {stats_z4.approved} confirmed collisions (dispatched with hospital transport)")
    print(f"Hospital Declines & Peak Timeouts:    {stats_all.declines + stats_all.timeouts} events recorded for H_ALPHA")
    print(f"Active Memory Bank ID:                {memory.bank_id}")
    print(f"Dual-write target:                    Deterministic Ledger ({memory.ledger.file_path.name}) + Hindsight")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Seed realistic AuraShield operational incident memory")
    parser.add_argument("--reset", action="store_true", help="Clear memory ledger and reset demo bank first")
    parser.add_argument("--n", type=int, default=30, help="Number of historical events to seed (default: 30)")
    args = parser.parse_args()

    asyncio.run(seed_memory(reset=args.reset, limit_n=args.n))


if __name__ == "__main__":
    main()
