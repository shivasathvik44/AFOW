"""Reverse a previous organize() run by replaying the undo log backwards."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from afow.organizer import Summary, UNDO_FILENAME


def undo(path: str | os.PathLike, run_id: int | None = None) -> Summary:
    """Reverse the moves recorded in SQLite or legacy JSON log.

    If run_id is provided, reverse that specific run from the database.
    If run_id is None, try to reverse the latest SQLite run first.
    Otherwise, fall back to reversing the legacy JSON log for this path.
    """
    root = Path(os.path.expandvars(str(path))).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    log_path = root / UNDO_FILENAME
    summary = Summary(root=str(root))

    # Database-backed undo
    from afow.history import delete_run, get_latest_run, get_run

    run_data = None
    if run_id is not None:
        run_data = get_run(run_id)
        if not run_data:
            raise ValueError(f"No run found with ID: {run_id}")
    else:
        run_data = get_latest_run(root)

    if run_data:
        moves = run_data.get("moves", [])
        touched_dirs = set()

        for entry in reversed(moves):
            src_rel = entry["dest_path"]
            dest_rel = entry["src_path"]

            if not src_rel:
                continue

            src = root / src_rel
            dest = root / dest_rel

            # If src doesn't exist (or isn't a symlink), skip it
            if not src.exists() and not src.is_symlink():
                summary.skipped += 1
                continue

            # If dest_rel is empty, it was a deletion, skip restoring it
            if not dest_rel:
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                try:
                    target_path = os.readlink(src)
                    target_abs = (src.parent / target_path).resolve()
                    if target_abs.exists():
                        shutil.copy2(target_abs, dest)
                    src.unlink()
                except OSError:
                    shutil.move(str(src), str(dest))
            else:
                shutil.move(str(src), str(dest))

            touched_dirs.add(src.parent)
            summary.moved += 1

        for d in touched_dirs:
            try:
                if d != root and d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

        delete_run(run_data["id"])

        # Clean up local JSON undo file if it matches
        if log_path.exists():
            try:
                log_path.unlink()
            except OSError:
                pass

        return summary

    # Fallback to legacy JSON undo if it exists
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
            moves = log.get("moves", [])
            touched_dirs = set()
            for entry in reversed(moves):
                src = root / entry["to"]
                dest = root / entry["from"]
                
                if not src.exists() and not src.is_symlink():
                    summary.skipped += 1
                    continue
                
                dest.parent.mkdir(parents=True, exist_ok=True)
                if src.is_symlink():
                    try:
                        target_path = os.readlink(src)
                        target_abs = (src.parent / target_path).resolve()
                        if target_abs.exists():
                            shutil.copy2(target_abs, dest)
                        src.unlink()
                    except OSError:
                        shutil.move(str(src), str(dest))
                else:
                    shutil.move(str(src), str(dest))
                
                touched_dirs.add(src.parent)
                summary.moved += 1

            for d in touched_dirs:
                try:
                    if d != root and d.is_dir() and not any(d.iterdir()):
                        d.rmdir()
                except OSError:
                    pass

            log_path.unlink()
            return summary
        except Exception:
            raise

    return summary

