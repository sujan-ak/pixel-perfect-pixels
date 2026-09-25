"""
PIXEL PERFECT PIXELS × AURASHIELD
Emergency Notification Service (Police & Hospital)

Manages Twilio notifications for police and hospital emergency dispatch.
Single source of truth: FastAPI Backend.
Credentials remain strictly on the backend.
"""

from datetime import datetime, timezone
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from database.interface import DatabaseBackend, EmergencyNotification, Incident

logger = logging.getLogger("aurashield.notifications")

# Mock sender hook for automated testing without real network / Twilio traffic
_mock_sender: Optional[Callable[[str, str, str], Tuple[bool, Optional[str], Optional[str]]]] = None
_dispatched_mock_history: List[Dict[str, Any]] = []


def set_notification_sender(
    fn: Optional[Callable[[str, str, str], Tuple[bool, Optional[str], Optional[str]]]]
) -> None:
    """Set custom sender hook for testing. Signature: fn(to, body, channel) -> (success, sid, error)"""
    global _mock_sender
    _mock_sender = fn


def reset_notification_sender() -> None:
    """Reset to default Twilio sender."""
    global _mock_sender, _dispatched_mock_history
    _mock_sender = None
    _dispatched_mock_history.clear()


def get_dispatched_mock_history() -> List[Dict[str, Any]]:
    """Return history of mock dispatched notifications for test inspection."""
    return list(_dispatched_mock_history)


def format_eta(eta_seconds: int) -> str:
    """Format seconds into concise, human-readable ETA."""
    if eta_seconds <= 0:
        return "< 1 min"
    if eta_seconds < 60:
        return f"{eta_seconds} seconds"
    minutes = round(eta_seconds / 60.0, 1)
    if minutes.is_integer():
        return f"~{int(minutes)} min ({eta_seconds}s)"
    return f"~{minutes} min ({eta_seconds}s)"


def format_severity(score: float) -> str:
    """Format severity score into human-readable label."""
    if score >= 0.85:
        label = "CRITICAL"
    elif score >= 0.70:
        label = "HIGH"
    elif score >= 0.50:
        label = "MODERATE"
    else:
        label = "LOW"
    return f"{score:.2f} ({label})"


def build_police_notification_message(
    incident: Incident, location_label: Optional[str] = None
) -> str:
    """
    Build dynamic police alert message.
    Strictly follows requirement:
    PIXEL PERFECT PIXELS ALERT:
    Accident reported near [LOCATION].
    Severity: [SEVERITY].
    Incident ID: [ID].
    Ambulance response initiated.
    Please proceed for enquiry/assistance.
    """
    loc = location_label or f"{incident.zone} (NH-44 Gachibowli Junction), Hyderabad"
    severity_str = format_severity(incident.corroborator_score)
    return (
        f"PIXEL PERFECT PIXELS ALERT:\n"
        f"Accident reported near {loc}.\n"
        f"Severity: {severity_str}.\n"
        f"Incident ID: {incident.id}.\n"
        f"Ambulance response initiated.\n"
        f"Please proceed for enquiry/assistance."
    )


def build_hospital_notification_message(
    incident: Incident, plan: dict, location_label: Optional[str] = None
) -> str:
    """
    Build dynamic hospital transport alert message.
    Strictly follows requirement:
    PIXEL PERFECT PIXELS ALERT:
    Patient from accident near [LOCATION] is being transported to [HOSPITAL].
    Severity: [SEVERITY].
    ETA: [ETA].
    Please prepare bed and required medical resources.
    """
    loc = location_label or f"{incident.zone} (NH-44 Gachibowli Junction), Hyderabad"
    hosp_name = plan.get("hospital_name") or "Emergency Trauma Center"
    eta_sec = plan.get("eta_seconds", 0)
    eta_str = format_eta(eta_sec)
    severity_str = format_severity(incident.corroborator_score)
    return (
        f"PIXEL PERFECT PIXELS ALERT:\n"
        f"Patient from accident near {loc} is being transported to {hosp_name}.\n"
        f"Severity: {severity_str}.\n"
        f"ETA: {eta_str}.\n"
        f"Please prepare bed and required medical resources."
    )


def get_police_recipient() -> str:
    """Resolve recipient phone number for police notifications from environment."""
    return (
        os.getenv("TWILIO_POLICE_TO")
        or os.getenv("TWILIO_DISPATCH_TO")
        or "+917893910211"
    )


def get_hospital_recipient(hospital_id: Optional[str] = None) -> str:
    """Resolve recipient phone number for hospital notifications according to hospital destination."""
    if hospital_id == "H_ALPHA":
        return (
            os.getenv("TWILIO_HOSPITAL_ALPHA_TO")
            or os.getenv("TWILIO_HOSPITAL_TO")
            or os.getenv("TWILIO_NEXT_OF_KIN_TO")
            or os.getenv("TWILIO_DISPATCH_TO")
            or "+917893910211"
        )
    elif hospital_id == "H_BETA":
        return (
            os.getenv("TWILIO_HOSPITAL_BETA_TO")
            or os.getenv("TWILIO_HOSPITAL_TO")
            or os.getenv("TWILIO_NEXT_OF_KIN_TO")
            or os.getenv("TWILIO_DISPATCH_TO")
            or "+917893910211"
        )
    return (
        os.getenv("TWILIO_HOSPITAL_TO")
        or os.getenv("TWILIO_NEXT_OF_KIN_TO")
        or os.getenv("TWILIO_DISPATCH_TO")
        or "+917893910211"
    )


