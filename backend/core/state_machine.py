import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

from agents.verification import (
    SCENARIO_FIXTURES,
    assert_terminal_state_matches,
    compute_fused_score,
    generate_reasoning,
    get_real_scores,
)
from core.city import CityTwin
from core.notifications import (
    dispatch_police_notification,
    dispatch_hospital_notification,
    get_police_recipient,
    build_police_notification_message,
)
from database import DatabaseBackend, AuditEntry, Incident

logger = logging.getLogger("aurashield.core.state_machine")

LEGAL_TRANSITIONS: Dict[Optional[str], Set[str]] = {
    None: {"OBSERVED"},
    "OBSERVED": {"CANDIDATE"},
    "CANDIDATE": {"VERIFIED", "REJECTED"},
    "VERIFIED": {"RESPONSE_PROPOSED"},
    "RESPONSE_PROPOSED": {"OPERATOR_APPROVED"},
    "OPERATOR_APPROVED": {"COORDINATION_IN_PROGRESS"},
    "COORDINATION_IN_PROGRESS": {"ACKNOWLEDGED", "REPLANNING", "REJECTED"},
    "REPLANNING": {"COORDINATION_IN_PROGRESS", "ACKNOWLEDGED"},
    "ACKNOWLEDGED": {"EN_ROUTE", "CLOSED"},
    "EN_ROUTE": {"ON_SCENE"},
    "ON_SCENE": {"PATIENT_LOADED", "HANDED_OVER"},
    "PATIENT_LOADED": {"HANDED_OVER"},
    "HANDED_OVER": {"CLOSED"},
    "CLOSED": set(),
    "REJECTED": set(),
}


