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
from database.audit import AuditDatabase, AuditEntry, ChainVerifyResponse, Incident

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

db = AuditDatabase(db_path=DATABASE_PATH)
connection_manager = ConnectionManager()
orchestrator = IncidentOrchestrator(db=db, connection_manager=connection_manager)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Initializing AuraShield backend with database at %s", DATABASE_PATH)
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


# Routes
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