def send_emergency_message(
    to: str, body: str, channel: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Send SMS or WhatsApp message via Twilio backend.
    Returns (success, provider_id, error_message).
    Never logs or exposes credentials.
    """
    global _mock_sender, _dispatched_mock_history

    resolved_channel = (channel or os.getenv("TWILIO_CHANNEL", "sms")).strip().lower()
    if to.startswith("whatsapp:"):
        resolved_channel = "whatsapp"

    if _mock_sender is not None:
        try:
            success, sid, err = _mock_sender(to, body, resolved_channel)
            _dispatched_mock_history.append({
                "to": to,
                "body": body,
                "channel": resolved_channel,
                "success": success,
                "sid": sid,
                "error": err,
            })
            return success, sid, err
        except Exception as e:
            return False, None, str(e)

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        err = "Missing TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN in backend environment"
        logger.warning(err)
        return False, None, err

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        if resolved_channel == "whatsapp":
            from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+17372508034")
            to_number = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        else:
            from_number = (
                os.getenv("TWILIO_FROM_NUMBER")
                or os.getenv("TWILIO_FROM")
                or "+17372508034"
            )
            to_number = to.replace("whatsapp:", "")

        msg = client.messages.create(to=to_number, from_=from_number, body=body)
        logger.info("Twilio notification delivered successfully via %s (SID: %s)", resolved_channel, msg.sid)
        return True, msg.sid, None
    except Exception as e:
        err_code = getattr(e, "code", None)
        err_msg = getattr(e, "msg", str(e))
        detail = f"Twilio Error {err_code}: {err_msg}" if err_code else str(e)
        logger.warning("Twilio notification failed (%s)", detail)
        return False, None, detail


async def dispatch_police_notification(
    db: DatabaseBackend,
    incident: Incident,
    location_label: Optional[str] = None,
    connection_manager: Optional[Any] = None,
) -> Optional[EmergencyNotification]:
    """
    Trigger idempotent Police Emergency Notification upon incident approval.
    """
    # 1. Idempotency Check
    existing = await db.get_notifications_for_incident(incident.id, "POLICE")
    already_sent = any(n.status == "SENT" for n in existing)
    if already_sent:
        logger.info("Police notification for incident %s already SENT (idempotent no-op)", incident.id)
        return None

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    recipient = get_police_recipient()
    channel = os.getenv("TWILIO_CHANNEL", "sms").upper()
    body = build_police_notification_message(incident, location_label)

    # 2. Dispatch via Twilio (or mock sender)
    success, sid, error = send_emergency_message(recipient, body, channel=channel)

    # 3. Persist EmergencyNotification record
    notification = EmergencyNotification(
        incident_id=incident.id,
        notification_type="POLICE",
        recipient=recipient,
        channel=channel,
        trigger_event="INCIDENT_APPROVED",
        timestamp=now_iso,
        status="SENT" if success else "FAILED",
        message_body=body,
        provider_id=sid if success else None,
        error_message=error if not success else None,
    )
    saved_notification = await db.record_notification(notification)

    # 4. Append to Audit Ledger
    action_str = (
        f"POLICE_NOTIFICATION_SENT: {sid or f'{incident.id}-POLICE-DISPATCH'}"
        if success
        else f"POLICE_NOTIFICATION_FAILED: {error or 'Twilio dispatch failed'}"
    )
    audit_entry = await db.append_audit_entry(
        actor="police_dispatcher",
        action=action_str,
        timestamp=now_iso,
    )

    if connection_manager:
        await connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry.model_dump()}
        )
        await connection_manager.broadcast_json(
            {"type": "notification_update", "notification": saved_notification.model_dump()}
        )

    return saved_notification


async def dispatch_hospital_notification(
    db: DatabaseBackend,
    incident: Incident,
    plan: dict,
    location_label: Optional[str] = None,
    connection_manager: Optional[Any] = None,
) -> Optional[EmergencyNotification]:
    """
    Trigger idempotent Hospital Notification ONLY after PATIENT_LOADED (Stage 2).
    Uses the exact Stage 2 routing plan (hospital_id, hospital_name, eta_seconds).
    """
    # 1. Idempotency Check
    existing = await db.get_notifications_for_incident(incident.id, "HOSPITAL")
    already_sent = any(n.status == "SENT" for n in existing)
    if already_sent:
        logger.info("Hospital notification for incident %s already SENT (idempotent no-op)", incident.id)
        return None

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hospital_id = plan.get("hospital_id")
    recipient = get_hospital_recipient(hospital_id)
    channel = os.getenv("TWILIO_CHANNEL", "sms").upper()
    body = build_hospital_notification_message(incident, plan, location_label)

    # 2. Dispatch via Twilio (or mock sender)
    success, sid, error = send_emergency_message(recipient, body, channel=channel)

    # 3. Persist EmergencyNotification record
    notification = EmergencyNotification(
        incident_id=incident.id,
        notification_type="HOSPITAL",
        recipient=recipient,
        channel=channel,
        trigger_event="PATIENT_LOADED",
        timestamp=now_iso,
        status="SENT" if success else "FAILED",
        message_body=body,
        provider_id=sid if success else None,
        error_message=error if not success else None,
    )
    saved_notification = await db.record_notification(notification)

    # 4. Append to Audit Ledger
    action_str = (
        f"HOSPITAL_NOTIFICATION_SENT: {sid or f'{incident.id}-{hospital_id}-CAPACITY'}"
        if success
        else f"HOSPITAL_NOTIFICATION_FAILED: {error or 'Twilio dispatch failed'}"
    )
    audit_entry = await db.append_audit_entry(
        actor="hospital_coordinator",
        action=action_str,
        timestamp=now_iso,
    )

    if connection_manager:
        await connection_manager.broadcast_json(
            {"type": "audit_entry", "entry": audit_entry.model_dump()}
        )
        await connection_manager.broadcast_json(
            {"type": "notification_update", "notification": saved_notification.model_dump()}
        )

    return saved_notification
