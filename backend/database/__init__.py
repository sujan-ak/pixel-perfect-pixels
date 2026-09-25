import logging
import os
from typing import Optional

from .interface import (
    AuditEntry,
    ChainVerifyResponse,
    DatabaseBackend,
    Incident,
    compute_short_hash,
    GENESIS_HASH,
)
from .sqlite_backend import SqliteBackend
from .supabase_backend import SupabaseBackend

logger = logging.getLogger("aurashield.database")


def get_database(backend_type: Optional[str] = None, db_path: Optional[str] = None) -> DatabaseBackend:
    if backend_type is None:
        backend_type = os.getenv("DB_BACKEND", "sqlite").lower()

    if backend_type == "supabase":
        supabase_url = os.getenv("SUPABASE_DB_URL")
        if not supabase_url:
            raise ValueError("DB_BACKEND is set to 'supabase' but SUPABASE_DB_URL is not configured in environment.")
        logger.info("Database factory: instantiated SupabaseBackend (PostgreSQL pool)")
        return SupabaseBackend(db_url=supabase_url)
    else:
        path = db_path or os.getenv("DATABASE_PATH", "aurashield.db")
        logger.info("Database factory: instantiated SqliteBackend (at %s)", path)
        return SqliteBackend(db_path=path)


# Backward compatibility alias
def AuditDatabase(db_path: Optional[str] = None) -> DatabaseBackend:
    return get_database(db_path=db_path)


__all__ = [
    "DatabaseBackend",
    "SqliteBackend",
    "SupabaseBackend",
    "AuditDatabase",
    "get_database",
    "AuditEntry",
    "Incident",
    "ChainVerifyResponse",
    "compute_short_hash",
    "GENESIS_HASH",
]
