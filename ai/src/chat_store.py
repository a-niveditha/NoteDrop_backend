"""
chat_store.py

SQLite persistence for chat sessions. Every message in every session is
stored, so past conversations can be listed and resumed later.

Schema:
  sessions(session_id, title, rolling_summary, created_at, updated_at)
  messages(id, session_id, role, content, tool_call_id, tool_calls_json, created_at)
"""

import os
import json
import sqlite3 
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "chat_history.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            rolling_summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_call_id TEXT,
            tool_calls_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)
    conn.commit()
    conn.close()


def create_session(title: str | None = None) -> str:
    session_id = str(uuid.uuid4())
    now = _now()
    conn = _connect()
    conn.execute(
        "INSERT INTO sessions (session_id, title, rolling_summary, created_at, updated_at) "
        "VALUES (?, ?, NULL, ?, ?)",
        (session_id, title, now, now),
    )
    conn.commit()
    conn.close()
    return session_id


def set_session_title_if_unset(session_id: str, title: str) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE sessions SET title = ? WHERE session_id = ? AND (title IS NULL OR title = '')",
        (title[:80], session_id),
    )
    conn.commit()
    conn.close()


def save_message(
    session_id: str,
    role: str,
    content: str | None,
    tool_call_id: str | None = None,
    tool_calls: list | None = None,
) -> None:
    now = _now()
    conn = _connect()
    conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_call_id, tool_calls_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            role,
            content,
            tool_call_id,
            json.dumps(tool_calls) if tool_calls else None,
            now,
        ),
    )
    conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
    conn.commit()
    conn.close()


def update_rolling_summary(session_id: str, summary: str) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE sessions SET rolling_summary = ?, updated_at = ? WHERE session_id = ?",
        (summary, _now(), session_id),
    )
    conn.commit()
    conn.close()


def get_rolling_summary(session_id: str) -> str | None:
    conn = _connect()
    row = conn.execute(
        "SELECT rolling_summary FROM sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return row["rolling_summary"] if row else None


def load_messages(session_id: str) -> list[dict]:
    """
    Reconstructs the message list in the exact dict shape the OpenAI API
    expects, so it can be dropped straight back into ChatSession.messages.
    """
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
    ).fetchall()
    conn.close()

    messages = []
    for row in rows:
        entry = {"role": row["role"], "content": row["content"]}
        if row["tool_call_id"]:
            entry["tool_call_id"] = row["tool_call_id"]
        if row["tool_calls_json"]:
            entry["tool_calls"] = json.loads(row["tool_calls_json"])
        messages.append(entry)
    return messages


def list_sessions(limit: int = 50) -> list[sqlite3.Row]:
    conn = _connect()
    rows = conn.execute(
        "SELECT session_id, title, created_at, updated_at FROM sessions "
        "ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


init_db()