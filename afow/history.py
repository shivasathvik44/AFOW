"""SQLite database management for transaction history."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def _resolve_dir(path: str | os.PathLike) -> Path:
    """Expand environment variables, user tildes, and return resolved Path."""
    return Path(os.path.expandvars(str(path))).expanduser().resolve()


def get_db_path() -> Path:
    """Return the Path to the SQLite history database according to OS standards.

    - If AFOW_DB_PATH is set, use it.
    - Windows: %LOCALAPPDATA%/afow or %APPDATA%/afow
    - macOS: ~/Library/Application Support/afow
    - Linux / POSIX (Fedora): Follows XDG Base Directory specification:
      $XDG_DATA_HOME/afow (default: ~/.local/share/afow).
      Falls back to ~/.config/afow if a legacy database already exists there.
    """
    env_path = os.getenv("AFOW_DB_PATH")
    if env_path:
        p = _resolve_dir(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    system = sys.platform
    if system == "win32":
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        db_dir = Path(base) / "afow" if base else Path.home() / "AppData" / "Local" / "afow"
    elif system == "darwin":
        db_dir = Path.home() / "Library" / "Application Support" / "afow"
    else:
        # Linux / POSIX / Fedora (XDG Base Directory specification)
        legacy_path = Path.home() / ".config" / "afow" / "history.db"
        xdg_data = os.getenv("XDG_DATA_HOME")
        if xdg_data:
            db_dir = _resolve_dir(xdg_data) / "afow"
        elif legacy_path.exists():
            db_dir = legacy_path.parent
        else:
            db_dir = Path.home() / ".local" / "share" / "afow"

    try:
        db_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If target directory is read-only (e.g. sandbox, container, live OS), try fallbacks
        for fallback in (Path.home() / ".config" / "afow", Path("/tmp") / "afow"):
            try:
                fallback.mkdir(parents=True, exist_ok=True)
                db_dir = fallback
                break
            except OSError:
                continue

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
    resolved = _resolve_dir(root_dir)
    root_abs = str(resolved)
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
    resolved = _resolve_dir(root_dir)
    root_abs = str(resolved)
    root_posix = resolved.as_posix()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, timestamp, root_dir, dry_run FROM runs WHERE root_dir = ? OR root_dir = ? ORDER BY id DESC LIMIT 1;",
            (root_abs, root_posix),
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