def is_valid_transition(from_state: Optional[str], to_state: str) -> bool:
    allowed = LEGAL_TRANSITIONS.get(from_state, set())
    return to_state in allowed


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WS client connected. Total clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info("WS client disconnected. Total clients: %d", len(self.active_connections))

    async def broadcast_json(self, data: dict) -> None:
        dead_connections: List[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning("Failed to send WS message to client: %s", e)
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    async def replay_to_client(
        self,
        websocket: WebSocket,
        latest_incident: Optional[Incident],
        audit_entries: List[AuditEntry],
    ) -> None:
        try:
            if latest_incident:
                await websocket.send_json(
                    {"type": "incident_update", "incident": latest_incident.model_dump()}
                )
                logger.debug("Replayed latest incident %s to new WS client", latest_incident.id)

            for entry in audit_entries:
                await websocket.send_json(
                    {"type": "audit_entry", "entry": entry.model_dump()}
                )
            logger.info(
                "Replayed %d audit entries to new WS client", len(audit_entries)
            )
        except Exception as e:
            logger.warning("Error during WS client replay: %s", e)


class IncidentOrchestrator:
    def __init__(self, db: DatabaseBackend, connection_manager: ConnectionManager) -> None:
        self.db = db
        self.connection_manager = connection_manager
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.incident_counter: int = 0
        self.last_scenario_times: Dict[str, float] = {}
        self.running_scenarios: Dict[str, str] = {}  # scenario -> incident_id
        self.governor_sensitivity: float = float(os.getenv("GOVERNOR_SENSITIVITY", "0.65"))
        self.automation_paused: bool = False
        self._lock = asyncio.Lock()

        # AuraShield Mobile Responder Integration State
        self.responder_device_enabled: bool = False
        self._device_seen_ms: Optional[int] = None
        self.ack_deadline_ms: Optional[int] = None
        self.twin = CityTwin()
        self.active_plan: Optional[dict] = None
        self.field_updates: List[dict] = []
        self.acknowledgements: List[dict] = []
        self.last_approved_incident_id: Optional[str] = None

    def device_heartbeat(self) -> None:
        self._device_seen_ms = int(time.time() * 1000)

    def device_connected(self) -> bool:
        if self._device_seen_ms is None:
            return False
        return (int(time.time() * 1000) - self._device_seen_ms) <= 5000

    async def set_responder_device(self, enabled: bool) -> dict:
        self.responder_device_enabled = bool(enabled)
        self.device_heartbeat()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        action = "RESPONDER_ON_DUTY: device connected" if enabled else "RESPONDER_OFF_DUTY: fallback to mock"
        audit = await self.db.append_audit_entry(actor="responder_device", action=action, timestamp=now_iso)
        await self.connection_manager.broadcast_json({"type": "audit_entry", "entry": audit.model_dump()})
        await self.connection_manager.broadcast_json(
            {"type": "responder_device_status", "enabled": enabled, "connected": self.device_connected()}
        )
        return await self.build_mobile_state()

    def build_dispatch_plan(self, incident: Incident) -> dict:
        severity = "CRITICAL" if incident.corroborator_score > 0.7 else "HIGH"
        hospital_id = self.twin.choose_hospital(severity)
        hospital = self.twin.hospitals.get(hospital_id)
        route_data = self.twin.plan_route(hospital_id, incident_node="N_CAM4")

        return {
            "plan_id": f"plan_{incident.id}",
            "version": 1,
            "stage": 1,
            "stage_label": "DISPATCH_TO_SCENE",
            "hospital_id": hospital_id,
            "hospital_name": hospital.name if hospital else "Sunshine Hospital, Gachibowli",
            "severity": severity,
            "route_node_ids": route_data["path"],
            "junction_ids": route_data["controllable_junctions"],
            "eta_seconds": route_data["eta_seconds"],
            "distance_meters": route_data["cost_m"],
            "resources": ["Ambulance Unit #09", "Advanced Life Support"] if severity == "CRITICAL" else ["Basic Life Support"],
            "superseded_by": None,
            "superseded_reason": "",
        }

    def build_stage2_dispatch_plan(self, incident: Incident) -> dict:
        severity = "CRITICAL" if incident.corroborator_score > 0.7 else "HIGH"
        incident_node = "N_CAM4"
        # Suitability first, then reachability and shortest graph path from N_CAM4
        hospital_id = self.twin.choose_hospital(severity, src_node=incident_node)
        hospital = self.twin.hospitals.get(hospital_id)
        route_data = self.twin.plan_route(hospital_id, incident_node=incident_node, src_node=incident_node)

        return {
            "plan_id": f"plan_{incident.id}_s2",
            "version": 2,
            "stage": 2,
            "stage_label": "PICKUP_TO_HOSPITAL",
            "hospital_id": hospital_id,
            "hospital_name": hospital.name if hospital else "Sunshine Hospital, Gachibowli",
            "severity": severity,
            "route_node_ids": route_data["path"],
            "junction_ids": route_data["controllable_junctions"],
            "eta_seconds": route_data["eta_seconds"],
            "distance_meters": route_data["cost_m"],
            "resources": ["Ambulance Unit #09", "Advanced Life Support"] if severity == "CRITICAL" else ["Basic Life Support"],
            "superseded_by": None,
            "superseded_reason": "",
        }

    async def stream_agent_reasoning(self, agent: str, text: str) -> None:
        try:
            await self.connection_manager.broadcast_json({
                "type": "agent_reasoning_chunk",
                "agent": agent,
                "text": text,
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })
        except Exception as e:
            logger.warning("Failed to stream reasoning chunk: %s", e)

    async def get_next_incident_id(self) -> str:
        async with self._lock:
            try:
                history = await self.db.get_incident_history()
                max_num = max([int(inc.id.split("_")[1]) for inc in history if inc.id.startswith("inc_") and inc.id.split("_")[1].isdigit()] or [0])
                self.incident_counter = max(self.incident_counter, max_num)
            except Exception:
                pass
            self.incident_counter += 1
            return f"inc_{self.incident_counter:03d}"

    def check_scenario_cooldown(self, scenario: str) -> bool:
        """
        Check if duplicate scenario is running or was triggered within cooldown (3 seconds).
        Returns True if allowed, False if conflict (409).
        """
        if scenario in self.running_scenarios:
            return False

        last_time = self.last_scenario_times.get(scenario, 0)
        if time.time() - last_time < 3.0:
            return False

        return True

    async def trigger_scenario(self, scenario: str) -> str:
        if not self.check_scenario_cooldown(scenario):
            raise ValueError(f"Duplicate trigger for scenario '{scenario}' in flight or on cooldown")

        incident_id = await self.get_next_incident_id()
        self.running_scenarios[scenario] = incident_id
        self.last_scenario_times[scenario] = time.time()

        task = asyncio.create_task(
            self.run_scenario_pipeline(incident_id, scenario),
            name=f"pipeline-{incident_id}",
        )
        self.active_tasks[incident_id] = task

        def cleanup_task(t: asyncio.Task) -> None:
            self.active_tasks.pop(incident_id, None)
            self.running_scenarios.pop(scenario, None)
            self.last_scenario_times[scenario] = time.time()
            if not t.cancelled():
                exc = t.exception()
                if exc:
                    logger.error(
                        "Pipeline for incident %s failed with exception: %s",
                        incident_id,
                        exc,
                    )

        task.add_done_callback(cleanup_task)
        return incident_id

    async def run_scenario_pipeline(self, incident_id: str, scenario: str) -> None:
        fixture = SCENARIO_FIXTURES.get(scenario)
        if not fixture:
            logger.error("Unknown scenario fixture: %s", scenario)
            return

        steps = fixture["steps"]
        zone = fixture["zone"]
        media_file = fixture["media_file"]
        prev_state: Optional[str] = None

        logger.info("Starting scenario pipeline for %s (%s, %s)", incident_id, scenario, zone)

        fallback_corr = steps[-1]["corroborator_score"]
        fallback_skep = steps[-1]["skeptic_score"]

        # Call get_real_scores ONCE at start of pipeline
        real_corr, real_skep, confidence, degraded, corr_evidence, skep_evidence, provider_summary = (
            await get_real_scores(
                scenario=scenario,
                fallback_corr=fallback_corr,
                fallback_skep=fallback_skep,
            )
        )
        logger.info(
            "Adversarial scoring for %s: corr=%.2f, skep=%.2f, conf=%.2f, degraded=%s, provider=%s",
            scenario,
            real_corr,
            real_skep,
            confidence,
            degraded,
            provider_summary,
        )

        corr_prov, skep_prov = provider_summary.split("+") if "+" in provider_summary else (provider_summary, provider_summary)
        await self.stream_agent_reasoning("CORROBORATOR", f"Initiating advocate analysis for {zone} (engine: {corr_prov})...")
        for ev in corr_evidence:
            await asyncio.sleep(0.06)
            await self.stream_agent_reasoning("CORROBORATOR", f"{ev} [Advocate Score: {real_corr:.2f}]")

        await self.stream_agent_reasoning("SKEPTIC", f"Auditing telemetry against optical noise, glare, mount vibration (engine: {skep_prov})...")
        for ev in skep_evidence:
            await asyncio.sleep(0.06)
            await self.stream_agent_reasoning("SKEPTIC", f"{ev} [Skeptic Score: {real_skep:.2f}]")

        final_fused = compute_fused_score(real_corr, real_skep)
        sensitivity_thresh = self.governor_sensitivity
        is_verified_by_gov = (final_fused > 0.35 and confidence >= sensitivity_thresh)
        gov_summary = (
            f"Dual-model fusion complete: Fused {final_fused:+.2f} | Confidence {confidence:.2f} "
            f"(Threshold: {sensitivity_thresh:.2f}) -> {'VERIFIED FOR DISPATCH' if is_verified_by_gov else 'REJECTED AS FALSE ALARM'}"
        )
        await self.stream_agent_reasoning("GOVERNOR", gov_summary)

        for i, step in enumerate(steps):
            if i > 0:
                await asyncio.sleep(1.4)

            raw_state = step["state"]
            # Dynamic sensitivity flip: if step is reaching VERIFIED or REJECTED, gate by governor
            if raw_state in ("VERIFIED", "RESPONSE_PROPOSED"):
                new_state = raw_state if is_verified_by_gov else "REJECTED"
            elif raw_state == "REJECTED":
                new_state = "REJECTED"
            else:
                new_state = raw_state

            if not is_valid_transition(prev_state, new_state):
                logger.error(
                    "Illegal transition attempted for %s: %s -> %s",
                    incident_id,
                    prev_state,
                    new_state,
                )
            else:
                logger.info(
                    "Transition for %s: %s -> %s",
                    incident_id,
                    prev_state or "None",
                    new_state,
                )

            # Interpolate towards real LLM scores
            if new_state == "OBSERVED":
                corr = round(real_corr * 0.22, 2)
                skep = round(real_skep * 0.40, 2)
            elif new_state == "CANDIDATE":
                corr = round(real_corr * 0.71, 2)
                skep = round(real_skep * 0.80, 2)
            else:
                corr = real_corr
                skep = real_skep

            fused = compute_fused_score(corr, skep)

            # Self-check assertion on final step
            if i == len(steps) - 1:
                assert_terminal_state_matches(
                    fixture_state=new_state,
                    corroborator_score=corr,
                    skeptic_score=skep,
                    confidence=confidence,
                )

            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            reasoning = await generate_reasoning(
                state=new_state,
                scenario=scenario,
                zone=zone,
                corroborator_score=corr,
                skeptic_score=skep,
                fused_score=fused,
                fallback=step["reasoning"],
            )

            if degraded and not reasoning.endswith("[FALLBACK SCORING]"):
                reasoning = f"{reasoning} [FALLBACK SCORING]"

            incident = Incident(
                id=incident_id,
                state=new_state,
                zone=zone,
                scenario=scenario,
                corroborator_score=corr,
                skeptic_score=skep,
                fused_score=fused,
                confidence=confidence,
                reasoning=reasoning,
                media_file=media_file,
                timestamp=now_iso,
                degraded=degraded,
            )

            # Persist incident
            await self.db.save_incident(incident)

            # Broadcast incident_update
            await self.connection_manager.broadcast_json(
                {
                    "type": "incident_update",
                    "incident": incident.model_dump(),
                    "degraded": degraded,
                }
            )

            # Paired audit entry
            if i == 0:
                actor = "system"
                action = f"INCIDENT_CREATED: {incident_id}"
                audit_entry = await self.db.append_audit_entry(
                    actor=actor, action=action, timestamp=now_iso
                )
                await self.connection_manager.broadcast_json(
                    {"type": "audit_entry", "entry": audit_entry.model_dump()}
                )

                # Log both agents' full evidence arrays as their own entries
                corr_ev_text = corr_evidence[0] if corr_evidence else "telemetry match"
                skep_ev_text = skep_evidence[0] if skep_evidence else "telemetry review"

                corr_audit = await self.db.append_audit_entry(
                    actor="corroborator_agent",
                    action=f"SCORED: {real_corr} ({corr_prov}) — {corr_ev_text}",
                    timestamp=now_iso,
                )
                await self.connection_manager.broadcast_json(
                    {"type": "audit_entry", "entry": corr_audit.model_dump()}
                )

                skep_audit = await self.db.append_audit_entry(
                    actor="skeptic_agent",
                    action=f"SCORED: {real_skep} ({skep_prov}) — {skep_ev_text}",
                    timestamp=now_iso,
                )
                await self.connection_manager.broadcast_json(
                    {"type": "audit_entry", "entry": skep_audit.model_dump()}
                )
            else:
                actor = "safety_governor"
                action = f"STATE_TRANSITION: {prev_state} -> {new_state}"
                audit_entry = await self.db.append_audit_entry(
                    actor=actor, action=action, timestamp=now_iso
                )
                await self.connection_manager.broadcast_json(
                    {"type": "audit_entry", "entry": audit_entry.model_dump()}
                )

            prev_state = new_state

            # If scenario got rejected by sensitivity gate, stop pipeline here
            if new_state == "REJECTED":
                break

        if prev_state == "RESPONSE_PROPOSED" and self.automation_paused:
            await self.stream_agent_reasoning(
                "GOVERNOR", "AUTOMATION PAUSED BY OPERATOR: incident awaiting manual clearance or resume."
            )

        logger.info("Completed scenario pipeline for %s (%s)", incident_id, scenario)

    async def override_reject_incident(
        self, incident_id: str, reason: str = "Operator manual override: marked as false positive"
    ) -> dict:
        incident = await self.db.get_incident_by_id(incident_id)
        if not incident:
            raise KeyError(f"Incident {incident_id} not found")

        # Cancel active task if running
        task = self.active_tasks.get(incident_id)
        if task and not task.done():
            task.cancel()

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Emit audit entry
        action_str = f"OPERATOR_OVERRIDE_REJECT: {incident.id} — {reason}"
        audit_entry = await self.db.append_audit_entry(
            actor="operator_1",
            action=action_str,
            timestamp=now_iso,
        )
        await self.connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry.model_dump()}
        )

        updated_incident = Incident(
            id=incident.id,
            state="REJECTED",
            zone=incident.zone,
            scenario=incident.scenario,
            corroborator_score=incident.corroborator_score,
            skeptic_score=incident.skeptic_score,
            fused_score=incident.fused_score,
            confidence=incident.confidence,
            reasoning=f"REJECTED: Operator manual override — {reason}",
            media_file=incident.media_file,
            timestamp=now_iso,
            degraded=incident.degraded,
        )
        await self.db.save_incident(updated_incident)
        await self.connection_manager.broadcast_json(
            {"type": "incident_update", "incident": updated_incident.model_dump()}
        )

        await self.stream_agent_reasoning(
            "GOVERNOR",
            f"OVERRIDE: Operator rejected incident {incident_id} ({reason}). State -> REJECTED.",
        )
        return {"status": "rejected", "incident_id": incident_id, "reason": reason}

    async def approve_incident(self, incident_id: str) -> dict:
        if self.automation_paused:
            raise ValueError(
                f"Automation is paused by operator. Unpause automation to approve incident {incident_id}."
            )

        incident = await self.db.get_incident_by_id(incident_id)
        if not incident:
            raise KeyError(f"Incident {incident_id} not found")

        # Must be awaiting clearance: VERIFIED or RESPONSE_PROPOSED
        if incident.state not in ("VERIFIED", "RESPONSE_PROPOSED"):
            raise ValueError(
                f"Incident {incident_id} in state '{incident.state}' cannot be approved"
            )

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Emit audit entry for operator approval
        audit_entry = await self.db.append_audit_entry(
            actor="operator_1",
            action=f"APPROVE_DISPATCH: {incident.id}",
            timestamp=now_iso,
        )
        await self.connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry.model_dump()}
        )

        # Transition state to COORDINATION_IN_PROGRESS
        incident.state = "COORDINATION_IN_PROGRESS"
        await self.db.save_incident(incident)
        await self.connection_manager.broadcast_json(
            {"type": "incident_update", "incident": incident.model_dump()}
        )

        self.last_approved_incident_id = incident.id
        self.active_plan = self.build_dispatch_plan(incident)
        self.field_updates = []
        self.acknowledgements = []
        self.ack_deadline_ms = int(time.time() * 1000) + 20000

        # Police Emergency Notification (idempotent, dynamic location and severity)
        location_label = f"{incident.zone} (NH-44 Gachibowli Junction), Hyderabad"
        await dispatch_police_notification(
            db=self.db,
            incident=incident,
            location_label=location_label,
            connection_manager=self.connection_manager,
        )

        police_recipient = get_police_recipient()
        police_body = build_police_notification_message(incident, location_label)
        police_from = (
            os.getenv("TWILIO_FROM_NUMBER")
            or os.getenv("TWILIO_FROM")
            or "+17372508034"
        )
        sms_payload = {
            "to": police_recipient,
            "from": police_from,
            "body": police_body,
            "timestamp": now_iso,
        }

        # Check if real responder mobile device is on duty
        if self.responder_device_enabled or self.device_connected():
            logger.info("Responder device is ACTIVE. Leaving incident %s in COORDINATION_IN_PROGRESS awaiting mobile ACK", incident.id)
            audit_disp = await self.db.append_audit_entry(
                actor="dispatch_coordinator",
                action=f"DISPATCH_TRANSMITTED: {incident.id} transmitted to responder mobile device",
                timestamp=now_iso,
            )
            await self.connection_manager.broadcast_json(
                {"type": "audit_entry", "entry": audit_disp.model_dump()}
            )
            await self.stream_agent_reasoning(
                "DISPATCH",
                f"Dispatch transmitted to responder iPhone. Awaiting slide acknowledgement."
            )
        else:
            logger.info("Responder device is not active. Running fallback post-approval pipeline for incident %s", incident.id)
            asyncio.create_task(
                self.run_post_approval_pipeline(incident),
                name=f"post-approval-{incident.id}",
            )

        return {"status": "approved", "sms_payload": sms_payload}

    async def acknowledge_dispatch(
        self, incident_id: Optional[str] = None, source: str = "responder_iphone", channel: str = "responder_device"
    ) -> dict:
        inc = await self.db.get_incident_by_id(incident_id) if incident_id else await self.db.get_latest_incident()
        if not inc:
            raise KeyError("No active incident found to acknowledge")
        if inc.state not in ("COORDINATION_IN_PROGRESS", "REPLANNING"):
            raise ValueError(f"No dispatch awaiting acknowledgement in state '{inc.state}'")

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inc.state = "ACKNOWLEDGED"
        inc.responder_id = source
        inc.ack_channel = channel
        inc.ack_time = now_iso
        self.acknowledgements.append({
            "source": source,
            "channel": channel,
            "at_ms": int(time.time() * 1000),
        })
        self.ack_deadline_ms = None

        await self.db.save_incident(inc)
        await self.connection_manager.broadcast_json(
            {"type": "incident_update", "incident": inc.model_dump()}
        )
        audit_entry = await self.db.append_audit_entry(
            actor="responder_device",
            action=f"RESPONDER_ACKNOWLEDGED: dispatch accepted by {source} via {channel}",
            timestamp=now_iso,
        )
        await self.connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry.model_dump()}
        )
        await self.stream_agent_reasoning(
            "DISPATCH",
            f"Ambulance Unit responder acknowledged dispatch on mobile device ({source})."
        )
        return await self.build_mobile_state()

    async def decline_dispatch(
        self, incident_id: Optional[str] = None, source: str = "responder_iphone"
    ) -> dict:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        audit_entry = await self.db.append_audit_entry(
            actor="responder_device",
            action=f"RESPONDER_DECLINED: dispatch declined by {source}",
            timestamp=now_iso,
        )
        await self.connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry.model_dump()}
        )
        await self.stream_agent_reasoning(
            "DISPATCH",
            f"Responder {source} declined dispatch. Backup reroute initiated."
        )
        return await self.build_mobile_state()

    async def update_field_status(
        self, incident_id: Optional[str] = None, source: str = "responder_iphone", status: str = "EN_ROUTE"
    ) -> dict:
        if status not in ("EN_ROUTE", "ON_SCENE", "PATIENT_LOADED", "HANDED_OVER"):
            raise ValueError(f"Unknown field status: {status}")

        inc = await self.db.get_incident_by_id(incident_id) if incident_id else await self.db.get_latest_incident()
        if not inc:
            raise KeyError("No active incident found to update field status")

        # Idempotency guard: if status already applied, return state without duplicate actions/routes
        if inc.field_status == status:
            logger.info("Field status '%s' already set for %s (idempotent no-op)", status, inc.id)
            return await self.build_mobile_state()

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        inc.field_status = status
        inc.state = status
        self.field_updates.append({
            "status": status,
            "source": source,
            "at_ms": int(time.time() * 1000),
        })

        # ONLY PATIENT_LOADED triggers Stage 2 routing (ON_SCENE does NOT trigger Stage 2)
        if status == "PATIENT_LOADED":
            self.active_plan = self.build_stage2_dispatch_plan(inc)
            logger.info("Stage 2 pickup-to-hospital route plan generated for %s (dest: %s, eta: %ds)",
                        inc.id, self.active_plan["hospital_id"], self.active_plan["eta_seconds"])
            location_label = f"{inc.zone} (NH-44 Gachibowli Junction), Hyderabad"
            await dispatch_hospital_notification(
                db=self.db,
                incident=inc,
                plan=self.active_plan,
                location_label=location_label,
                connection_manager=self.connection_manager,
            )

        await self.db.save_incident(inc)
        await self.connection_manager.broadcast_json(
            {"type": "incident_update", "incident": inc.model_dump()}
        )
        audit_entry = await self.db.append_audit_entry(
            actor="responder_device",
            action=f"RESPONDER_{status}: reported by {source} on mobile device",
            timestamp=now_iso,
        )
        await self.connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry.model_dump()}
        )
        status_msg = "Patient loaded into ambulance — Stage 2 Hospital Green Wave activated" if status == "PATIENT_LOADED" else status.replace('_', ' ').title()
        await self.stream_agent_reasoning(
            "DISPATCH",
            f"Mobile responder telemetry: Ambulance Unit status -> {status_msg}"
        )
        return await self.build_mobile_state()

    async def check_ack_timeout(self, force: bool = False) -> dict:
        now_ms = int(time.time() * 1000)
        if self.ack_deadline_ms and (force or now_ms >= self.ack_deadline_ms):
            inc = await self.db.get_latest_incident()
            if inc and inc.state == "COORDINATION_IN_PROGRESS":
                now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                audit_entry = await self.db.append_audit_entry(
                    actor="safety_governor",
                    action=f"ACK_DEADLINE_EXPIRED: 20s timeout elapsed for {inc.id}",
                    timestamp=now_iso,
                )
                await self.connection_manager.broadcast_json(
                    {"type": "audit_entry", "entry": audit_entry.model_dump()}
                )
        return await self.build_mobile_state()

    async def build_mobile_state(self) -> dict:
        inc = await self.db.get_latest_incident()
        audit_entries = await self.db.get_all_audit_entries()
        audit_check = await self.db.verify_chain()

        mobile_inc = None
        if inc:
            plan = self.active_plan or self.build_dispatch_plan(inc)
            mob_state = inc.state
            if inc.state in ("EN_ROUTE", "ON_SCENE", "PATIENT_LOADED", "HANDED_OVER"):
                mob_state = "ACKNOWLEDGED"

            # Derive authoritative incident coordinates from CityTwin node N_CAM4
            nodes_list = self.twin.snapshot()["nodes"]
            cam_node = next((n for n in nodes_list if n["id"] == "N_CAM4"), None)
            inc_lat = cam_node["lat"] if cam_node else 17.4400
            inc_lon = cam_node["lon"] if cam_node else 78.3480

            mobile_inc = {
                "incident_id": inc.id,
                "scenario": inc.scenario,
                "state": mob_state,
                "field_status": inc.field_status,
                "responder_id": inc.responder_id,
                "location_label": f"{inc.zone} (NH-44 Gachibowli Junction), Hyderabad",
                "lat": inc_lat,
                "lon": inc_lon,
                "camera_id": "CAM-HYD-04",
                "confidence": inc.confidence if inc.confidence is not None else 0.90,
                "verdict": "VERIFIED" if inc.state not in ("REJECTED", "OBSERVED", "CANDIDATE") else inc.state,
                "reason_code": "VERIFIED_DUAL_AGENT_CONSENSUS" if inc.state not in ("REJECTED", "OBSERVED", "CANDIDATE") else "REJECTED_SKEPTIC_VETO",
                "corroboration": {
                    "stance": "INCIDENT",
                    "claim": "Collision signature confirmed by video feed & kinematics",
                    "points": ["Optical flow shockwave detected", "Vehicle deceleration pattern anomalous"],
                    "strength": inc.corroborator_score,
                },
                "skeptic": {
                    "stance": "BENIGN",
                    "claim": "Sensor glare and camera shake evaluation",
                    "points": ["Shadow motion ruled out", "Environmental lighting verified normal"],
                    "strength": inc.skeptic_score,
                },
                "active_plan": plan,
                "plans": [plan],
                "acknowledgements": self.acknowledgements,
                "approved_by": "Operator-1",
                "field_updates": self.field_updates,
            }
            notifs = await self.db.get_notifications_for_incident(inc.id)
            mobile_inc["notifications"] = [
                {
                    "type": n.notification_type,
                    "recipient": n.recipient,
                    "channel": n.channel,
                    "status": n.status,
                    "trigger_event": n.trigger_event,
                    "timestamp": n.timestamp,
                    "provider_id": n.provider_id,
                }
                for n in notifs
            ]

        summary_en = (
            f"Collision alert at {inc.zone if inc else 'Zone 04'}. Destination Osmania General Hospital. "
            "Priority green corridor requested. Slide to acknowledge, or decline if unavailable."
        )
        summary_te = (
            f"{inc.zone if inc else 'Zone 04'} వద్ద ప్రమాద హెచ్చరిక. గమ్యస్థానం ఉస్మానియా జనరల్ హాస్పిటల్. "
            "గ్రీన్ కారిడార్ యాక్టివేట్ చేయబడింది. దయచేసి ధృవీకరించండి."
        )

        audit_list = []
        for e in audit_entries[-50:]:
            try:
                at_ms = int(datetime.fromisoformat(e.timestamp.replace("Z", "+00:00")).timestamp() * 1000)
            except Exception:
                at_ms = int(time.time() * 1000)
            audit_list.append({
                "seq": e.id,
                "at_ms": at_ms,
                "actor": e.actor,
                "action": e.action,
                "result": "OK",
                "state": inc.state if inc else "IDLE",
                "reason_code": e.action.split(":")[0],
                "payload": {"prev_hash": e.previous_hash, "curr_hash": e.current_hash},
            })

        return {
            "scenario": inc.scenario if inc else None,
            "scenarios": {
                "crash_zone04": {"name": "MJ Market Arterial Crash (Zone 04)", "clip": "scenario_a_collision.mp4"},
                "false_alarm": {"name": "False Alarm - Shadow & Reflection", "clip": "scenario_b_false_alarm.mp4"},
            },
            "incident": mobile_inc,
            "twin": self.twin.snapshot(),
            "summary_en": summary_en,
            "summary_te": summary_te,
            "ack_deadline_ms": self.ack_deadline_ms,
            "audit": audit_list,
            "audit_check": {"intact": audit_check.valid, "length": audit_check.checked_blocks},
            "responder_device": {
                "enabled": self.responder_device_enabled,
                "connected": self.device_connected(),
                "stale_after_ms": 5000,
            },
        }

    async def run_post_approval_pipeline(self, incident: Incident) -> None:
        post_states = [
            "OPERATOR_APPROVED",
            "COORDINATION_IN_PROGRESS",
            "ACKNOWLEDGED",
            "CLOSED",
        ]
        prev_state = incident.state

        logger.info("Beginning post-approval pipeline for incident %s", incident.id)

        for next_state in post_states:
            await asyncio.sleep(1.2)

            if not is_valid_transition(prev_state, next_state):
                logger.error(
                    "Illegal post-approval transition for %s: %s -> %s",
                    incident.id,
                    prev_state,
                    next_state,
                )
            else:
                logger.info(
                    "Post-approval transition for %s: %s -> %s",
                    incident.id,
                    prev_state,
                    next_state,
                )

            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            updated_incident = Incident(
                id=incident.id,
                state=next_state,
                zone=incident.zone,
                scenario=incident.scenario,
                corroborator_score=incident.corroborator_score,
                skeptic_score=incident.skeptic_score,
                fused_score=incident.fused_score,
                reasoning=f"{next_state}: dispatch pipeline",
                media_file=incident.media_file,
                timestamp=now_iso,
            )

            await self.db.save_incident(updated_incident)
            await self.connection_manager.broadcast_json(
                {"type": "incident_update", "incident": updated_incident.model_dump()}
            )

            audit_entry = await self.db.append_audit_entry(
                actor="dispatch_coordinator",
                action=f"STATE_TRANSITION: -> {next_state}",
                timestamp=now_iso,
            )
            await self.connection_manager.broadcast_json(
                {"type": "audit_entry", "entry": audit_entry.model_dump()}
            )

            prev_state = next_state

        logger.info("Completed post-approval pipeline for incident %s", incident.id)
