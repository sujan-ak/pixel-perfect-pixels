import asyncio
from datetime import datetime, timezone
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, List, Literal, Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from agents.verification import generate_reasoning
from core.state_machine import ConnectionManager, IncidentOrchestrator
from database import get_database, AuditEntry, ChainVerifyResponse, Incident
from memory import (
    memory,
    MemoryEvent,
    MemoryStatus,
    Precedent,
    MemoryToggleRequest,
    InsightsResponse,
    LearningCurvePoint,
    MemorySeedResponse,
    MemoryResetResponse,
)
from seed_memory import seed_memory, reset_memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aurashield.main")

PORT = int(os.getenv("PORT", "8000"))
ALLOWED_ORIGIN_STR = os.getenv(
    "ALLOWED_ORIGIN", "http://localhost:5173,http://localhost:3000,http://localhost:8080,http://127.0.0.1:8080"
)
ALLOWED_ORIGINS = [orig.strip() for orig in ALLOWED_ORIGIN_STR.split(",") if orig.strip()]
DATABASE_PATH = os.getenv("DATABASE_PATH", "aurashield.db")

db = get_database()
connection_manager = ConnectionManager()
orchestrator = IncidentOrchestrator(db=db, connection_manager=connection_manager)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    backend_mode = os.getenv("DB_BACKEND", "sqlite").lower()
    logger.info("Initializing AuraShield backend with active DB_BACKEND='%s'", backend_mode)
    await db.init_db()

    async def _async_warmup():
        try:
            logger.info("Executing non-blocking background warm-up call for Hugging Face reasoning model...")
            warmup_res = await asyncio.wait_for(
                generate_reasoning("OBSERVED", "warmup", "test", 0.5, 0.5, 0.0, fallback="warmup"),
                timeout=5.0,
            )
            logger.info("Hugging Face warm-up response: %s", warmup_res)
        except Exception as e:
            logger.warning("Hugging Face warm-up timed out or failed (non-blocking): %s", e)

    asyncio.create_task(_async_warmup())
    yield
    logger.info("Shutting down AuraShield backend...")


app = FastAPI(
    title="AuraShield Safety Incident Orchestrator API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas
class TriggerRequest(BaseModel):
    scenario: Literal["crash_zone04", "false_alarm", "glare_ambiguous"]


class TriggerResponse(BaseModel):
    incident_id: str


class SmsPayload(BaseModel):
    to: str
    from_: str = Field(alias="from")
    body: str
    timestamp: str

    model_config = ConfigDict(populate_by_name=True)


class ApproveResponse(BaseModel):
    status: str
    sms_payload: SmsPayload


class OverrideRejectRequest(BaseModel):
    reason: Optional[str] = "Operator manual override: marked as false positive"
    cause_tag: Optional[str] = None


class OverrideRejectResponse(BaseModel):
    status: str
    incident_id: str
    reason: str


class SensitivityRequest(BaseModel):
    sensitivity: float


class PauseRequest(BaseModel):
    paused: bool


# Routes
@app.get("/health", status_code=status.HTTP_200_OK, summary="API Health Check")
async def health_check():
    return {
        "status": "healthy",
        "governor_sensitivity": orchestrator.governor_sensitivity,
        "automation_paused": orchestrator.automation_paused,
    }


@app.post(
    "/incidents/trigger",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TriggerResponse,
    summary="Trigger safety incident scenario",
)
async def trigger_incident(req: TriggerRequest) -> TriggerResponse:
    try:
        incident_id = await orchestrator.trigger_scenario(req.scenario)
        logger.info("Triggered scenario '%s' -> assigned incident '%s'", req.scenario, incident_id)
        return TriggerResponse(incident_id=incident_id)
    except ValueError as e:
        logger.warning("Trigger rejected with 409 conflict: %s", e)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@app.post(
    "/incidents/{incident_id}/approve",
    status_code=status.HTTP_200_OK,
    response_model=ApproveResponse,
    summary="Approve dispatch for a verified incident",
)
async def approve_incident(incident_id: str) -> ApproveResponse:
    try:
        res = await orchestrator.approve_incident(incident_id)
        return ApproveResponse(**res)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@app.post(
    "/incidents/{incident_id}/override-reject",
    status_code=status.HTTP_200_OK,
    response_model=OverrideRejectResponse,
    summary="Operator manually overrides and rejects a candidate/verified incident",
)
async def override_reject(
    incident_id: str, req: OverrideRejectRequest = OverrideRejectRequest()
) -> OverrideRejectResponse:
    try:
        res = await orchestrator.override_reject_incident(
            incident_id=incident_id,
            reason=req.reason or "Operator manual override: marked as false positive",
            cause_tag=req.cause_tag,
        )
        return OverrideRejectResponse(**res)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Override reject failed for %s: %s", incident_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post(
    "/governor/sensitivity",
    status_code=status.HTTP_200_OK,
    summary="Set safety governor confidence sensitivity threshold (0.50 - 0.95)",
)
async def set_governor_sensitivity(req: SensitivityRequest) -> dict:
    val = round(max(0.50, min(0.95, req.sensitivity)), 2)
    orchestrator.governor_sensitivity = val
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    audit = await db.append_audit_entry(
        actor="operator_1",
        action=f"GOVERNOR_SENSITIVITY_SET: threshold={val:.2f}",
        timestamp=now_iso,
    )
    await connection_manager.broadcast_json({"type": "audit_entry", "entry": audit.model_dump()})
    await connection_manager.broadcast_json({"type": "governor_sensitivity", "sensitivity": val})
    return {"sensitivity": val}


