import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
import aiosqlite

from .interface import (
    AuditEntry,
    ChainVerifyResponse,
    DatabaseBackend,
    EmergencyNotification,
    Incident,
    compute_short_hash,
    GENESIS_HASH,
)

logger = logging.getLogger("aurashield.database.sqlite")
demo_tamper_backup: Dict[int, dict] = {}


class SqliteBackend(DatabaseBackend):
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
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS emergency_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    trigger_event TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message_body TEXT NOT NULL,
                    provider_id TEXT,
                    error_message TEXT
                );
                """
            )
            await db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_emergency_notifications_incident
                ON emergency_notifications(incident_id, notification_type);
                """
            )
            await db.commit()
            try:
                await db.execute("ALTER TABLE incidents ADD COLUMN degraded INTEGER DEFAULT 0;")
                await db.commit()
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE incidents ADD COLUMN confidence REAL DEFAULT 0.90;")
                await db.commit()
            except Exception:
                pass
            for col in [
                "field_status TEXT DEFAULT NULL",
                "responder_id TEXT DEFAULT NULL",
                "ack_channel TEXT DEFAULT NULL",
                "ack_time TEXT DEFAULT NULL",
            ]:
                try:
                    await db.execute(f"ALTER TABLE incidents ADD COLUMN {col};")
                    await db.commit()
                except Exception:
                    pass
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

    async def get_all_audit_entries(self) -> List[AuditEntry]:
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
            expected_prev = GENESIS_HASH if i == 0 else entries[i - 1].current_hash
            if entry.previous_hash != expected_prev:
                logger.warning(
                    "Hash chain broken at index %d: previous_hash mismatch (%s != %s)",
                    i,
                    entry.previous_hash,
                    expected_prev,
                )
                return ChainVerifyResponse(valid=False, checked_blocks=i, broken_at=entry.id)

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
                return ChainVerifyResponse(valid=False, checked_blocks=i, broken_at=entry.id)

        return ChainVerifyResponse(valid=True, checked_blocks=len(entries), broken_at=None)

    async def tamper_demo_row(self) -> Dict[str, Any]:
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                if demo_tamper_backup:
                    for r_id, orig in list(demo_tamper_backup.items()):
                        await db.execute(
                            "UPDATE audit_log SET action = ?, actor = ? WHERE id = ?",
                            (orig["action"], orig["actor"], r_id),
                        )
                    await db.commit()
                    demo_tamper_backup.clear()

                cursor = await db.execute("SELECT * FROM audit_log ORDER BY id ASC")
                rows = await cursor.fetchall()
                if len(rows) < 3:
                    raise ValueError("Not enough audit rows to perform tamper demo")

                middle_rows = [r for r in rows[1:-1]]
                closed_candidates = [
                    r
                    for r in middle_rows
                    if "CLOSED" in r["action"] or "APPROVE_DISPATCH" in r["action"]
                ]
                candidates = closed_candidates if closed_candidates else middle_rows

                selected_row = candidates[len(candidates) // 2]
                row_id = selected_row["id"]
                original_action = selected_row["action"]
                original_actor = selected_row["actor"]

                demo_tamper_backup[row_id] = {
                    "action": original_action,
                    "actor": original_actor,
                    "current_hash": selected_row["current_hash"],
                }

                tampered_action = f"{original_action} [UNAUTHORIZED MUTATION]"
                await db.execute(
                    "UPDATE audit_log SET action = ? WHERE id = ?",
                    (tampered_action, row_id),
                )
                await db.commit()

                zone = "Zone 04"
                match = re.search(r"inc_\d+", original_action)
                if match:
                    inc_id = match.group(0)
                    cur_inc = await db.execute(
                        "SELECT zone FROM incidents WHERE id = ?", (inc_id,)
                    )
                    inc_row = await cur_inc.fetchone()
                    if inc_row and inc_row["zone"]:
                        zone = inc_row["zone"]

                logger.info(
                    "DEMO TAMPER: Altered audit row #%d action: '%s' -> '%s'",
                    row_id,
                    original_action,
                    tampered_action,
                )
                return {"tampered_row_id": row_id, "zone": zone}

    async def restore_demo_row(self) -> Dict[str, Any]:
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                restored_id = 0
                if demo_tamper_backup:
                    for r_id, orig in list(demo_tamper_backup.items()):
                        await db.execute(
                            "UPDATE audit_log SET action = ?, actor = ? WHERE id = ?",
                            (orig["action"], orig["actor"], r_id),
                        )
                        restored_id = r_id
                    await db.commit()
                    demo_tamper_backup.clear()
                else:
                    db.row_factory = aiosqlite.Row
                    cursor = await db.execute(
                        "SELECT id, action FROM audit_log WHERE action LIKE '%[UNAUTHORIZED MUTATION]%'"
                    )
                    rows = await cursor.fetchall()
                    for r in rows:
                        cleaned = r["action"].replace(" [UNAUTHORIZED MUTATION]", "")
                        await db.execute(
                            "UPDATE audit_log SET action = ? WHERE id = ?",
                            (cleaned, r["id"]),
                        )
                        restored_id = r["id"]
                    await db.commit()

                logger.info("DEMO RESTORE: Restored audit row #%d", restored_id)
                return {"restored_row_id": restored_id}

    async def save_incident(self, incident: Incident) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO incidents (
                    id, state, zone, scenario, corroborator_score, skeptic_score,
                    fused_score, confidence, reasoning, media_file, timestamp, degraded,
                    field_status, responder_id, ack_channel, ack_time, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    state = excluded.state,
                    zone = excluded.zone,
                    scenario = excluded.scenario,
                    corroborator_score = excluded.corroborator_score,
                    skeptic_score = excluded.skeptic_score,
                    fused_score = excluded.fused_score,
                    confidence = excluded.confidence,
                    reasoning = excluded.reasoning,
                    media_file = excluded.media_file,
                    timestamp = excluded.timestamp,
                    degraded = excluded.degraded,
                    field_status = excluded.field_status,
                    responder_id = excluded.responder_id,
                    ack_channel = excluded.ack_channel,
                    ack_time = excluded.ack_time,
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
                    incident.confidence if incident.confidence is not None else 0.90,
                    incident.reasoning,
                    incident.media_file,
                    incident.timestamp,
                    1 if incident.degraded else 0,
                    incident.field_status,
                    incident.responder_id,
                    incident.ack_channel,
                    incident.ack_time,
                ),
            )
            await db.commit()
            logger.info("Saved incident %s [state=%s, field_status=%s]", incident.id, incident.state, incident.field_status)

    async def get_latest_incident(self) -> Optional[Incident]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM incidents ORDER BY updated_at DESC, rowid DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            if not row:
                return None
            keys = row.keys()
            return Incident(
                id=row["id"],
                state=row["state"],
                zone=row["zone"],
                scenario=row["scenario"],
                corroborator_score=row["corroborator_score"],
                skeptic_score=row["skeptic_score"],
                fused_score=row["fused_score"],
                confidence=float(row["confidence"]) if "confidence" in keys and row["confidence"] is not None else 0.90,
                reasoning=row["reasoning"],
                media_file=row["media_file"],
                timestamp=row["timestamp"],
                degraded=bool(row["degraded"]) if "degraded" in keys and row["degraded"] is not None else False,
                field_status=row["field_status"] if "field_status" in keys else None,
                responder_id=row["responder_id"] if "responder_id" in keys else None,
                ack_channel=row["ack_channel"] if "ack_channel" in keys else None,
                ack_time=row["ack_time"] if "ack_time" in keys else None,
            )

    async def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            keys = row.keys()
            return Incident(
                id=row["id"],
                state=row["state"],
                zone=row["zone"],
                scenario=row["scenario"],
                corroborator_score=row["corroborator_score"],
                skeptic_score=row["skeptic_score"],
                fused_score=row["fused_score"],
                confidence=float(row["confidence"]) if "confidence" in keys and row["confidence"] is not None else 0.90,
                reasoning=row["reasoning"],
                media_file=row["media_file"],
                timestamp=row["timestamp"],
                degraded=bool(row["degraded"]) if "degraded" in keys and row["degraded"] is not None else False,
                field_status=row["field_status"] if "field_status" in keys else None,
                responder_id=row["responder_id"] if "responder_id" in keys else None,
                ack_channel=row["ack_channel"] if "ack_channel" in keys else None,
                ack_time=row["ack_time"] if "ack_time" in keys else None,
            )

    async def get_incident_history(self) -> List[Incident]:
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
            history = []
            for row in rows:
                keys = row.keys()
                history.append(
                    Incident(
                        id=row["id"],
                        state=row["state"],
                        zone=row["zone"],
                        scenario=row["scenario"],
                        corroborator_score=row["corroborator_score"],
                        skeptic_score=row["skeptic_score"],
                        fused_score=row["fused_score"],
                        confidence=float(row["confidence"]) if "confidence" in keys and row["confidence"] is not None else 0.90,
                        reasoning=row["reasoning"],
                        media_file=row["media_file"],
                        timestamp=row["timestamp"],
                        degraded=bool(row["degraded"]) if "degraded" in keys and row["degraded"] is not None else False,
                        field_status=row["field_status"] if "field_status" in keys else None,
                        responder_id=row["responder_id"] if "responder_id" in keys else None,
                        ack_channel=row["ack_channel"] if "ack_channel" in keys else None,
                        ack_time=row["ack_time"] if "ack_time" in keys else None,
                    )
                )
            return history

    async def record_notification(self, notif: EmergencyNotification) -> EmergencyNotification:
        async with self._write_lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    """
                    INSERT INTO emergency_notifications (
                        incident_id, notification_type, recipient, channel, trigger_event,
                        timestamp, status, message_body, provider_id, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        notif.incident_id,
                        notif.notification_type,
                        notif.recipient,
                        notif.channel,
                        notif.trigger_event,
                        notif.timestamp,
                        notif.status,
                        notif.message_body,
                        notif.provider_id,
                        notif.error_message,
                    ),
                )
                await db.commit()
                notif.id = cursor.lastrowid
                return notif

    async def get_notifications_for_incident(
        self, incident_id: str, notification_type: Optional[str] = None, channel: Optional[str] = None
    ) -> List[EmergencyNotification]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            conditions = ["incident_id = ?"]
            params = [incident_id]
            if notification_type:
                conditions.append("notification_type = ?")
                params.append(notification_type)
            if channel:
                conditions.append("channel = ?")
                params.append(channel.upper())
            where_sql = " AND ".join(conditions)
            cursor = await db.execute(
                f"""
                SELECT * FROM emergency_notifications
                WHERE {where_sql}
                ORDER BY id ASC
                """,
                tuple(params),
            )
            rows = await cursor.fetchall()
            return [
                EmergencyNotification(
                    id=row["id"],
                    incident_id=row["incident_id"],
                    notification_type=row["notification_type"],
                    recipient=row["recipient"],
                    channel=row["channel"],
                    trigger_event=row["trigger_event"],
                    timestamp=row["timestamp"],
                    status=row["status"],
                    message_body=row["message_body"],
                    provider_id=row["provider_id"],
                    error_message=row["error_message"],
                )
                for row in rows
            ]


AuditDatabase = SqliteBackend
