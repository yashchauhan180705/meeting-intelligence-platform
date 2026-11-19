"""SQLite database module — async via aiosqlite.

Provides `init_db()` to create schema and `get_db()` for connection access.
Schema matches data-model.md exactly.
"""

from __future__ import annotations

import aiosqlite
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "meeting_intel.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id                  TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    duration_seconds    REAL,
    speaker_count_hint  INTEGER CHECK(speaker_count_hint IS NULL OR (speaker_count_hint BETWEEN 1 AND 10)),
    processing_status   TEXT NOT NULL DEFAULT 'uploading',
    is_debate           INTEGER NOT NULL DEFAULT 0,
    consent_granted_at  TEXT NOT NULL,
    last_completed_step TEXT,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS audio_files (
    id                TEXT PRIMARY KEY,
    conversation_id   TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    file_path         TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    format            TEXT NOT NULL,
    size_bytes        INTEGER NOT NULL,
    duration_seconds  REAL
);

CREATE TABLE IF NOT EXISTS speakers (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT    NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    system_label    TEXT    NOT NULL,
    display_name    TEXT    NOT NULL,
    color_index     INTEGER NOT NULL CHECK(color_index BETWEEN 0 AND 9),
    order_index     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    speaker_id      TEXT NOT NULL REFERENCES speakers(id),
    start_time      REAL NOT NULL,
    end_time        REAL NOT NULL CHECK(end_time > start_time),
    text            TEXT NOT NULL,
    confidence      REAL,
    is_low_confidence INTEGER NOT NULL DEFAULT 0,
    language_code   TEXT,
    order_index     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics (
    id                      TEXT PRIMARY KEY,
    conversation_id         TEXT NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    computed_at             TEXT NOT NULL,
    total_duration_seconds  REAL NOT NULL,
    interruption_count      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS speaker_metrics (
    id                      TEXT PRIMARY KEY,
    analytics_id            TEXT NOT NULL REFERENCES analytics(id) ON DELETE CASCADE,
    speaker_id              TEXT NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
    talk_time_seconds       REAL NOT NULL,
    talk_time_pct           REAL NOT NULL,
    turn_count              INTEGER NOT NULL,
    avg_turn_length_seconds REAL NOT NULL,
    interruption_count      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS summaries (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    overview        TEXT NOT NULL,
    key_points      TEXT NOT NULL,
    decisions       TEXT NOT NULL,
    action_items    TEXT NOT NULL,
    debate_claims   TEXT,
    generated_at    TEXT NOT NULL,
    transcript_hash TEXT NOT NULL,
    model_used      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_segments_conversation
    ON segments(conversation_id, order_index);
CREATE INDEX IF NOT EXISTS idx_speaker_metrics_analytics
    ON speaker_metrics(analytics_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created
    ON conversations(created_at DESC);
"""


async def init_db(db_path: Path | None = None) -> None:
    """Create all tables and indexes if they don't already exist."""
    path = db_path or _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(path)) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.executescript(_SCHEMA)
        await db.commit()


async def get_db(db_path: Path | None = None) -> aiosqlite.Connection:
    """Return an open connection with FK enforcement enabled."""
    path = db_path or _DB_PATH
    db = await aiosqlite.connect(str(path))
    await db.execute("PRAGMA foreign_keys = ON")
    db.row_factory = aiosqlite.Row
    return db
