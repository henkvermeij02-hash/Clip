"""SQLite database access and schema migrations.

Each call to :func:`connect` opens a fresh connection; SQLite in WAL mode
handles concurrent readers and one writer safely, which is all we need for a
single-user local app with a few background worker threads.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config

# Migrations run in order, exactly once each. Never edit an old migration:
# add a new one so existing databases upgrade cleanly.
MIGRATIONS: list[str] = [
    # 1 — Phase 1 foundation
    """
    CREATE TABLE videos (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        title               TEXT,
        original_filename   TEXT NOT NULL,
        file_path           TEXT NOT NULL,
        storage_mode        TEXT NOT NULL CHECK (storage_mode IN ('copied', 'referenced')),
        file_size           INTEGER NOT NULL,
        content_hash        TEXT NOT NULL UNIQUE,
        status              TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'processing', 'ready', 'error')),
        error               TEXT,
        duration_seconds    REAL,
        width               INTEGER,
        height              INTEGER,
        fps                 REAL,
        video_codec         TEXT,
        audio_codec         TEXT,
        has_audio           INTEGER,
        bitrate             INTEGER,
        container           TEXT,
        metadata_json       TEXT,
        thumbnail_path      TEXT,
        -- Rights tracking: owning a recording does not automatically mean
        -- you may monetise it. These fields make the situation explicit.
        rights_source       TEXT NOT NULL DEFAULT 'own_recording'
                            CHECK (rights_source IN ('own_recording', 'licensed', 'other')),
        rights_confirmed    INTEGER NOT NULL DEFAULT 0,
        monetization_status TEXT NOT NULL DEFAULT 'unknown'
                            CHECK (monetization_status IN ('unknown', 'not_monetized', 'cleared', 'not_allowed')),
        rights_notes        TEXT,
        notes               TEXT,
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL
    );
    CREATE INDEX idx_videos_status ON videos(status);

    CREATE TABLE jobs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        type            TEXT NOT NULL,
        status          TEXT NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
        video_id        INTEGER REFERENCES videos(id) ON DELETE CASCADE,
        payload_json    TEXT NOT NULL DEFAULT '{}',
        result_json     TEXT,
        dedupe_key      TEXT,
        priority        INTEGER NOT NULL DEFAULT 100,
        progress        REAL NOT NULL DEFAULT 0,
        message         TEXT,
        error           TEXT,
        error_detail    TEXT,
        attempts        INTEGER NOT NULL DEFAULT 0,
        max_attempts    INTEGER NOT NULL DEFAULT 3,
        run_after       TEXT,
        created_at      TEXT NOT NULL,
        started_at      TEXT,
        finished_at     TEXT,
        updated_at      TEXT NOT NULL
    );
    CREATE INDEX idx_jobs_status ON jobs(status, priority, id);
    CREATE INDEX idx_jobs_video ON jobs(video_id);
    -- Prevents the same work from being queued twice while it is pending.
    CREATE UNIQUE INDEX idx_jobs_active_dedupe ON jobs(dedupe_key)
        WHERE dedupe_key IS NOT NULL AND status IN ('queued', 'running');

    CREATE TABLE settings (
        key         TEXT PRIMARY KEY,
        value_json  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );

    -- Licences for music, sound effects, voices, fonts and logos.
    CREATE TABLE licenses (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_type          TEXT NOT NULL
                            CHECK (asset_type IN ('music', 'sfx', 'voice', 'font', 'logo', 'model', 'other')),
        name                TEXT NOT NULL,
        source_url          TEXT,
        license_name        TEXT NOT NULL,
        license_url         TEXT,
        allows_commercial   INTEGER NOT NULL DEFAULT 0,
        attribution_required INTEGER NOT NULL DEFAULT 0,
        attribution_text    TEXT,
        file_path           TEXT,
        notes               TEXT,
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL
    );
    """,
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db_path() -> Path:
    return Path(config.DB_PATH)


def _new_connection() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Autocommit connection. Use :func:`transaction` for multi-statement writes."""
    conn = _new_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """A write transaction that takes the write lock immediately."""
    conn = _new_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.close()


def init_db() -> None:
    """Create the database file and apply any pending migrations."""
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        for index, sql in enumerate(MIGRATIONS[current:], start=current + 1):
            conn.execute("BEGIN IMMEDIATE")
            try:
                for statement in _split_sql(sql):
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {index}")
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise


def _split_sql(script: str) -> list[str]:
    """Split a migration script into statements (our migrations contain no
    semicolons inside string literals or triggers)."""
    statements = []
    for chunk in script.split(";"):
        lines = [ln for ln in chunk.splitlines() if not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if stmt:
            statements.append(stmt)
    return statements


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def loads(value: str | None, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
