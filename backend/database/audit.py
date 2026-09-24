import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import aiosqlite
from pydantic import BaseModel, Field

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
    reasoning: str
    media_file: str
    timestamp: str


class ChainVerifyResponse(BaseModel):
    valid: bool
    checked_blocks: int
    broken_at: Optional[int] = None


def compute_short_hash(previous_hash: str, actor: str, action: str, timestamp: str) -> str:
    payload = f"{previous_hash}|{actor}|{action}|{timestamp}".encode("utf-8")
    full_hex = hashlib.sha256(payload).hexdigest()
    return f"{full_hex[:4]}...{full_hex[-4:]}"


class AuditDatabase:
    def __init__(self, db_path: str = "aurashield.db") -> None:
        self.db_path = db_path
        self._write_lock = asyncio.Lock()

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    zone TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    corroborator_score REAL NOT NULL,
                    skeptic_score REAL NOT NULL,
                    fused_score REAL NOT NULL,
                    reasoning TEXT NOT NULL,
                    media_file TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await db.commit()
            logger.info("Initialized SQLite database tables at %s", self.db_path)

    async def append_audit_entry(
        self, actor: str, action: str, timestamp: Optional[str] = None
    ) -> AuditEntry:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT current_hash FROM audit_log ORDER BY id DESC LIMIT 1"
                )
                last_row = await cursor.fetchone()
                previous_hash = last_row["current_hash"] if last_row else GENESIS_HASH

                current_hash = compute_short_hash(previous_hash, actor, action, timestamp)

                cursor = await db.execute(
                    """
                    INSERT INTO audit_log (timestamp, actor, action, previous_hash, current_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (timestamp, actor, action, previous_hash, current_hash),
                )
                entry_id = cursor.lastrowid
                await db.commit()

                entry = AuditEntry(
                    id=entry_id,
                    timestamp=timestamp,
                    actor=actor,
                    action=action,
                    previous_hash=previous_hash,
                    current_hash=current_hash,
                )
                logger.info(
                    "Audit write [id=%d, actor=%s, action=%s, prev=%s, curr=%s]",
                    entry.id,
                    entry.actor,
                    entry.action,
                    entry.previous_hash,
                    entry.current_hash,
                )
                return entry

    async def get_all_audit_entries(self) -> list[AuditEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM audit_log ORDER BY id ASC")
            rows = await cursor.fetchall()
            return [
                AuditEntry(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    actor=row["actor"],
                    action=row["action"],
                    previous_hash=row["previous_hash"],
                    current_hash=row["current_hash"],
                )
                for row in rows
            ]

    async def verify_chain(self) -> ChainVerifyResponse:
        entries = await self.get_all_audit_entries()
        if not entries:
            return ChainVerifyResponse(valid=True, checked_blocks=0, broken_at=None)

        for i, entry in enumerate(entries):
            # Check previous_hash link
            expected_prev = GENESIS_HASH if i == 0 else entries[i - 1].current_hash
            if entry.previous_hash != expected_prev:
                logger.warning(
                    "Hash chain broken at index %d: previous_hash mismatch (%s != %s)",
                    i,
                    entry.previous_hash,
                    expected_prev,
                )
                return ChainVerifyResponse(valid=False, checked_blocks=i, broken_at=i)

            # Check current_hash computation
            recomputed = compute_short_hash(
                entry.previous_hash, entry.actor, entry.action, entry.timestamp
            )
            if entry.current_hash != recomputed:
                logger.warning(
                    "Hash chain broken at index %d: current_hash corrupted (%s != %s)",
                    i,
                    entry.current_hash,
                    recomputed,
                )
                return ChainVerifyResponse(valid=False, checked_blocks=i, broken_at=i)

        return ChainVerifyResponse(valid=True, checked_blocks=len(entries), broken_at=None)

    async def save_incident(self, incident: Incident) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO incidents (
                    id, state, zone, scenario, corroborator_score, skeptic_score,
                    fused_score, reasoning, media_file, timestamp, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    state = excluded.state,
                    zone = excluded.zone,
                    scenario = excluded.scenario,
                    corroborator_score = excluded.corroborator_score,
                    skeptic_score = excluded.skeptic_score,
                    fused_score = excluded.fused_score,
                    reasoning = excluded.reasoning,
                    media_file = excluded.media_file,
                    timestamp = excluded.timestamp,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    incident.id,
                    incident.state,
                    incident.zone,
                    incident.scenario,
                    incident.corroborator_score,
                    incident.skeptic_score,
                    incident.fused_score,
                    incident.reasoning,
                    incident.media_file,
                    incident.timestamp,
                ),
            )
            await db.commit()
            logger.info("Saved incident %s [state=%s]", incident.id, incident.state)

    async def get_latest_incident(self) -> Optional[Incident]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM incidents ORDER BY updated_at DESC, rowid DESC LIMIT 1")
            row = await cursor.fetchone()
            if not row:
                return None
            return Incident(
                id=row["id"],
                state=row["state"],
                zone=row["zone"],
                scenario=row["scenario"],
                corroborator_score=row["corroborator_score"],
                skeptic_score=row["skeptic_score"],
                fused_score=row["fused_score"],
                reasoning=row["reasoning"],
                media_file=row["media_file"],
                timestamp=row["timestamp"],
            )

    async def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return Incident(
                id=row["id"],
                state=row["state"],
                zone=row["zone"],
                scenario=row["scenario"],
                corroborator_score=row["corroborator_score"],
                skeptic_score=row["skeptic_score"],
                fused_score=row["fused_score"],
                reasoning=row["reasoning"],
                media_file=row["media_file"],
                timestamp=row["timestamp"],
            )

    async def get_incident_history(self) -> list[Incident]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM incidents
                WHERE state IN ('CLOSED', 'REJECTED')
                ORDER BY updated_at DESC, rowid DESC
                """
            )
            rows = await cursor.fetchall()
            return [
                Incident(
                    id=row["id"],
                    state=row["state"],
                    zone=row["zone"],
                    scenario=row["scenario"],
                    corroborator_score=row["corroborator_score"],
                    skeptic_score=row["skeptic_score"],
                    fused_score=row["fused_score"],
                    reasoning=row["reasoning"],
                    media_file=row["media_file"],
                    timestamp=row["timestamp"],
                )
                for row in rows
            ]
