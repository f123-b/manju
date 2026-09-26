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


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(row[1] == column_name for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall())