@app.post(
    "/governor/pause",
    status_code=status.HTTP_200_OK,
    summary="Toggle operator pause automation",
)
async def set_automation_pause(req: PauseRequest) -> dict:
    orchestrator.automation_paused = req.paused
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    action = "AUTOMATION_PAUSED_BY_OPERATOR" if req.paused else "AUTOMATION_RESUMED_BY_OPERATOR"
    audit = await db.append_audit_entry(
        actor="operator_1",
        action=action,
        timestamp=now_iso,
    )
    await connection_manager.broadcast_json({"type": "audit_entry", "entry": audit.model_dump()})
    await connection_manager.broadcast_json({"type": "automation_pause_status", "paused": req.paused})
    return {"paused": req.paused}


@app.get(
    "/incidents/history",
    status_code=status.HTTP_200_OK,
    response_model=List[Incident],
    summary="Get history of resolved and rejected incidents",
)
async def get_incident_history() -> List[Incident]:
    history = await db.get_incident_history()
    return history


@app.get(
    "/audit/verify",
    status_code=status.HTTP_200_OK,
    response_model=ChainVerifyResponse,
    summary="Verify immutable audit ledger hash chain",
)
async def verify_audit_ledger() -> ChainVerifyResponse:
    result = await db.verify_chain()
    logger.info(
        "Audit ledger verification: valid=%s, checked_blocks=%d, broken_at=%s",
        result.valid,
        result.checked_blocks,
        result.broken_at,
    )
    return result


@app.get(
    "/audit/entries",
    status_code=status.HTTP_200_OK,
    response_model=List[AuditEntry],
    summary="Get all immutable audit ledger entries in chronological order",
)
async def get_audit_entries() -> List[AuditEntry]:
    return await db.get_all_audit_entries()


@app.get(
    "/audit/history",
    status_code=status.HTTP_200_OK,
    response_model=List[AuditEntry],
    summary="Get all immutable audit ledger entries (alias for /audit/entries)",
)
async def get_audit_history() -> List[AuditEntry]:
    return await db.get_all_audit_entries()



class SignalActuationRequest(BaseModel):
    signal_id: str
    junction_name: str
    color: str = "GREEN"
    time_saved: str = "4 min 20 sec"


@app.post(
    "/corridor/signal-actuate",
    status_code=status.HTTP_200_OK,
    summary="[P6] Record municipal traffic signal override actuation block in audit ledger",
)
async def log_signal_actuation(req: SignalActuationRequest) -> dict:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    action_str = f"MUNICIPAL_SIGNAL_ACTUATION: {req.signal_id} ({req.junction_name}) -> {req.color} [GREEN_CORRIDOR_ACTIVE | TIME_SAVED: {req.time_saved}]"
    audit = await db.append_audit_entry(
        actor="municipal_signal_api",
        action=action_str,
        timestamp=now_iso,
    )
    await connection_manager.broadcast_json({"type": "audit_entry", "entry": audit.model_dump()})
    return {"status": "actuated", "signal_id": req.signal_id, "audit_id": audit.id, "hash": audit.current_hash}


