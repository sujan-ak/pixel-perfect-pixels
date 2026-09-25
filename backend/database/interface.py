from abc import ABC, abstractmethod
import hashlib
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("aurashield.database")

GENESIS_HASH = "0000...0000"


class AuditEntry(BaseModel):
    id: int
    timestamp: str
    actor: str
    action: str
    previous_hash: str
    current_hash: str


class Incident(BaseModel):
    id: str
    state: str
    zone: str
    scenario: str
    corroborator_score: float
    skeptic_score: float
    fused_score: float
    confidence: Optional[float] = 0.90
    reasoning: str
    media_file: str
    timestamp: str
    degraded: Optional[bool] = False


class ChainVerifyResponse(BaseModel):
    valid: bool
    checked_blocks: int
    broken_at: Optional[int] = None


def compute_short_hash(previous_hash: str, actor: str, action: str, timestamp: str) -> str:
    payload = f"{previous_hash}|{actor}|{action}|{timestamp}".encode("utf-8")
    full_hex = hashlib.sha256(payload).hexdigest()
    return f"{full_hex[:4]}...{full_hex[-4:]}"


class DatabaseBackend(ABC):
    @abstractmethod
    async def init_db(self) -> None:
        """Initialize connection, tables, or pools."""
        pass

    @abstractmethod
    async def save_incident(self, incident: Incident) -> None:
        """Upsert incident record."""
        pass

    @abstractmethod
    async def get_latest_incident(self) -> Optional[Incident]:
        """Fetch the most recently updated incident."""
        pass

    @abstractmethod
    async def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
        """Fetch incident by its ID."""
        pass

    @abstractmethod
    async def get_incident_history(self) -> List[Incident]:
        """Fetch all resolved or rejected incidents."""
        pass

    @abstractmethod
    async def append_audit_entry(self, actor: str, action: str, timestamp: str) -> AuditEntry:
        """Append an immutable audit entry to the ledger."""
        pass

    @abstractmethod
    async def get_all_audit_entries(self) -> List[AuditEntry]:
        """Return all audit ledger entries in chronological order."""
        pass

    @abstractmethod
    async def verify_chain(self) -> ChainVerifyResponse:
        """Verify cryptographic integrity of the hash chain."""
        pass

    @abstractmethod
    async def tamper_demo_row(self) -> Dict[str, Any]:
        """[DEMO ONLY] Simulate adversary tampering with an audit ledger row."""
        pass

    @abstractmethod
    async def restore_demo_row(self) -> Dict[str, Any]:
        """[DEMO ONLY] Revert tampered audit ledger row back to authentic state."""
        pass
