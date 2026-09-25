from datetime import datetime, timezone
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Literal, Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from agents.verification import generate_reasoning
from core.state_machine import ConnectionManager, IncidentOrchestrator
from database import get_database, AuditEntry, ChainVerifyResponse, Incident

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
    logger.info("Executing startup warm-up call for Hugging Face reasoning model...")
    warmup_res = await generate_reasoning(
        "OBSERVED", "warmup", "test", 0.5, 0.5, 0.0, fallback="warmup"
    )
    logger.info("Hugging Face warm-up response: %s", warmup_res)
    yield
    logger.info("Shutting down AuraShield backend...")


app = FastAPI(
    title="AuraShield Safety Incident Orchestrator API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.on_event("startup")
async def warm_up_hf():
    await generate_reasoning("OBSERVED", "warmup", "test", 0.5, 0.5, 0.0, fallback="warmup")

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
    scenario: Literal["crash_zone04", "false_alarm"]


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
            incident_id, req.reason or "Operator manual override: marked as false positive"
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
