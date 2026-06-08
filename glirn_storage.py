import json
import os
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from threading import RLock
from datetime import datetime, timezone


DEFAULT_DB_PATH = Path("data") / "glirn_live.db"
_lock = RLock()


def database_path():
    return Path(os.getenv("GLIRN_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()


def persistence_status():
    configured_path = os.getenv("GLIRN_DB_PATH")
    status = {
        "persistence_enabled": True,
        "persistence_path": str(database_path()),
    }
    if not configured_path:
        status["persistence_warning"] = "GLIRN_DB_PATH is using non-persistent default storage"
    return status


@contextmanager
def _connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_schema():
    with _lock, _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
                category TEXT NOT NULL,
                record_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (category, record_id)
            );
            CREATE TABLE IF NOT EXISTS state (
                state_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS action_history (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                subject_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def upsert_record(category, record_id, payload):
    initialize_schema()
    now = datetime.now(timezone.utc).isoformat()
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO records (category, record_id, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category, record_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (str(category), str(record_id), serialized, now, now),
        )


def list_records(category):
    initialize_schema()
    with _lock, _connect() as connection:
        rows = connection.execute(
            "SELECT payload_json FROM records WHERE category = ? ORDER BY created_at, record_id",
            (str(category),),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def set_state(state_key, payload):
    initialize_schema()
    now = datetime.now(timezone.utc).isoformat()
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO state (state_key, payload_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(state_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (str(state_key), serialized, now),
        )


def get_state(state_key, default=None):
    initialize_schema()
    with _lock, _connect() as connection:
        row = connection.execute(
            "SELECT payload_json FROM state WHERE state_key = ?",
            (str(state_key),),
        ).fetchone()
    return json.loads(row["payload_json"]) if row else default


def append_action(action_type, subject_id, payload):
    initialize_schema()
    now = datetime.now(timezone.utc).isoformat()
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO action_history (action_type, subject_id, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(action_type), str(subject_id or ""), serialized, now),
        )


def list_actions():
    initialize_schema()
    with _lock, _connect() as connection:
        rows = connection.execute(
            "SELECT action_type, subject_id, payload_json, created_at FROM action_history ORDER BY action_id",
        ).fetchall()
    return [
        {
            "action_type": row["action_type"],
            "subject_id": row["subject_id"],
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
