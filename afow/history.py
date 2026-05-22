"""SQLite database management for transaction history."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def get_db_path() -> Path:
    """Return the Path to the SQLite history database."""
    env_path = os.getenv("AFOW_DB_PATH")
    if env_path:
        return Path(env_path)

    appdata = os.getenv("APPDATA")
    if appdata:
        db_dir = Path(appdata) / "afow"
    else:
        db_dir = Path.home() / ".config" / "afow"

    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "history.db"


def get_connection() -> sqlite3.Connection:
    """Return a database connection with initialized tables."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Initialize schema
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            root_dir TEXT NOT NULL,
            dry_run INTEGER NOT NULL CHECK (dry_run IN (0, 1))
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            src_path TEXT NOT NULL,
            dest_path TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    return conn


def log_run(
    root_dir: str | os.PathLike,
    moves: list[tuple[str, str]],
    dry_run: bool = False,
    timestamp: str | None = None,
) -> int:
    """Log an organize run and its associated moves. Returns the run ID."""
    root_abs = str(Path(root_dir).resolve())
    ts = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    dry_run_int = 1 if dry_run else 0

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runs (timestamp, root_dir, dry_run) VALUES (?, ?, ?);",
            (ts, root_abs, dry_run_int),
        )
        run_id = cursor.lastrowid
        assert run_id is not None

        if moves:
            cursor.executemany(
                "INSERT INTO moves (run_id, src_path, dest_path) VALUES (?, ?, ?);",
                [(run_id, src, dest) for src, dest in moves],
            )
        conn.commit()
        return run_id


def get_history() -> list[dict]:
    """Retrieve all organization runs sorted by newest first."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, root_dir, dry_run FROM runs ORDER BY id DESC;")
        return [dict(row) for row in cursor.fetchall()]


def get_run(run_id: int) -> dict | None:
    """Retrieve details and moves for a specific run ID."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, root_dir, dry_run FROM runs WHERE id = ?;", (run_id,))
        run_row = cursor.fetchone()
        if not run_row:
            return None

        cursor.execute("SELECT src_path, dest_path FROM moves WHERE run_id = ? ORDER BY id ASC;", (run_id,))
        move_rows = cursor.fetchall()
        
        run_dict = dict(run_row)
        run_dict["moves"] = [dict(row) for row in move_rows]
        return run_dict


def get_latest_run(root_dir: str | os.PathLike) -> dict | None:
    """Retrieve the most recent run for a specific target folder."""
    root_abs = str(Path(root_dir).resolve())
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, timestamp, root_dir, dry_run FROM runs WHERE root_dir = ? ORDER BY id DESC LIMIT 1;",
            (root_abs,),
        )
        run_row = cursor.fetchone()
        if not run_row:
            return None
        return get_run(run_row["id"])


def delete_run(run_id: int) -> None:
    """Delete a run and its moves from the database."""
    with get_connection() as conn:
        conn.execute("DELETE FROM runs WHERE id = ?;", (run_id,))
        conn.commit()
