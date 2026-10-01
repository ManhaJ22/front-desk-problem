"""SQLite schema and query helpers. No business logic lives here."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from backend import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS handbook_chunks (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  embedding TEXT NOT NULL,            -- JSON list[float]
  updated_at TEXT NOT NULL            -- ISO-8601 UTC
);

CREATE TABLE IF NOT EXISTS question_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT,                        -- shown OR would-have-been answer
  escalated INTEGER NOT NULL,
  escalation_reason TEXT,             -- out_of_scope | sensitive_forced | below_threshold | system_error
  is_sensitive INTEGER NOT NULL DEFAULT 0,
  is_urgent INTEGER NOT NULL DEFAULT 0,
  sensitivity_category TEXT,
  sensitivity_score INTEGER,
  sensitivity_rationale TEXT,
  semantic_score REAL,
  adherence_score REAL,
  combined_score REAL,
  threshold_used REAL,
  retrieved_chunk_ids TEXT NOT NULL DEFAULT '[]',
  claimed_facts TEXT NOT NULL DEFAULT '[]',
  unmatched_facts TEXT NOT NULL DEFAULT '[]',
  resolved INTEGER NOT NULL DEFAULT 0
);
"""

LOG_JSON_FIELDS = ("retrieved_chunk_ids", "claimed_facts", "unmatched_facts")
LOG_BOOL_FIELDS = ("escalated", "is_sensitive", "is_urgent", "resolved")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchall()


def _execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    with closing(get_conn()) as conn, conn:  # inner `conn` commits the transaction
        return conn.execute(sql, params)


def init_db() -> None:
    with closing(get_conn()) as conn:
        conn.executescript(SCHEMA)


# --- handbook_chunks ---------------------------------------------------------------


def _chunk(row: sqlite3.Row, with_embedding: bool) -> dict:
    chunk = dict(row)
    if with_embedding:
        chunk["embedding"] = json.loads(chunk["embedding"])
    else:
        chunk.pop("embedding", None)
    return chunk


def list_chunks(with_embedding: bool = False) -> list[dict]:
    rows = _query("SELECT * FROM handbook_chunks ORDER BY category, title")
    return [_chunk(r, with_embedding) for r in rows]


def get_chunk(chunk_id: str) -> dict | None:
    rows = _query("SELECT * FROM handbook_chunks WHERE id = ?", (chunk_id,))
    return _chunk(rows[0], with_embedding=False) if rows else None


def chunk_exists(chunk_id: str) -> bool:
    return bool(_query("SELECT 1 FROM handbook_chunks WHERE id = ?", (chunk_id,)))


def upsert_chunk(chunk_id: str, category: str, title: str, content: str, embedding: list[float]) -> dict:
    _execute(
        """
        INSERT INTO handbook_chunks (id, category, title, content, embedding, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          category = excluded.category, title = excluded.title, content = excluded.content,
          embedding = excluded.embedding, updated_at = excluded.updated_at
        """,
        (chunk_id, category, title, content, json.dumps(embedding), now_iso()),
    )
    return get_chunk(chunk_id)


def delete_chunk(chunk_id: str) -> bool:
    return _execute("DELETE FROM handbook_chunks WHERE id = ?", (chunk_id,)).rowcount > 0


def count_chunks() -> int:
    return _query("SELECT COUNT(*) FROM handbook_chunks")[0][0]


# --- question_log --------------------------------------------------------------------


def _log(row: sqlite3.Row) -> dict:
    entry = dict(row)
    for f in LOG_JSON_FIELDS:
        entry[f] = json.loads(entry[f])
    for f in LOG_BOOL_FIELDS:
        entry[f] = bool(entry[f])
    return entry


def insert_log(fields: dict) -> int:
    """Insert a question_log row. Missing columns take their defaults; created_at defaults to now."""
    row = {"created_at": now_iso(), **fields}
    for f in LOG_JSON_FIELDS:
        row[f] = json.dumps(row.get(f) or [])
    for f in LOG_BOOL_FIELDS:
        if f in row:
            row[f] = int(bool(row[f]))
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    return _execute(f"INSERT INTO question_log ({cols}) VALUES ({marks})", tuple(row.values())).lastrowid


def list_logs(view: str = "all") -> list[dict]:
    """view='needs_review' -> escalated and unresolved only; 'all' -> everything."""
    where = "WHERE escalated = 1 AND resolved = 0" if view == "needs_review" else ""
    return [_log(r) for r in _query(f"SELECT * FROM question_log {where}")]


def get_log(log_id: int) -> dict | None:
    rows = _query("SELECT * FROM question_log WHERE id = ?", (log_id,))
    return _log(rows[0]) if rows else None


def mark_resolved(log_id: int) -> dict | None:
    _execute("UPDATE question_log SET resolved = 1 WHERE id = ?", (log_id,))
    return get_log(log_id)
