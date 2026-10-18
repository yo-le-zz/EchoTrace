"""Gestionnaire SQLite : cibles, recherches, résultats, faux positifs et cache HTTP."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any

from echotrace import paths

STATUSES = ("", "confirmed", "to_check", "false_positive")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  REAL    NOT NULL,
    data        TEXT    NOT NULL,
    input_score INTEGER NOT NULL DEFAULT 0,
    label       TEXT    NOT NULL DEFAULT '',
    purpose     TEXT    NOT NULL DEFAULT '',
    target_key  TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS searches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id   INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    module      TEXT    NOT NULL,
    query       TEXT    NOT NULL,
    started_at  REAL    NOT NULL,
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
    found_at    REAL    NOT NULL,
    status      TEXT    NOT NULL DEFAULT '',
    note        TEXT    NOT NULL DEFAULT ''
);

-- Résultats marqués « faux positif » : ne sont plus proposés pour la même cible.
CREATE TABLE IF NOT EXISTS ignored (
    target_key  TEXT    NOT NULL,
    url         TEXT    NOT NULL,
    created_at  REAL    NOT NULL,
    PRIMARY KEY (target_key, url)
);

CREATE TABLE IF NOT EXISTS cache (
    key         TEXT    PRIMARY KEY,
    value       TEXT    NOT NULL,
    expires_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_results_target ON results(target_id);
CREATE INDEX IF NOT EXISTS idx_results_module ON results(module);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);
"""

# Colonnes ajoutées après la première version du schéma : (table, colonne, définition).
_MIGRATIONS = [
    ("targets", "purpose", "TEXT NOT NULL DEFAULT ''"),
    ("targets", "target_key", "TEXT NOT NULL DEFAULT ''"),
    ("results", "status", "TEXT NOT NULL DEFAULT ''"),
    ("results", "note", "TEXT NOT NULL DEFAULT ''"),
]

# Bases déjà initialisées dans ce processus (une base par chemin).
_initialized: set[str] = set()


def _migrate(conn: sqlite3.Connection) -> None:
    """Ajoute les colonnes manquantes d'une base créée par une version plus ancienne."""
    for table, column, definition in _MIGRATIONS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Ouvre une connexion, valide la transaction en cas de succès puis ferme.

    `with sqlite3.connect()` seul ne ferme pas la connexion : sous Windows le
    fichier resterait verrouillé tant que le ramasse-miettes ne passe pas.
    """
    db_path = paths.database_file()
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        if str(db_path) not in _initialized:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            _migrate(conn)
            _initialized.add(str(db_path))
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Crée les tables si besoin (appelé implicitement à la première connexion)."""
    with get_conn():
        pass


def _decode(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["data"] = json.loads(item["data"])
    return item


# ─── Cibles ───────────────────────────────────────────────────────────────────


def save_target(data: dict, input_score: int, label: str = "", purpose: str = "",
                target_key: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO targets (created_at, data, input_score, label, purpose, target_key) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), json.dumps(data, ensure_ascii=False), input_score, label, purpose, target_key),
        )
        return int(cur.lastrowid)


def get_target(target_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM targets WHERE id=?", (target_id,)).fetchone()
    return _decode(row) if row else None


def list_targets() -> list[dict]:
    """Cibles les plus récentes d'abord, avec le nombre de résultats (`results_count`)."""
    query = """
        SELECT t.*, (SELECT COUNT(*) FROM results r WHERE r.target_id = t.id) AS results_count
        FROM targets t ORDER BY t.created_at DESC
    """
    with get_conn() as conn:
        return [_decode(row) for row in conn.execute(query).fetchall()]


def previous_target(target_key: str, before_id: int) -> dict | None:
    """Analyse précédente de la même cible (même empreinte), pour comparer deux passages."""
    if not target_key:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM targets WHERE target_key=? AND id<? ORDER BY id DESC LIMIT 1",
            (target_key, before_id),
        ).fetchone()
    return _decode(row) if row else None


def delete_target(target_id: int) -> None:
    """Supprime une cible ; recherches et résultats suivent (ON DELETE CASCADE)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM targets WHERE id=?", (target_id,))


# ─── Résultats ────────────────────────────────────────────────────────────────

_INSERT_RESULT = """
    INSERT INTO results
        (target_id, search_id, module, platform, url, title, username, confidence, data, found_at)
    VALUES (?,?,?,?,?,?,?,?,?,?)
