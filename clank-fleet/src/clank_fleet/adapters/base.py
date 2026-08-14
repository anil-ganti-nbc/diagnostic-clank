"""Shared read-only SQLite helpers for adapters."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def open_readonly(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def fetchall(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(con.execute(sql, params).fetchall())
