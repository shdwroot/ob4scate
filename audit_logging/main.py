"""Tamper-evident audit event storage."""

import hashlib
import hmac
import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
app = FastAPI(title="Audit Logging Service", version="0.5.0")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("AUDIT_LOG_DB", PROJECT_ROOT / ".data" / "audit_logs.db"))
GENESIS_HASH = "0" * 64


class AuditLog(BaseModel):
    event_type: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    event_data: dict[str, Any]


def _signing_key() -> bytes:
    key = os.getenv("AUDIT_LOG_SIGNING_KEY")
    if not key or len(key) < 32:
        raise RuntimeError("AUDIT_LOG_SIGNING_KEY must contain at least 32 characters")
    return key.encode()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def _initialize_database() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp)"
        )


def _canonical_event(timestamp: str, event_type: str, event_data: str, previous_hash: str) -> bytes:
    return json.dumps(
        {
            "timestamp": timestamp,
            "event_type": event_type,
            "event_data": json.loads(event_data),
            "previous_hash": previous_hash,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _event_hash(timestamp: str, event_type: str, event_data: str, previous_hash: str) -> str:
    return hmac.new(
        _signing_key(),
        _canonical_event(timestamp, event_type, event_data, previous_hash),
        hashlib.sha256,
    ).hexdigest()


def _store_event(event: AuditLog) -> tuple[int, str, str]:
    timestamp = datetime.now(UTC).isoformat()
    event_data = json.dumps(event.event_data, separators=(",", ":"), sort_keys=True)
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute(
            "SELECT event_hash FROM audit_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else GENESIS_HASH
        digest = _event_hash(timestamp, event.event_type, event_data, previous_hash)
        cursor = connection.execute(
            """
            INSERT INTO audit_logs
                (timestamp, event_type, event_data, previous_hash, event_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (timestamp, event.event_type, event_data, previous_hash, digest),
        )
        connection.commit()
        return int(cursor.lastrowid), timestamp, digest
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _read_logs(limit: int) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, timestamp, event_type, event_data, previous_hash, event_hash
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "event_type": row["event_type"],
            "event_data": json.loads(row["event_data"]),
            "previous_hash": row["previous_hash"],
            "event_hash": row["event_hash"],
        }
        for row in rows
    ]


def _verify_chain() -> tuple[bool, int | None]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, timestamp, event_type, event_data, previous_hash, event_hash
            FROM audit_logs
            ORDER BY id ASC
            """
        ).fetchall()
    previous_hash = GENESIS_HASH
    for row in rows:
        expected = _event_hash(
            row["timestamp"], row["event_type"], row["event_data"], previous_hash
        )
        if not hmac.compare_digest(row["previous_hash"], previous_hash) or not hmac.compare_digest(
            row["event_hash"], expected
        ):
            return False, int(row["id"])
        previous_hash = row["event_hash"]
    return True, None


_initialize_database()


@app.get("/health")
async def health_check() -> dict[str, str]:
    try:
        await run_in_threadpool(_signing_key)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit signing is not configured",
        ) from exc
    return {"status": "ok"}


@app.post("/log", status_code=status.HTTP_201_CREATED)
async def log_event(event: AuditLog) -> dict[str, Any]:
    try:
        event_id, timestamp, digest = await run_in_threadpool(_store_event, event)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit signing is not configured",
        ) from exc
    logger.info("Stored audit event id=%s type=%s", event_id, event.event_type)
    return {
        "status": "logged",
        "id": event_id,
        "timestamp": timestamp,
        "event_hash": digest,
    }


@app.get("/logs")
async def get_logs(
    limit: int = Query(default=100, ge=1, le=1_000),
) -> list[dict[str, Any]]:
    return await run_in_threadpool(_read_logs, limit)


@app.get("/verify")
async def verify_logs() -> dict[str, Any]:
    try:
        valid, invalid_event_id = await run_in_threadpool(_verify_chain)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit signing is not configured",
        ) from exc
    return {"valid": valid, "invalid_event_id": invalid_event_id}
