# Re-export from modular database package for backward compatibility
from .interface import (
    AuditEntry,
    Incident,
    ChainVerifyResponse,
    DatabaseBackend,
    compute_short_hash,
    GENESIS_HASH,
)
from .sqlite_backend import SqliteBackend
from .supabase_backend import SupabaseBackend
from . import get_database, AuditDatabase

__all__ = [
    "AuditEntry",
    "Incident",
    "ChainVerifyResponse",
    "DatabaseBackend",
    "SqliteBackend",
    "SupabaseBackend",
    "AuditDatabase",
    "get_database",
    "compute_short_hash",
    "GENESIS_HASH",
]
