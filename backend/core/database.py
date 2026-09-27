from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DB_PATH, ROOT


DB_LOCK = threading.RLock()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    with DB_LOCK:
        connection = connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _row_value(row: sqlite3.Row | None, key: str, default=None):
    return default if row is None else row[key]


def init_database() -> None:
    migration_file = ROOT / "backend" / "migrations" / "001_initial.sql"
    with session() as connection:
        connection.executescript(migration_file.read_text(encoding="utf-8"))
        # The migration file is also used for fresh databases. These guards
        # keep an existing V1 database compatible when a task-runtime field
        # is added without requiring a destructive reset.
        for column, definition in (
            ("provider_task_id", "TEXT"),
            ("status_url", "TEXT"),
        ):
            if not column_exists(connection, "generation_tasks", column):
                connection.execute(f"ALTER TABLE generation_tasks ADD COLUMN {column} {definition}")
        _ensure_generation_task_targets(connection)
        for table, column, definition in (
            ("characters", "aliases_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("characters", "age_range", "TEXT NOT NULL DEFAULT ''"),
            ("characters", "identity_anchors_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("characters", "persistent_performance_facts_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("characters", "canonical_reference_id", "TEXT"),
            ("characters", "identity_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("characters", "locked_at", "TEXT"),
            ("shots", "stale", "INTEGER NOT NULL DEFAULT 0"),
            ("shots", "stale_reason", "TEXT NOT NULL DEFAULT ''"),
            ("shot_characters", "id", "TEXT"),
            ("shot_characters", "look_id", "TEXT"),
            ("shot_characters", "primary_reference_id", "TEXT"),
            ("shot_characters", "position", "INTEGER NOT NULL DEFAULT 0"),
            ("shot_characters", "emotion", "TEXT NOT NULL DEFAULT ''"),
            ("shot_characters", "action", "TEXT NOT NULL DEFAULT ''"),
            ("shot_characters", "state_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("shot_characters", "continuity_overrides_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("dependencies", "status", "TEXT NOT NULL DEFAULT 'active'"),
            ("dependencies", "stale_reason", "TEXT NOT NULL DEFAULT ''"),
        ):
            if not column_exists(connection, table, column):
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_shot_characters_character ON shot_characters(character_id, shot_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_shot_characters_look ON shot_characters(look_id, shot_id)")
        character_migration = ROOT / "backend" / "migrations" / "002_character_engine.sql"
        connection.executescript(character_migration.read_text(encoding="utf-8"))
        audio_migration = ROOT / "backend" / "migrations" / "003_audio_engine.sql"
        connection.executescript(audio_migration.read_text(encoding="utf-8"))
        runtime_migration = ROOT / "backend" / "migrations" / "004_runtime_settings.sql"
        connection.executescript(runtime_migration.read_text(encoding="utf-8"))
        agent_migration = ROOT / "backend" / "migrations" / "005_agent_runs.sql"
        connection.executescript(agent_migration.read_text(encoding="utf-8"))
        render_migration = ROOT / "backend" / "migrations" / "006_render_jobs.sql"
        connection.executescript(render_migration.read_text(encoding="utf-8"))
        video_timeline_migration = ROOT / "backend" / "migrations" / "007_video_timeline.sql"
        connection.executescript(video_timeline_migration.read_text(encoding="utf-8"))
        connection.execute("UPDATE shot_characters SET id = 'SCB-' || lower(hex(randomblob(6))) WHERE id IS NULL")
        connection.execute("UPDATE shot_characters SET position = (SELECT COUNT(*) FROM shot_characters earlier WHERE earlier.shot_id = shot_characters.shot_id AND earlier.rowid <= shot_characters.rowid) - 1 WHERE position = 0")
        has_projects = connection.execute("SELECT 1 FROM projects LIMIT 1").fetchone()
        legacy = connection.execute(
            "SELECT data_json FROM project_state ORDER BY updated_at DESC LIMIT 1"
        ).fetchone() if table_exists(connection, "project_state") else None
    if not has_projects:
        from ..domain.seed import seed_demo_project, seed_legacy_project

        if legacy:
            seed_legacy_project(json.loads(legacy["data_json"]))
        else:
            seed_demo_project()
    from ..domain.character_assets import migrate_legacy_character_assets

    migrate_legacy_character_assets()
    from ..domain.audio_engine import migrate_legacy_audio

    migrate_legacy_audio()
    from ..domain.video_engine import ensure_video_clips

    ensure_video_clips()


def _ensure_generation_task_targets(connection: sqlite3.Connection) -> None:
    """Make generation_tasks target any durable asset, not only a shot.

    V1 declared shot_id NOT NULL. Rebuilding once is safer than maintaining a
    second queue or silently putting character work into an in-memory path.
    """
    columns = {row[1]: row for row in connection.execute("PRAGMA table_info(generation_tasks)").fetchall()}
    if "target_type" not in columns:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.commit()
        connection.executescript(
            """
            CREATE TABLE generation_tasks_v2 (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              shot_id TEXT REFERENCES shots(id) ON DELETE CASCADE,
              target_type TEXT NOT NULL DEFAULT 'shot',
              target_id TEXT,
              type TEXT NOT NULL DEFAULT '视频',
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'Queued',
              prompt TEXT NOT NULL DEFAULT '',
              parameters_json TEXT NOT NULL DEFAULT '{}',
              estimated_cost REAL NOT NULL DEFAULT 0,
              actual_cost REAL,
              progress INTEGER NOT NULL DEFAULT 0,
              retry_count INTEGER NOT NULL DEFAULT 0,
              max_retries INTEGER NOT NULL DEFAULT 3,
              error_message TEXT,
              provider_task_id TEXT,
              status_url TEXT,
              queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              started_at TEXT,
              completed_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO generation_tasks_v2(
              id, project_id, shot_id, target_type, target_id, type, provider, model,
              status, prompt, parameters_json, estimated_cost, actual_cost, progress,
              retry_count, max_retries, error_message, provider_task_id, status_url,
              queued_at, started_at, completed_at, created_at, updated_at
            )
            SELECT id, project_id, shot_id, 'shot', shot_id, type, provider, model,
              status, prompt, parameters_json, estimated_cost, actual_cost, progress,
              retry_count, max_retries, error_message, provider_task_id, status_url,
              queued_at, started_at, completed_at, created_at, updated_at
            FROM generation_tasks;
            DROP TABLE generation_tasks;
            ALTER TABLE generation_tasks_v2 RENAME TO generation_tasks;
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON generation_tasks(status, queued_at);
            """
        )
        connection.commit()
        connection.execute("PRAGMA foreign_keys = ON")
    else:
        if "target_id" not in columns:
            connection.execute("ALTER TABLE generation_tasks ADD COLUMN target_id TEXT")
        connection.execute("UPDATE generation_tasks SET target_id = COALESCE(target_id, shot_id) WHERE target_type = 'shot'")


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(row[1] == column_name for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall())
