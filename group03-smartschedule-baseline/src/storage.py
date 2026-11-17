"""SQLite persistence layer for SmartSchedule workspace state and completion history.

Stores user workspaces (commitments, tasks, pins, completed blocks, actual durations,
active algorithm) and task completion telemetry locally using Python's standard
library ``sqlite3`` module with zero external database dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _REPO_ROOT / "data" / "local_state.db"


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
