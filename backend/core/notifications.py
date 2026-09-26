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


def build_police_call_message(
    incident: Incident, location_label: Optional[str] = None
) -> str:
    """
    Build dynamic spoken voice message for Police emergency call.
    Includes explicit demo disclaimer.
    """
    loc = location_label or f"{incident.zone} (NH-44 Gachibowli Junction), Hyderabad"
    severity_str = format_severity(incident.corroborator_score)
    return (
        f"This is an AuraShield demo alert, not a real emergency service call. "
        f"A road accident was reported at {loc}. "
        f"Severity is {severity_str}. "
        f"Incident ID is {incident.id}. "
        f"Ambulance response initiated. Please proceed for assistance."
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


def build_hospital_call_message(
    incident: Incident, plan: dict, location_label: Optional[str] = None
) -> str:
    """
    Build dynamic spoken voice message for Hospital emergency desk call.
    Includes explicit demo disclaimer.
    """
    loc = location_label or f"{incident.zone} (NH-44 Gachibowli Junction), Hyderabad"
    hosp_name = plan.get("hospital_name") or "Emergency Trauma Center"
    eta_sec = plan.get("eta_seconds", 0)
    eta_str = format_eta(eta_sec)
    severity_str = format_severity(incident.corroborator_score)
    return (
        f"This is an AuraShield demo alert, not a real emergency service call. "
        f"Alert for {hosp_name} emergency desk. An accident patient with {severity_str} severity "
        f"from {loc} is coming to your hospital by ambulance. "
        f"Estimated arrival in {eta_str}. Please keep an emergency bed and a doctor ready."
    )


def emergency_refusal(phone: str) -> Optional[str]:
    """Never dial or SMS real emergency numbers or short codes."""
    digits = "".join(c for c in phone if c.isdigit())
    if any(digits.endswith(s) for s in ("112", "108", "100", "101", "102", "911")):
        return f"Refusing real emergency destination: {phone}"
    if len(digits) <= 5 and digits:
        return f"Refusing short-code destination: {phone}"
    return None


def get_police_recipient() -> str:
    """Resolve recipient phone number for police notifications from environment."""
    return (
        os.getenv("POLICE_PHONE")
        or os.getenv("TWILIO_POLICE_TO")
        or os.getenv("TWILIO_DISPATCH_TO")
        or "+917893910211"
    )


def get_hospital_recipient(hospital_id: Optional[str] = None) -> str:
    """Resolve recipient phone number for hospital notifications according to hospital destination."""
    if hospital_id == "H_ALPHA":
        return (
            os.getenv("HOSPITAL_PHONE")
            or os.getenv("TWILIO_HOSPITAL_ALPHA_TO")
            or os.getenv("TWILIO_HOSPITAL_TO")
            or os.getenv("TWILIO_NEXT_OF_KIN_TO")
            or os.getenv("TWILIO_DISPATCH_TO")
            or "+917893910211"
        )
    elif hospital_id == "H_BETA":
        return (
            os.getenv("HOSPITAL_PHONE")
            or os.getenv("TWILIO_HOSPITAL_BETA_TO")
            or os.getenv("TWILIO_HOSPITAL_TO")
            or os.getenv("TWILIO_NEXT_OF_KIN_TO")
            or os.getenv("TWILIO_DISPATCH_TO")
            or "+917893910211"
        )
    return (
        os.getenv("HOSPITAL_PHONE")
        or os.getenv("TWILIO_HOSPITAL_TO")
        or os.getenv("TWILIO_NEXT_OF_KIN_TO")
        or os.getenv("TWILIO_DISPATCH_TO")
        or "+917893910211"
    )


def send_via_android_sms_gateway(
    to: str, body: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Optional local Android SMS Gateway provider (capcom6/android-sms-gateway).
    Sends real SMS via local Android phone's SIM card without Indian DLT restriction.
    Never exposes or logs credentials.
    """
    import base64
    import json as _json
    import urllib.error
    import urllib.request

    gateway_url = os.getenv("SMS_GATEWAY_URL", "").strip().rstrip("/")
    gateway_user = os.getenv("SMS_GATEWAY_USER", "").strip()
    gateway_pass = os.getenv("SMS_GATEWAY_PASS", "")

    if not gateway_url or not gateway_user or not gateway_pass:
        return False, None, "SMS Gateway credentials unconfigured"

    refusal = emergency_refusal(to)
    if refusal:
        return False, None, refusal

    endpoint = f"{gateway_url}/messages"
    payload = _json.dumps({
        "textMessage": {"text": body},
        "phoneNumbers": [to.strip()],
    }).encode("utf-8")

    req = urllib.request.Request(endpoint, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    auth_header = base64.b64encode(f"{gateway_user}:{gateway_pass}".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", f"Basic {auth_header}")

    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read().decode("utf-8", "replace")
            out = _json.loads(raw) if raw.strip() else {}
            msg_id = out.get("id") or out.get("message_id") or "gateway_ok"
            logger.info("Notification successfully dispatched via Android SMS Gateway (ID: %s)", msg_id)
            return True, str(msg_id), None
    except Exception as exc:
        err_msg = f"SMS Gateway Error: {type(exc).__name__}: {exc}"
        logger.warning(err_msg)
        return False, None, err_msg


def send_emergency_message(
    to: str, body: str, channel: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Send emergency alert message via configured notification provider.
    Priority order:
    1. Mock sender hook (for automated unit/integration tests)
    2. Android SMS Gateway (if AURASHIELD_SMS_ENABLED=1 and channel in ('sms', None))
    3. Twilio Provider (SMS, WhatsApp, or Voice with echo fallback)
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

    # 1. Check emergency refusal safety check
    refusal = emergency_refusal(to)
    if refusal:
        logger.warning("Emergency notification refused: %s", refusal)
        return False, None, refusal

    # 2. Check Android SMS Gateway provider (primary hackathon provider for real local SIM SMS)
    sms_gateway_enabled = os.getenv("AURASHIELD_SMS_ENABLED", "0").strip() == "1"
    if sms_gateway_enabled and resolved_channel in ("sms", "text"):
        gw_ok, gw_id, gw_err = send_via_android_sms_gateway(to, body)
        if gw_ok:
            return True, gw_id, None
        logger.warning("Android SMS Gateway attempt unsuccessful, falling back to Twilio: %s", gw_err)

    # 3. Twilio provider (fallback SMS, WhatsApp, or Voice)
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        err = "Missing notification provider configuration (set SMS_GATEWAY_* or TWILIO_* credentials)"
        logger.warning(err)
        return False, None, err

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        if resolved_channel == "whatsapp":
            from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+17372508034")
            to_number = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
            msg = client.messages.create(to=to_number, from_=from_number, body=body)
            logger.info("Twilio notification delivered successfully via whatsapp (SID: %s)", msg.sid)
            return True, msg.sid, None

        elif resolved_channel == "voice":
            from_number = (
                os.getenv("TWILIO_FROM_NUMBER")
                or os.getenv("TWILIO_FROM")
                or "+17372508034"
            )
            # Support DEMO_CALLS_TO for Twilio trial accounts
            target_phone = os.getenv("DEMO_CALLS_TO") or to.replace("whatsapp:", "")
            twiml = f"<Response><Say voice='alice'>{body}</Say></Response>"
            try:
                call_res = client.calls.create(to=target_phone, from_=from_number, twiml=twiml)
                logger.info("Twilio voice call placed successfully (SID: %s)", call_res.sid)
                return True, call_res.sid, None
            except Exception as call_err:
                # Auto-fallback to echo url for Twilio trial accounts on 400 parameter rejection
                import urllib.parse
                echo_url = "https://twimlets.com/echo?Twiml=" + urllib.parse.quote(twiml)
                call_res = client.calls.create(to=target_phone, from_=from_number, url=echo_url)
                logger.info("Twilio voice call placed via echo URL fallback (SID: %s)", call_res.sid)
                return True, call_res.sid, None

        else:  # SMS
            from_number = (
                os.getenv("TWILIO_FROM_NUMBER")
                or os.getenv("TWILIO_FROM")
                or "+17372508034"
            )
            to_number = to.replace("whatsapp:", "")
            msg = client.messages.create(to=to_number, from_=from_number, body=body)
            logger.info("Twilio notification delivered successfully via sms (SID: %s)", msg.sid)
            return True, msg.sid, None

    except Exception as e:
        err_code = getattr(e, "code", None)
        err_msg = getattr(e, "msg", str(e))
        detail = f"Twilio Error {err_code}: {err_msg}" if err_code else str(e)
        if err_code == 21219 or "trial accounts have limited parameter access" in detail:
            detail += " (trial account: recipient must be a Verified Caller ID in Twilio console, or set DEMO_CALLS_TO / AURASHIELD_SMS_ENABLED=1)"
        logger.warning("Twilio notification failed (%s)", detail)
        return False, None, detail


async def dispatch_police_notification(
    db: DatabaseBackend,
    incident: Incident,
    location_label: Optional[str] = None,
    connection_manager: Optional[Any] = None,
    channel: Optional[str] = None,
) -> Optional[EmergencyNotification]:
    """
    Trigger idempotent Police Emergency Notification upon incident approval.
    Dispatches Police SMS and attempts Police CALL (voice).
    If channel is 'SMS' or 'VOICE', executes that specific channel.
    If channel is None, executes both SMS and CALL.
    """
    if channel is None:
        sms_notif = await dispatch_police_notification(
            db=db,
            incident=incident,
            location_label=location_label,
            connection_manager=connection_manager,
            channel="SMS",
        )
        call_notif = await dispatch_police_notification(
            db=db,
            incident=incident,
            location_label=location_label,
            connection_manager=connection_manager,
            channel="VOICE",
        )
        return sms_notif or call_notif

    resolved_channel = channel.upper()
    existing = await db.get_notifications_for_incident(
        incident.id, "POLICE", channel=resolved_channel
    )
    if any(n.status == "SENT" for n in existing):
        logger.info(
            "Police %s notification for incident %s already SENT (idempotent no-op)",
            resolved_channel,
            incident.id,
        )
        return None

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    recipient = get_police_recipient()

    if resolved_channel == "VOICE":
        body = build_police_call_message(incident, location_label)
        success, sid, error = send_emergency_message(recipient, body, channel="voice")
        action_prefix = "POLICE_CALL"
    else:  # SMS
        body = build_police_notification_message(incident, location_label)
        success, sid, error = send_emergency_message(recipient, body, channel="sms")
        action_prefix = "POLICE_NOTIFICATION"

    notification = EmergencyNotification(
        incident_id=incident.id,
        notification_type="POLICE",
        recipient=recipient,
        channel=resolved_channel,
        trigger_event="INCIDENT_APPROVED",
        timestamp=now_iso,
        status="SENT" if success else "FAILED",
        message_body=body,
        provider_id=sid if success else None,
        error_message=error if not success else None,
    )
    saved_notification = await db.record_notification(notification)

    action_str = (
        f"{action_prefix}_SENT: {sid or f'{incident.id}-POLICE-{resolved_channel}'}"
        if success
        else f"{action_prefix}_FAILED: {error or f'Police {resolved_channel} dispatch failed'}"
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
    channel: Optional[str] = None,
) -> Optional[EmergencyNotification]:
    """
    Trigger idempotent Hospital Notification ONLY after PATIENT_LOADED (Stage 2).
    Dispatches Hospital SMS and attempts Hospital CALL (voice).
    If channel is 'SMS' or 'VOICE', executes that specific channel.
    If channel is None, executes both SMS and CALL.
    """
    if channel is None:
        sms_notif = await dispatch_hospital_notification(
            db=db,
            incident=incident,
            plan=plan,
            location_label=location_label,
            connection_manager=connection_manager,
            channel="SMS",
        )
        call_notif = await dispatch_hospital_notification(
            db=db,
            incident=incident,
            plan=plan,
            location_label=location_label,
            connection_manager=connection_manager,
            channel="VOICE",
        )
        return sms_notif or call_notif

    resolved_channel = channel.upper()
    existing = await db.get_notifications_for_incident(
        incident.id, "HOSPITAL", channel=resolved_channel
    )
    if any(n.status == "SENT" for n in existing):
        logger.info(
            "Hospital %s notification for incident %s already SENT (idempotent no-op)",
            resolved_channel,
            incident.id,
        )
        return None

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hospital_id = plan.get("hospital_id")
    recipient = get_hospital_recipient(hospital_id)

    if resolved_channel == "VOICE":
        body = build_hospital_call_message(incident, plan, location_label)
        success, sid, error = send_emergency_message(recipient, body, channel="voice")
        action_prefix = "HOSPITAL_CALL"
    else:  # SMS
        body = build_hospital_notification_message(incident, plan, location_label)
        success, sid, error = send_emergency_message(recipient, body, channel="sms")
        action_prefix = "HOSPITAL_NOTIFICATION"

    notification = EmergencyNotification(
        incident_id=incident.id,
        notification_type="HOSPITAL",
        recipient=recipient,
        channel=resolved_channel,
        trigger_event="PATIENT_LOADED",
        timestamp=now_iso,
        status="SENT" if success else "FAILED",
        message_body=body,
        provider_id=sid if success else None,
        error_message=error if not success else None,
    )
    saved_notification = await db.record_notification(notification)

    action_str = (
        f"{action_prefix}_SENT: {sid or f'{incident.id}-{hospital_id}-{resolved_channel}'}"
        if success
        else f"{action_prefix}_FAILED: {error or f'Hospital {resolved_channel} dispatch failed'}"
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
