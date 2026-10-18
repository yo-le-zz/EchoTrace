"""
EchoTrace — SQLite Database Manager
"""

import sqlite3
import os
import json
import time
from typing import Optional, List, Dict, Any

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(_BASE_DIR, "cache", "echotrace.db")


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS targets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  REAL    NOT NULL DEFAULT (unixepoch('now')),
            data        TEXT    NOT NULL,
            input_score INTEGER NOT NULL DEFAULT 0,
            label       TEXT    NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS searches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id   INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
            module      TEXT    NOT NULL,
            query       TEXT    NOT NULL,
            started_at  REAL    NOT NULL DEFAULT (unixepoch('now')),
            finished_at REAL,
            status      TEXT    NOT NULL DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id   INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
            search_id   INTEGER REFERENCES searches(id) ON DELETE CASCADE,
            module      TEXT    NOT NULL,
            platform    TEXT    NOT NULL DEFAULT '',
            url         TEXT    NOT NULL DEFAULT '',
            title       TEXT    NOT NULL DEFAULT '',
            username    TEXT    NOT NULL DEFAULT '',
            confidence  REAL    NOT NULL DEFAULT 0.0,
            data        TEXT    NOT NULL DEFAULT '{}',
            found_at    REAL    NOT NULL DEFAULT (unixepoch('now'))
        );

        CREATE TABLE IF NOT EXISTS cache (
            key         TEXT    PRIMARY KEY,
            value       TEXT    NOT NULL,
            expires_at  REAL    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_results_target ON results(target_id);
        CREATE INDEX IF NOT EXISTS idx_results_module ON results(module);
        CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);
        """)


# ─── Target CRUD ──────────────────────────────────────────────────────────────

def save_target(data: dict, input_score: int, label: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO targets (data, input_score, label) VALUES (?, ?, ?)",
            (json.dumps(data), input_score, label)
        )
        return cur.lastrowid


def get_target(target_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM targets WHERE id=?", (target_id,)).fetchone()
        if row:
            d = dict(row)
            d["data"] = json.loads(d["data"])
            return d
    return None


def list_targets() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM targets ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["data"] = json.loads(d["data"])
            result.append(d)
        return result


# ─── Results CRUD ─────────────────────────────────────────────────────────────

def save_result(target_id: int, search_id: Optional[int], module: str,
                platform: str, url: str, title: str, username: str,
                confidence: float, data: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO results
               (target_id, search_id, module, platform, url, title, username, confidence, data)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (target_id, search_id, module, platform, url, title, username,
             confidence, json.dumps(data))
        )
        return cur.lastrowid


def get_results(target_id: int) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE target_id=? ORDER BY confidence DESC",
            (target_id,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["data"] = json.loads(d["data"])
            result.append(d)
        return result


# ─── Cache ────────────────────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM cache WHERE key=? AND expires_at > ?",
            (key, time.time())
        ).fetchone()
        if row:
            return json.loads(row["value"])
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 86400):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?,?,?)",
            (key, json.dumps(value), time.time() + ttl_seconds)
        )


def cache_clean():
    with get_conn() as conn:
        conn.execute("DELETE FROM cache WHERE expires_at <= ?", (time.time(),))


# ─── Search tracking ──────────────────────────────────────────────────────────

def start_search(target_id: int, module: str, query: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO searches (target_id, module, query, status) VALUES (?,?,?,'running')",
            (target_id, module, query)
        )
        return cur.lastrowid


def finish_search(search_id: int, status: str = "done"):
    with get_conn() as conn:
        conn.execute(
            "UPDATE searches SET finished_at=?, status=? WHERE id=?",
            (time.time(), status, search_id)
        )


# Init on import
init_db()