# AuraShield Mobile Responder Integration Models
class ResponderDeviceReq(BaseModel):
    enabled: bool = True


class AckReq(BaseModel):
    source: str = "responder_iphone"
    channel: str = "responder_device"


class DeclineReq(BaseModel):
    source: str = "responder_iphone"


class FieldStatusReq(BaseModel):
    source: str = "responder_iphone"
    status: str = Field(..., pattern="^(EN_ROUTE|ON_SCENE|PATIENT_LOADED|HANDED_OVER)$")


class TimeoutReq(BaseModel):
    force: bool = False


# Asset paths for AuraShield tiles and video clips
DATA_DIR = Path(__file__).resolve().parent.parent / "AuraShield-master" / "AuraShield-master" / "data"
TILES_DIR = (DATA_DIR / "tiles").resolve()
VIDEO_DIR = (DATA_DIR / "video").resolve()


# AuraShield Mobile Compatibility Routes
@app.get("/api/state", summary="[AuraShield] Unified state snapshot for mobile responder")
async def get_mobile_state(client: str = "") -> dict:
    if client == "responder":
        orchestrator.device_heartbeat()
    return await orchestrator.build_mobile_state()


@app.post("/api/responder_device", summary="[AuraShield] Toggle mobile responder on-duty state")
async def set_responder_device(req: ResponderDeviceReq) -> dict:
    return await orchestrator.set_responder_device(req.enabled)


@app.post("/api/ack", summary="[AuraShield] Mobile responder acknowledges dispatch")
async def responder_ack(req: AckReq) -> dict:
    orchestrator.device_heartbeat()
    return await orchestrator.acknowledge_dispatch(source=req.source, channel=req.channel)


@app.post("/api/decline", summary="[AuraShield] Mobile responder declines dispatch")
async def responder_decline(req: DeclineReq) -> dict:
    orchestrator.device_heartbeat()
    return await orchestrator.decline_dispatch(source=req.source)


@app.post("/api/field_status", summary="[AuraShield] Advance trip status: EN_ROUTE -> ON_SCENE -> PATIENT_LOADED -> HANDED_OVER")
async def responder_field_status(req: FieldStatusReq) -> dict:
    orchestrator.device_heartbeat()
    return await orchestrator.update_field_status(source=req.source, status=req.status)


@app.post("/api/timeout", summary="[AuraShield] Check dispatch acknowledgement deadline")
async def responder_timeout(req: TimeoutReq) -> dict:
    return await orchestrator.check_ack_timeout(force=req.force)


@app.get("/api/assets", summary="[AuraShield] Check cached map tiles and video assets")
async def get_assets() -> dict:
    style = TILES_DIR / "style.txt"
    attrib = TILES_DIR / "ATTRIBUTION.txt"
    return {
        "tiles_cached": TILES_DIR.is_dir() and any(TILES_DIR.glob("*/*/*.png")),
        "tile_style": style.read_text().strip() if style.is_file() else None,
        "tile_attribution": (attrib.read_text().strip().splitlines()[0] if attrib.is_file() else None),
        "videos": (sorted(p.name for p in VIDEO_DIR.glob("*.mp4")) if VIDEO_DIR.is_dir() else []),
    }


@app.get("/tiles/{rel:path}", include_in_schema=False)
async def serve_tile(rel: str) -> FileResponse:
    target = (TILES_DIR / rel).resolve()
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Tile not found")
    return FileResponse(target, media_type="image/png")


@app.get("/video/{rel:path}", include_in_schema=False)
async def serve_video(rel: str) -> FileResponse:
    target = (VIDEO_DIR / rel).resolve()
    if not target.is_file():
        media_fallback = Path(__file__).resolve().parent.parent / "pixel-perfect-pixels-main" / "public" / "media" / rel
        if media_fallback.is_file():
            return FileResponse(media_fallback, media_type="video/mp4")
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(target, media_type="video/mp4")


# Demo Endpoints (Demonstration-only, not part of production contract)
class DemoTamperResponse(BaseModel):
    tampered_row_id: int
    zone: str


class DemoRestoreResponse(BaseModel):
    restored_row_id: int


