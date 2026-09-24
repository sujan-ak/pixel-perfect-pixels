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
    generate_reasoning,
)
from database.audit import AuditDatabase, AuditEntry, Incident

logger = logging.getLogger("aurashield.core.state_machine")

LEGAL_TRANSITIONS: Dict[Optional[str], Set[str]] = {
    None: {"OBSERVED"},
    "OBSERVED": {"CANDIDATE"},
    "CANDIDATE": {"VERIFIED", "REJECTED"},
    "VERIFIED": {"RESPONSE_PROPOSED"},
    "RESPONSE_PROPOSED": {"OPERATOR_APPROVED"},
    "OPERATOR_APPROVED": {"COORDINATION_IN_PROGRESS"},
    "COORDINATION_IN_PROGRESS": {"ACKNOWLEDGED"},
    "ACKNOWLEDGED": {"CLOSED"},
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
    def __init__(self, db: AuditDatabase, connection_manager: ConnectionManager) -> None:
        self.db = db
        self.connection_manager = connection_manager
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.incident_counter: int = 0
        self.last_scenario_times: Dict[str, float] = {}
        self.running_scenarios: Dict[str, str] = {}  # scenario -> incident_id
        self._lock = asyncio.Lock()

    async def get_next_incident_id(self) -> str:
        async with self._lock:
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
            if t.exception():
                logger.error(
                    "Pipeline for incident %s failed with exception: %s",
                    incident_id,
                    t.exception(),
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

        for i, step in enumerate(steps):
            if i > 0:
                await asyncio.sleep(1.4)

            new_state = step["state"]
            if not is_valid_transition(prev_state, new_state):
                logger.error(
                    "Illegal transition attempted for %s: %s -> %s",
                    incident_id,
                    prev_state,
                    new_state,
                )
                # Still log and proceed gracefully with fixture for demo resilience
            else:
                logger.info(
                    "Transition for %s: %s -> %s",
                    incident_id,
                    prev_state or "None",
                    new_state,
                )

            # Self-check assertion on final step
            if i == len(steps) - 1:
                assert_terminal_state_matches(
                    fixture_state=new_state,
                    corroborator_score=step["corroborator_score"],
                    skeptic_score=step["skeptic_score"],
                )

            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            reasoning = await generate_reasoning(
                state=new_state,
                scenario=scenario,
                zone=zone,
                corroborator_score=step["corroborator_score"],
                skeptic_score=step["skeptic_score"],
                fused_score=step["fused_score"],
                fallback=step["reasoning"],
            )

            incident = Incident(
                id=incident_id,
                state=new_state,
                zone=zone,
                scenario=scenario,
                corroborator_score=step["corroborator_score"],
                skeptic_score=step["skeptic_score"],
                fused_score=step["fused_score"],
                reasoning=reasoning,
                media_file=media_file,
                timestamp=now_iso,
            )

            # Persist incident
            await self.db.save_incident(incident)

            # Broadcast incident_update
            await self.connection_manager.broadcast_json(
                {"type": "incident_update", "incident": incident.model_dump()}
            )

            # Paired audit entry
            if i == 0:
                actor = "system"
                action = f"INCIDENT_CREATED: {incident_id}"
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

        logger.info("Completed scenario pipeline for %s (%s)", incident_id, scenario)

    async def approve_incident(self, incident_id: str) -> dict:
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

        dispatch_to = os.getenv("TWILIO_DISPATCH_TO") or "+919876543210"
        from_number = os.getenv("TWILIO_FROM_NUMBER") or "AURASHIELD"
        whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        sms_body = f"VERIFIED INCIDENT {incident.zone} — severity {incident.corroborator_score:.2f} — dispatch requested"

        sms_payload = {
            "to": f"whatsapp:{dispatch_to}",
            "from": whatsapp_from,
            "body": sms_body,
            "timestamp": now_iso,
        }

        # 1. Real Twilio WhatsApp - Dispatch (WhatsApp sandbox channel)
        # Fallback for future DLT-registered account (SMS):
        # msg = client.messages.create(to=dispatch_to, from_=from_number, body=sms_body)
        twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        try:
            from twilio.rest import Client

            client = Client(twilio_account_sid, twilio_auth_token)
            msg = client.messages.create(
                to=f"whatsapp:{dispatch_to}", from_=whatsapp_from, body=sms_body
            )
            audit_action = f"WHATSAPP_SENT: {msg.sid}"
            logger.info("Twilio dispatch WhatsApp sent successfully: %s", msg.sid)
        except Exception as e:
            err_code = getattr(e, "code", None)
            err_msg = getattr(e, "msg", str(e))
            detail = f"Error {err_code}: {err_msg}" if err_code else str(e)
            logger.error("Twilio WhatsApp send failed: %s", detail)
            audit_action = f"WHATSAPP_SEND_FAILED: {detail}"

        audit_entry_sms = await self.db.append_audit_entry(
            actor="dispatch_coordinator",
            action=audit_action,
            timestamp=now_iso,
        )
        await self.connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry_sms.model_dump()}
        )

        # 2. Real Twilio WhatsApp - Next-of-Kin (WhatsApp sandbox channel)
        # Fallback for future DLT-registered account (SMS):
        # msg2 = client.messages.create(to=next_of_kin_to, from_=from_number, body=nok_body)
        next_of_kin_to = os.getenv("TWILIO_NEXT_OF_KIN_TO") or dispatch_to
        nok_body = f"Family notification: incident at {incident.zone} — dispatch coordinator has been notified. Reference: {incident.id}"
        try:
            from twilio.rest import Client

            client = Client(twilio_account_sid, twilio_auth_token)
            msg2 = client.messages.create(
                to=f"whatsapp:{next_of_kin_to}", from_=whatsapp_from, body=nok_body
            )
            nok_action = f"NEXT_OF_KIN_WHATSAPP_SENT: {msg2.sid}"
            logger.info("Twilio next-of-kin WhatsApp sent successfully: %s", msg2.sid)
        except Exception as e:
            err_code2 = getattr(e, "code", None)
            err_msg2 = getattr(e, "msg", str(e))
            detail2 = f"Error {err_code2}: {err_msg2}" if err_code2 else str(e)
            logger.error("Twilio next-of-kin WhatsApp send failed: %s", detail2)
            nok_action = f"NEXT_OF_KIN_WHATSAPP_FAILED: {detail2}"

        audit_entry_nok = await self.db.append_audit_entry(
            actor="dispatch_coordinator",
            action=nok_action,
            timestamp=now_iso,
        )
        await self.connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry_nok.model_dump()}
        )

        # Asynchronously run post-approval sequence
        asyncio.create_task(
            self.run_post_approval_pipeline(incident),
            name=f"post-approval-{incident.id}",
        )

        return {"status": "approved", "sms_payload": sms_payload}

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
