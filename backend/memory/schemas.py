"""
Pydantic schemas for AuraShield Hindsight Memory Subsystem.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


MemoryKind = Literal[
    "INCIDENT_VERIFIED",
    "INCIDENT_REJECTED",
    "OPERATOR_APPROVED",
    "OPERATOR_OVERRIDE",
    "DISPATCH_ACKED",
    "DISPATCH_DECLINED",
    "ACK_TIMEOUT",
    "INCIDENT_CLOSED",
]


class MemoryEvent(BaseModel):
    event_id: str
    ts: str
    kind: MemoryKind
    incident_id: str
    zone: str
    scenario: str
    cause_tags: List[str] = Field(default_factory=list)
    operator_action: Optional[str] = None
    outcome: Optional[str] = None
    confidence: Optional[float] = 0.90
    corr_score: Optional[float] = None
    skeptic_score: Optional[float] = None
    fused_score: Optional[float] = None
    hospital_id: Optional[str] = None
    ack_latency_ms: Optional[int] = None
    notes: Optional[str] = None


class Precedent(BaseModel):
    text: str
    source: Literal["hindsight", "local-fallback"]
    relevance: Optional[float] = None
    ts: Optional[str] = None
    kind: Optional[str] = None
    zone: Optional[str] = None
    cause_tags: Optional[List[str]] = Field(default_factory=list)


class MemoryStatus(BaseModel):
    enabled: bool
    hindsight_reachable: bool
    bank_id: str
    events_in_ledger: int
    last_error: Optional[str] = None
    circuit_breaker_open: Optional[bool] = False


class MemoryStats(BaseModel):
    zone: Optional[str] = None
    cause_tags: List[str] = Field(default_factory=list)
    approved: int = 0
    overrides: int = 0
    verified: int = 0
    rejected: int = 0
    declines: int = 0
    timeouts: int = 0
    total: int = 0
