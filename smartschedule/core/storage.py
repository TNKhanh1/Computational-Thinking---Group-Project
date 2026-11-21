"""SQLite persistence layer for SmartSchedule workspace state and completion history.

Stores user workspaces (commitments, tasks, pins, completed blocks, actual durations,
active algorithm) and task completion telemetry locally using Python's standard
library ``sqlite3`` module with zero external database dependencies.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


from smartschedule.core.config import DEFAULT_DB_PATH, REPO_ROOT as _REPO_ROOT

_DEFAULT_DB_PATH = DEFAULT_DB_PATH


def get_db_path() -> Path:
    """Resolve SQLite database path from ``SMARTSCHEDULE_DB_PATH`` or default location."""
    override = os.environ.get("SMARTSCHEDULE_DB_PATH", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_DB_PATH


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    db_path = get_db_path()
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspace_state (
            workspace_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS completion_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            task_id TEXT NOT NULL,
            category TEXT NOT NULL,
            estimated_duration_min INTEGER NOT NULL,
            actual_duration_min INTEGER NOT NULL,
            completed_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_completion_logs_workspace
            ON completion_logs (workspace_id, id DESC);

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'local',
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
        """
    )
    conn.commit()


def load_workspace_state(workspace_id: str = "default") -> Optional[Dict[str, Any]]:
    """Load persisted workspace state dictionary, or None if no record exists."""
    ws_id = (workspace_id or "default").strip() or "default"
    with _connect() as conn:
        row = conn.execute(
            "SELECT workspace_id, payload_json, updated_at FROM workspace_state WHERE workspace_id = ?",
            (ws_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload_json"])
    except json.JSONDecodeError:
        payload = {}
    return {
        "workspace_id": row["workspace_id"],
        "state": payload if isinstance(payload, dict) else {},
        "updated_at": row["updated_at"],
    }


def save_workspace_state(state_payload: Dict[str, Any], workspace_id: str = "default") -> str:
    """Persist or overwrite workspace state dictionary and return updated ISO timestamp."""
    ws_id = (workspace_id or "default").strip() or "default"
    updated_at = _utc_now_iso()
    payload_json = json.dumps(state_payload, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO workspace_state (workspace_id, payload_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (ws_id, payload_json, updated_at),
        )
        conn.commit()
    return updated_at


def delete_workspace_state(workspace_id: str = "default") -> bool:
    """Delete saved workspace state for ``workspace_id``. Returns True if a row was removed."""
    ws_id = (workspace_id or "default").strip() or "default"
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM workspace_state WHERE workspace_id = ?",
            (ws_id,),
        )
        conn.commit()
    return cur.rowcount > 0


def append_completion_log(
    task_id: str,
    category: str,
    estimated_duration_min: int,
    actual_duration_min: int,
    workspace_id: str = "default",
) -> Dict[str, Any]:
    """Append a completed task duration record and return the inserted row dictionary."""
    ws_id = (workspace_id or "default").strip() or "default"
    completed_at = _utc_now_iso()
    cat = (category or "OTHER").strip().upper()
    est_min = max(1, int(estimated_duration_min))
    act_min = max(1, int(actual_duration_min))
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO completion_logs (
                workspace_id, task_id, category, estimated_duration_min, actual_duration_min, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ws_id, str(task_id), cat, est_min, act_min, completed_at),
        )
        conn.commit()
        row_id = cur.lastrowid
    return {
        "id": row_id,
        "workspace_id": ws_id,
        "task_id": str(task_id),
        "category": cat,
        "estimated_duration_min": est_min,
        "actual_duration_min": act_min,
        "completed_at": completed_at,
    }


def list_completion_logs(workspace_id: str = "default", limit: int = 200) -> List[Dict[str, Any]]:
    """Return recent completion log entries ordered newest-first."""
    ws_id = (workspace_id or "default").strip() or "default"
    capped_limit = max(1, min(1000, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, workspace_id, task_id, category, estimated_duration_min, actual_duration_min, completed_at
            FROM completion_logs
            WHERE workspace_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (ws_id, capped_limit),
        ).fetchall()
    return [dict(r) for r in rows]


def _hash_password(password: str, salt_hex: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        120_000,
    )
    return dk.hex()


def create_user(
    email: str,
    password: str,
    display_name: str = "",
    provider: str = "local",
) -> Dict[str, Any]:
    """Create a new local/OAuth user account in SQLite. Raises ValueError if email already exists."""
    norm_email = (email or "").strip().lower()
    if not norm_email or "@" not in norm_email:
        raise ValueError("Invalid email address.")
    if provider == "local" and len(password or "") < 6:
        raise ValueError("Password must be at least 6 characters.")

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    name = (display_name or norm_email.split("@")[0]).strip() or "Student"
    salt_hex = secrets.token_hex(16)
    pw_hash = _hash_password(password or secrets.token_urlsafe(24), salt_hex)
    created_at = _utc_now_iso()

    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, email, display_name, provider, password_hash, password_salt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, norm_email, name, provider, pw_hash, salt_hex, created_at),
            )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("Email is already registered.") from exc

    return {
        "user_id": user_id,
        "email": norm_email,
        "display_name": name,
        "provider": provider,
        "created_at": created_at,
    }


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Lookup user record (excluding password secrets) by normalized email."""
    norm_email = (email or "").strip().lower()
    if not norm_email:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id, email, display_name, provider, created_at FROM users WHERE email = ?",
            (norm_email,),
        ).fetchone()
    return dict(row) if row is not None else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Lookup user record (excluding password secrets) by user_id."""
    uid = (user_id or "").strip()
    if not uid:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id, email, display_name, provider, created_at FROM users WHERE user_id = ?",
            (uid,),
        ).fetchone()
    return dict(row) if row is not None else None


def verify_user_credentials(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify email + password against SQLite PBKDF2-HMAC-SHA256 hash."""
    norm_email = (email or "").strip().lower()
    if not norm_email or not password:
        return None
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, email, display_name, provider, password_hash, password_salt, created_at
            FROM users WHERE email = ?
            """,
            (norm_email,),
        ).fetchone()
    if row is None:
        return None
    expected = _hash_password(password, row["password_salt"])
    if not hmac.compare_digest(expected, row["password_hash"]):
        return None
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "provider": row["provider"],
        "created_at": row["created_at"],
    }