"""


def save_result(
    target_id: int,
    search_id: int | None,
    module: str,
    platform: str,
    url: str,
    title: str,
    username: str,
    confidence: float,
    data: dict,
) -> int:
    row = (target_id, search_id, module, platform, url, title, username, confidence,
           json.dumps(data, ensure_ascii=False), time.time())
    with get_conn() as conn:
        return int(conn.execute(_INSERT_RESULT, row).lastrowid)


def save_results(target_id: int, search_id: int | None, results: Iterable) -> list[int]:
    """Enregistre des `OsintResult` en une transaction ; retourne leurs identifiants."""
    now = time.time()
    ids: list[int] = []
    with get_conn() as conn:
        for r in results:
            cur = conn.execute(_INSERT_RESULT, (
                target_id, search_id, r.module, r.platform, r.url, r.title, r.username,
                r.confidence, json.dumps(r.data, ensure_ascii=False), now))
            ids.append(int(cur.lastrowid))
    return ids


def get_results(target_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE target_id=? ORDER BY confidence DESC, id",
            (target_id,),
        ).fetchall()
    return [_decode(row) for row in rows]


def update_result(result_id: int, confidence: float, data: dict) -> None:
    """Met à jour la confiance et les données d'un résultat (étape de vérification)."""
    with get_conn() as conn:
        conn.execute("UPDATE results SET confidence=?, data=? WHERE id=?",
                     (confidence, json.dumps(data, ensure_ascii=False), result_id))


def set_result_review(result_id: int, status: str | None = None, note: str | None = None) -> None:
    """Définit le statut (voir STATUSES) et/ou la note d'un résultat.

    Marquer « faux positif » mémorise aussi l'URL pour cette cible ; changer ce
    statut ensuite la réautorise.
    """
    if status is not None and status not in STATUSES:
        raise ValueError(f"Statut inconnu : {status}")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT r.url, t.target_key FROM results r JOIN targets t ON t.id = r.target_id "
            "WHERE r.id=?", (result_id,)).fetchone()
        if row is None:
            return
        if status is not None:
            conn.execute("UPDATE results SET status=? WHERE id=?", (status, result_id))
            if row["url"] and row["target_key"]:
                if status == "false_positive":
                    conn.execute("INSERT OR IGNORE INTO ignored (target_key, url, created_at) "
                                 "VALUES (?,?,?)", (row["target_key"], row["url"], time.time()))
                else:
                    conn.execute("DELETE FROM ignored WHERE target_key=? AND url=?",
                                 (row["target_key"], row["url"]))
        if note is not None:
            conn.execute("UPDATE results SET note=? WHERE id=?", (note, result_id))


def ignored_urls(target_key: str) -> set[str]:
    if not target_key:
        return set()
    with get_conn() as conn:
        rows = conn.execute("SELECT url FROM ignored WHERE target_key=?", (target_key,)).fetchall()
    return {row["url"] for row in rows}


# ─── Protection des données ───────────────────────────────────────────────────


def purge_older_than(days: int) -> int:
    """Supprime les analyses de plus de `days` jours ; retourne leur nombre. 0 jour = rien."""
    if days <= 0:
        return 0
    cutoff = time.time() - days * 86400
    with get_conn() as conn:
        ids = [row["id"] for row in conn.execute("SELECT id FROM targets WHERE created_at < ?", (cutoff,))]
        conn.execute("DELETE FROM targets WHERE created_at < ?", (cutoff,))
        conn.execute("DELETE FROM ignored WHERE created_at < ?", (cutoff,))
    return len(ids)


def export_everything() -> dict:
    """Toutes les données personnelles stockées (droit d'accès) : cibles, résultats, faux positifs."""
    targets = list_targets()
    for target in targets:
        target["results"] = get_results(target["id"])
    with get_conn() as conn:
        ignored = [dict(row) for row in conn.execute("SELECT * FROM ignored")]
    return {"targets": targets, "ignored": ignored}


def erase_everything() -> None:
    """Efface toutes les cibles, résultats, faux positifs et le cache (droit à l'effacement)."""
    with get_conn() as conn:
        for table in ("results", "searches", "targets", "ignored", "cache"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence")


# ─── Cache ────────────────────────────────────────────────────────────────────


def cache_get(key: str) -> Any | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM cache WHERE key=? AND expires_at > ?", (key, time.time())
        ).fetchone()
    return json.loads(row["value"]) if row else None


def cache_set(key: str, value: Any, ttl_seconds: int = 86400) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?,?,?)",
            (key, json.dumps(value, ensure_ascii=False), time.time() + ttl_seconds),
        )


def cache_clean() -> None:
    """Supprime les entrées expirées."""
    with get_conn() as conn:
        conn.execute("DELETE FROM cache WHERE expires_at <= ?", (time.time(),))


def cache_clear() -> None:
    """Vide entièrement le cache."""
    with get_conn() as conn:
        conn.execute("DELETE FROM cache")


# ─── Suivi des recherches ─────────────────────────────────────────────────────


def start_search(target_id: int, module: str, query: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO searches (target_id, module, query, started_at, status) "
            "VALUES (?,?,?,?,'running')",
            (target_id, module, query, time.time()),
        )
        return int(cur.lastrowid)


def finish_search(search_id: int, status: str = "done") -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE searches SET finished_at=?, status=? WHERE id=?",
            (time.time(), status, search_id),
        )
