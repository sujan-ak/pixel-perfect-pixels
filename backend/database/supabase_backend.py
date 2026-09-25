import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
import asyncpg

from .interface import (
    AuditEntry,
    ChainVerifyResponse,
    DatabaseBackend,
    EmergencyNotification,
    Incident,
    compute_short_hash,
    GENESIS_HASH,
)

logger = logging.getLogger("aurashield.database.supabase")


class SupabaseBackend(DatabaseBackend):
    def __init__(self, db_url: str) -> None:
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
        self._write_lock = asyncio.Lock()

    async def init_db(self) -> None:
        logger.info("Connecting to Supabase PostgreSQL pool...")
        try:
            # statement_cache_size=0 is REQUIRED for Transaction pooler (PgBouncer)
            self.pool = await asyncpg.create_pool(
                self.db_url,
                statement_cache_size=0,
                min_size=1,
                max_size=10,
                timeout=15.0,
            )
            # Test connectivity
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version();")
                # Ensure demo_tamper_backup table exists if not already present
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS demo_tamper_backup (
                        row_id bigint references audit_log(id) on delete cascade,
                        original_action text not null,
                        original_hash text not null,
                        tampered_at timestamptz not null default now(),
                        primary key (row_id)
                    );
                    ALTER TABLE incidents ADD COLUMN IF NOT EXISTS degraded boolean default false;
                    """
                )
            logger.info("Successfully connected to Supabase PostgreSQL pool! (%s)", version[:50])
        except Exception as e:
            logger.error("FATAL: Failed to connect to Supabase PostgreSQL: %s", e)
            raise RuntimeError(f"Could not connect to Supabase pooler: {e}") from e

    async def append_audit_entry(
        self, actor: str, action: str, timestamp: Optional[str] = None
    ) -> AuditEntry:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        if not self.pool:
            raise RuntimeError("Database pool not initialized. Call init_db() first.")

        dt_val = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        async with self._write_lock:
            async with self.pool.acquire() as conn:
                last_row = await conn.fetchrow(
                    "SELECT current_hash FROM audit_log ORDER BY id DESC LIMIT 1;"
                )
                previous_hash = last_row["current_hash"] if last_row else GENESIS_HASH

                current_hash = compute_short_hash(previous_hash, actor, action, timestamp)

                row = await conn.fetchrow(
                    """
                    INSERT INTO audit_log (ts, actor, action, previous_hash, current_hash)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id, ts, actor, action, previous_hash, current_hash;
                    """,
                    dt_val,
                    actor,
                    action,
                    previous_hash,
                    current_hash,
                )

                entry = AuditEntry(
                    id=row["id"],
                    timestamp=timestamp,
                    actor=row["actor"],
                    action=row["action"],
                    previous_hash=row["previous_hash"],
                    current_hash=row["current_hash"],
                )
                logger.info(
                    "Supabase audit write [id=%d, actor=%s, action=%s, prev=%s, curr=%s]",
                    entry.id,
                    entry.actor,
                    entry.action,
                    entry.previous_hash,
                    entry.current_hash,
                )
                return entry

    async def get_all_audit_entries(self) -> List[AuditEntry]:
        if not self.pool:
            raise RuntimeError("Database pool not initialized. Call init_db() first.")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, ts, actor, action, previous_hash, current_hash FROM audit_log ORDER BY id ASC;"
            )
            entries = []
            for r in rows:
                ts_dt = r["ts"]
                if isinstance(ts_dt, datetime):
                    ts_str = ts_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    ts_str = str(ts_dt)

                entries.append(
                    AuditEntry(
                        id=r["id"],
                        timestamp=ts_str,
                        actor=r["actor"],
                        action=r["action"],
                        previous_hash=r["previous_hash"],
                        current_hash=r["current_hash"],
                    )
                )
            return entries

    async def verify_chain(self) -> ChainVerifyResponse:
        entries = await self.get_all_audit_entries()
        if not entries:
            return ChainVerifyResponse(valid=True, checked_blocks=0, broken_at=None)

        for i, entry in enumerate(entries):
            expected_prev = GENESIS_HASH if i == 0 else entries[i - 1].current_hash
            if entry.previous_hash != expected_prev:
                logger.warning(
                    "Supabase hash chain broken at index %d: previous_hash mismatch (%s != %s)",
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
                    "Supabase hash chain broken at index %d: current_hash corrupted (%s != %s)",
                    i,
                    entry.current_hash,
                    recomputed,
                )
                return ChainVerifyResponse(valid=False, checked_blocks=i, broken_at=entry.id)

        return ChainVerifyResponse(valid=True, checked_blocks=len(entries), broken_at=None)

    async def tamper_demo_row(self) -> Dict[str, Any]:
        """
        Demo-only helper: picks a middle CLOSED/APPROVE audit row,
        backs up to demo_tamper_backup table, mutates action without changing current_hash.
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized.")

        async with self._write_lock:
            async with self.pool.acquire() as conn:
                # If there's an existing tamper in shadow table, restore it first
                backups = await conn.fetch("SELECT row_id, original_action, original_hash FROM demo_tamper_backup;")
                for b in backups:
                    await conn.execute(
                        "UPDATE audit_log SET action = $1, current_hash = $2 WHERE id = $3;",
                        b["original_action"],
                        b["original_hash"],
                        b["row_id"],
                    )
                await conn.execute("DELETE FROM demo_tamper_backup;")

                rows = await conn.fetch("SELECT id, actor, action, previous_hash, current_hash FROM audit_log ORDER BY id ASC;")
                if len(rows) < 3:
                    raise ValueError("Not enough audit rows to perform tamper demo")

                middle_rows = rows[1:-1]
                closed_candidates = [
                    r
                    for r in middle_rows
                    if "CLOSED" in r["action"] or "APPROVE_DISPATCH" in r["action"]
                ]
                candidates = closed_candidates if closed_candidates else middle_rows

                selected_row = candidates[len(candidates) // 2]
                row_id = selected_row["id"]
                original_action = selected_row["action"]
                original_hash = selected_row["current_hash"]

                # Save backup in demo_tamper_backup table
                await conn.execute(
                    """
                    INSERT INTO demo_tamper_backup (row_id, original_action, original_hash, tampered_at)
                    VALUES ($1, $2, $3, now())
                    ON CONFLICT (row_id) DO UPDATE SET
                        original_action = EXCLUDED.original_action,
                        original_hash = EXCLUDED.original_hash,
                        tampered_at = now();
                    """,
                    row_id,
                    original_action,
                    original_hash,
                )

                tampered_action = f"{original_action} [UNAUTHORIZED MUTATION]"
                await conn.execute(
                    "UPDATE audit_log SET action = $1 WHERE id = $2;",
                    tampered_action,
                    row_id,
                )

                zone = "Zone 04"
                match = re.search(r"inc_\d+", original_action)
                if match:
                    inc_id = match.group(0)
                    inc_row = await conn.fetchrow(
                        "SELECT zone FROM incidents WHERE id = $1;", inc_id
                    )
                    if inc_row and inc_row["zone"]:
                        zone = inc_row["zone"]

                logger.info(
                    "DEMO TAMPER (Supabase): Altered audit row #%d action: '%s' -> '%s'",
                    row_id,
                    original_action,
                    tampered_action,
                )
                return {"tampered_row_id": row_id, "zone": zone}

    async def restore_demo_row(self) -> Dict[str, Any]:
        """
        Demo-only helper: restores previously tampered row using demo_tamper_backup table.
        """
        if not self.pool:
            raise RuntimeError("Database pool not initialized.")

        async with self._write_lock:
            async with self.pool.acquire() as conn:
                backups = await conn.fetch("SELECT row_id, original_action, original_hash FROM demo_tamper_backup;")
                restored_id = 0
                if backups:
                    for b in backups:
                        await conn.execute(
                            "UPDATE audit_log SET action = $1, current_hash = $2 WHERE id = $3;",
                            b["original_action"],
                            b["original_hash"],
                            b["row_id"],
                        )
                        restored_id = b["row_id"]
                    await conn.execute("DELETE FROM demo_tamper_backup;")
                else:
                    rows = await conn.fetch(
                        "SELECT id, action FROM audit_log WHERE action LIKE '%[UNAUTHORIZED MUTATION]%';"
                    )
                    for r in rows:
                        cleaned = r["action"].replace(" [UNAUTHORIZED MUTATION]", "")
                        await conn.execute(
                            "UPDATE audit_log SET action = $1 WHERE id = $2;",
                            cleaned,
                            r["id"],
                        )
                        restored_id = r["id"]

                logger.info("DEMO RESTORE (Supabase): Restored audit row #%d", restored_id)
                return {"restored_row_id": restored_id}

    async def save_incident(self, incident: Incident) -> None:
        if not self.pool:
            raise RuntimeError("Database pool not initialized.")

        dt_val = datetime.fromisoformat(incident.timestamp.replace("Z", "+00:00"))

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO incidents (
                    id, state, zone, scenario, corroborator_score, skeptic_score,
                    fused_score, reasoning, media_file, created_at, degraded
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    state = EXCLUDED.state,
                    zone = EXCLUDED.zone,
                    scenario = EXCLUDED.scenario,
                    corroborator_score = EXCLUDED.corroborator_score,
                    skeptic_score = EXCLUDED.skeptic_score,
                    fused_score = EXCLUDED.fused_score,
                    reasoning = EXCLUDED.reasoning,
                    media_file = EXCLUDED.media_file,
                    created_at = EXCLUDED.created_at,
                    degraded = EXCLUDED.degraded;
                """,
                incident.id,
                incident.state,
                incident.zone,
                incident.scenario,
                float(incident.corroborator_score),
                float(incident.skeptic_score),
                float(incident.fused_score),
                incident.reasoning,
                incident.media_file,
                dt_val,
                bool(incident.degraded),
            )
            logger.info("Saved incident %s [state=%s] to Supabase", incident.id, incident.state)

    async def get_latest_incident(self) -> Optional[Incident]:
        if not self.pool:
            raise RuntimeError("Database pool not initialized.")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM incidents ORDER BY created_at DESC LIMIT 1;"
            )
            if not row:
                return None
            ts_dt = row["created_at"]
            ts_str = ts_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(ts_dt, datetime) else str(ts_dt)
            return Incident(
                id=row["id"],
                state=row["state"],
                zone=row["zone"],
                scenario=row["scenario"],
                corroborator_score=float(row["corroborator_score"]),
                skeptic_score=float(row["skeptic_score"]),
                fused_score=float(row["fused_score"]),
                reasoning=row["reasoning"],
                media_file=row["media_file"],
                timestamp=ts_str,
                degraded=bool(row["degraded"]) if "degraded" in row and row["degraded"] is not None else False,
            )

    async def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
        if not self.pool:
            raise RuntimeError("Database pool not initialized.")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM incidents WHERE id = $1;", incident_id)
            if not row:
                return None
            ts_dt = row["created_at"]
            ts_str = ts_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(ts_dt, datetime) else str(ts_dt)
            return Incident(
                id=row["id"],
                state=row["state"],
                zone=row["zone"],
                scenario=row["scenario"],
                corroborator_score=float(row["corroborator_score"]),
                skeptic_score=float(row["skeptic_score"]),
                fused_score=float(row["fused_score"]),
                reasoning=row["reasoning"],
                media_file=row["media_file"],
                timestamp=ts_str,
                degraded=bool(row["degraded"]) if "degraded" in row and row["degraded"] is not None else False,
            )

    async def get_incident_history(self) -> List[Incident]:
        if not self.pool:
            raise RuntimeError("Database pool not initialized.")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM incidents
                WHERE state IN ('CLOSED', 'REJECTED')
                ORDER BY created_at DESC;
                """
            )
            incidents = []
            for row in rows:
                ts_dt = row["created_at"]
                ts_str = ts_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(ts_dt, datetime) else str(ts_dt)
                incidents.append(
                    Incident(
                        id=row["id"],
                        state=row["state"],
                        zone=row["zone"],
                        scenario=row["scenario"],
                        corroborator_score=float(row["corroborator_score"]),
                        skeptic_score=float(row["skeptic_score"]),
                        fused_score=float(row["fused_score"]),
                        reasoning=row["reasoning"],
                        media_file=row["media_file"],
                        timestamp=ts_str,
                        degraded=bool(row["degraded"]) if "degraded" in row and row["degraded"] is not None else False,
                    )
                )
            return incidents

    async def record_notification(self, notif: EmergencyNotification) -> EmergencyNotification:
        if not self.pool:
            notif.id = 1
            return notif
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO emergency_notifications (
                        incident_id, notification_type, recipient, channel, trigger_event,
                        timestamp, status, message_body, provider_id, error_message
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING id;
                    """,
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
                )
                if row:
                    notif.id = row["id"]
        except Exception as e:
            logger.warning("Could not persist notification in Supabase: %s", e)
            notif.id = 1
        return notif

    async def get_notifications_for_incident(
        self, incident_id: str, notification_type: Optional[str] = None
    ) -> List[EmergencyNotification]:
        if not self.pool:
            return []
        try:
            async with self.pool.acquire() as conn:
                if notification_type:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM emergency_notifications
                        WHERE incident_id = $1 AND notification_type = $2
                        ORDER BY id ASC;
                        """,
                        incident_id,
                        notification_type,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM emergency_notifications
                        WHERE incident_id = $1
                        ORDER BY id ASC;
                        """,
                        incident_id,
                    )
                return [
                    EmergencyNotification(
                        id=row["id"],
                        incident_id=row["incident_id"],
                        notification_type=row["notification_type"],
                        recipient=row["recipient"],
                        channel=row["channel"],
                        trigger_event=row["trigger_event"],
                        timestamp=str(row["timestamp"]),
                        status=row["status"],
                        message_body=row["message_body"],
                        provider_id=row["provider_id"],
                        error_message=row["error_message"],
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.warning("Could not fetch notifications from Supabase: %s", e)
            return []