@app.post(
    "/demo/tamper",
    status_code=status.HTTP_200_OK,
    response_model=DemoTamperResponse,
    summary="[DEMO ONLY] Simulate adversary tampering with an audit ledger row",
)
async def demo_tamper() -> DemoTamperResponse:
    try:
        res = await db.tamper_demo_row()
        all_entries = await db.get_all_audit_entries()
        await connection_manager.broadcast_json(
            {"type": "audit_sync", "entries": [e.model_dump() for e in all_entries]}
        )
        return DemoTamperResponse(**res)
    except Exception as e:
        logger.error("Demo tamper failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post(
    "/demo/restore",
    status_code=status.HTTP_200_OK,
    response_model=DemoRestoreResponse,
    summary="[DEMO ONLY] Revert tampered audit ledger row back to authentic state",
)
async def demo_restore() -> DemoRestoreResponse:
    try:
        res = await db.restore_demo_row()
        all_entries = await db.get_all_audit_entries()
        await connection_manager.broadcast_json(
            {"type": "audit_sync", "entries": [e.model_dump() for e in all_entries]}
        )
        return DemoRestoreResponse(**res)
    except Exception as e:
        logger.error("Demo restore failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# -----------------------------------------------------------------------------
# Memory Subsystem Endpoints (Phase 7)
# -----------------------------------------------------------------------------
_insights_cache = {
    "ts": 0.0,
    "data": None,
}


@app.get(
    "/memory/status",
    status_code=status.HTTP_200_OK,
    response_model=MemoryStatus,
    summary="Get current memory subsystem status",
)
async def get_memory_status() -> MemoryStatus:
    return await memory.status()


@app.post(
    "/memory/toggle",
    status_code=status.HTTP_200_OK,
    response_model=MemoryStatus,
    summary="Toggle memory subsystem enabled state",
)
async def toggle_memory(req: MemoryToggleRequest) -> MemoryStatus:
    memory.enabled = req.enabled
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    action = f"MEMORY_TOGGLED: enabled={req.enabled}"
    audit_entry = await db.append_audit_entry(
        actor="operator",
        action=action,
        timestamp=now_iso,
    )
    await connection_manager.broadcast_json(
        {"type": "audit_entry", "entry": audit_entry.model_dump()}
    )
    st = await memory.status()
    await connection_manager.broadcast_json(
        {"type": "memory_status", "status": st.model_dump()}
    )
    logger.info("Memory toggled: enabled=%s", req.enabled)
    return st


@app.get(
    "/memory/recall",
    status_code=status.HTTP_200_OK,
    response_model=List[Precedent],
    summary="Recall memory precedents by query and zone",
)
async def recall_memory(
    q: str = "",
    zone: Optional[str] = None,
    limit: int = 5,
) -> List[Precedent]:
    return await memory.recall(query=q, zone=zone, limit=limit)


@app.get(
    "/memory/insights",
    status_code=status.HTTP_200_OK,
    response_model=InsightsResponse,
    summary="Synthesize high-level operational memory insights with 60s cache",
)
async def get_memory_insights() -> InsightsResponse:
    now = time.time()
    if _insights_cache["data"] is not None and (now - _insights_cache["ts"]) < 60.0:
        cached_data = dict(_insights_cache["data"])
        cached_data["cached"] = True
        return InsightsResponse(**cached_data)

    prompt = (
        "What recurring patterns have operators confirmed as false alarms or real incidents, "
        "and which hospitals decline at peak hours?"
    )
    insights_text = await memory.reflect(prompt)
    data = {
        "insights": insights_text,
        "cached": False,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _insights_cache["ts"] = now
    _insights_cache["data"] = data
    return InsightsResponse(**data)


@app.get(
    "/memory/timeline",
    status_code=status.HTTP_200_OK,
    response_model=List[MemoryEvent],
    summary="Get recent memory events timeline",
)
async def get_memory_timeline(limit: int = 50) -> List[MemoryEvent]:
    return await memory.ledger.query(limit=limit)


@app.post(
    "/memory/seed",
    status_code=status.HTTP_200_OK,
    response_model=MemorySeedResponse,
    summary="[DEMO ONLY] Seed realistic incident memory history",
)
async def api_seed_memory() -> MemorySeedResponse:
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode disabled")
    res = await seed_memory(reset=False, limit_n=30, close_client=False)
    st = await memory.status()
    await connection_manager.broadcast_json(
        {"type": "memory_status", "status": st.model_dump()}
    )
    return MemorySeedResponse(**res)


@app.post(
    "/memory/reset",
    status_code=status.HTTP_200_OK,
    response_model=MemoryResetResponse,
    summary="[DEMO ONLY] Reset local ledger and demo memory bank",
)
async def api_reset_memory() -> MemoryResetResponse:
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode disabled")
    res = await reset_memory(close_client=False)
    st = await memory.status()
    await connection_manager.broadcast_json(
        {"type": "memory_status", "status": st.model_dump()}
    )
    return MemoryResetResponse(**res)


@app.get(
    "/memory/learning-curve",
    status_code=status.HTTP_200_OK,
    response_model=List[LearningCurvePoint],
    summary="Get per-run memory learning curve series",
)
async def get_learning_curve() -> List[LearningCurvePoint]:
    events = await memory.ledger.query(limit=250)
    # Terminal pipeline runs
    terminal_events = [e for e in events if e.kind in ("INCIDENT_VERIFIED", "INCIDENT_REJECTED")]
    terminal_events.sort(key=lambda x: x.ts)

    points: List[LearningCurvePoint] = []

    # If fewer than 5 live runs exist, include historical learning curve from seeded overrides & approvals
    if len(terminal_events) < 5:
        historical_ops = [
            e for e in events if e.kind in ("OPERATOR_OVERRIDE", "OPERATOR_APPROVED")
        ]
        historical_ops.sort(key=lambda x: x.ts)
        seen_overrides = 0
        seen_approvals = 0
        for ev in historical_ops:
            if ev.kind == "OPERATOR_OVERRIDE":
                seen_overrides += 1
                prec = seen_overrides
                pre_f = round(0.42 + (0.01 * (seen_overrides % 5)), 2)
                post_f = round(max(-0.25, 0.42 - (0.06 * seen_overrides)), 2)
                points.append(
                    LearningCurvePoint(
                        run=len(points) + 1,
                        scenario=ev.scenario or "glare_ambiguous",
                        pre_memory_fused=pre_f,
                        post_memory_fused=post_f,
                        verdict="REJECTED",
                        precedents=prec,
                        timestamp=ev.ts,
                    )
                )
            elif ev.kind == "OPERATOR_APPROVED":
                seen_approvals += 1
                prec = seen_approvals
                fused = round(ev.fused_score or 0.77, 2)
                points.append(
                    LearningCurvePoint(
                        run=len(points) + 1,
                        scenario=ev.scenario or "crash_zone04",
                        pre_memory_fused=fused,
                        post_memory_fused=fused,
                        verdict="VERIFIED",
                        precedents=prec,
                        timestamp=ev.ts,
                    )
                )

    # Append live terminal events
    base_run = len(points)
    for idx, ev in enumerate(terminal_events, start=1):
        pre_f = ev.pre_memory_fused if ev.pre_memory_fused is not None else (ev.fused_score or 0.0)
        post_f = ev.post_memory_fused if ev.post_memory_fused is not None else (ev.fused_score or 0.0)
        verdict = "VERIFIED" if ev.kind == "INCIDENT_VERIFIED" else "REJECTED"
        prec = ev.precedents_count if ev.precedents_count is not None else 0
        points.append(
            LearningCurvePoint(
                run=base_run + idx,
                scenario=ev.scenario,
                pre_memory_fused=round(pre_f, 2),
                post_memory_fused=round(post_f, 2),
                verdict=verdict,
                precedents=prec,
                timestamp=ev.ts,
            )
        )

    return points


@app.get(
    "/audit/entries",
    status_code=status.HTTP_200_OK,
    response_model=List[AuditEntry],
    summary="Get all audit ledger entries",
)
async def get_audit_entries() -> List[AuditEntry]:
    return await db.get_all_audit_entries()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await connection_manager.connect(websocket)
    try:
        # Replay current incident if present
        latest_incident = await db.get_latest_incident()
        audit_entries = await db.get_all_audit_entries()
        await connection_manager.replay_to_client(
            websocket, latest_incident=latest_incident, audit_entries=audit_entries
        )
        await websocket.send_json(
            {"type": "governor_sensitivity", "sensitivity": orchestrator.governor_sensitivity}
        )
        await websocket.send_json(
            {"type": "automation_pause_status", "paused": orchestrator.automation_paused}
        )
        mem_status = await memory.status()
        await websocket.send_json(
            {"type": "memory_status", "status": mem_status.model_dump()}
        )

        while True:
            # Keep socket alive and listen for client frames
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket client connection error: %s", e)
        connection_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
