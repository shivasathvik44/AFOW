"""Core organize logic: scan, plan, move, write undo log."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from afow.categories import ALL_CATEGORIES, categorize

UNDO_FILENAME = ".afow_undo.json"
UNDO_VERSION = 1

_CATEGORY_NAMES = frozenset(ALL_CATEGORIES)


@dataclass
class Summary:
    root: str
    moved: int = 0
    skipped: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    dry_run: bool = False
    duplicates: list[dict] = field(default_factory=list)
    planned_moves: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "moved": self.moved,
            "skipped": self.skipped,
            "by_category": self.by_category,
            "dry_run": self.dry_run,
            "duplicates": self.duplicates,
            "planned_moves": self.planned_moves,
        }


def _sha256(path: Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _is_cross_device(src: Path, dest_dir: Path) -> bool:
    """Determine if a move from src to dest_dir is cross-device."""
    curr = dest_dir
    while not curr.exists() and curr != curr.parent:
        curr = curr.parent
    try:
        return src.stat().st_dev != curr.stat().st_dev
    except OSError:
        return src.drive != curr.drive


def _move_cross_device(src: Path, dest: Path) -> None:
    """Move a file across devices, verifying the integrity with SHA-256."""
    src_hash = _sha256(src)
    shutil.copy2(src, dest)
    dest_hash = _sha256(dest)
    if src_hash != dest_hash:
        dest.unlink(missing_ok=True)
        raise ValueError(
            f"Hash verification failed for cross-device copy: {src} -> {dest}. "
            "Source file was preserved."
        )
    src.unlink()


def organize(
    path: str | os.PathLike,
    dry_run: bool = False,
    dedup_policy: str = "rename",
) -> Summary:
    """Organize top-level files in *path* into category subfolders.

    Subdirectories are left alone. On collision, the destination filename is
    auto-renamed with a ``(N)`` suffix. When ``dry_run`` is False, history is
    logged to SQLite and a local ``.afow_undo.json`` log is written.
    """
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    summary = Summary(root=str(root), dry_run=dry_run)
    moves: list[tuple[Path, Path, str]] = []  # (src, dest, type)
    reserved: set[Path] = set()
    seen_hashes: dict[str, Path] = {}  # hash -> planned/executed dest path

    # First, collect all files to organize
    entries: list[os.DirEntry] = []
    with os.scandir(root) as it:
        for entry in it:
            if _should_skip(entry):
                summary.skipped += 1
                continue
            entries.append(entry)

    # Sort entries by name for deterministic sorting
    entries.sort(key=lambda e: e.name)

    # Count frequency of each file size to avoid hashing unique files
    size_counts: dict[int, int] = {}
    for entry in entries:
        try:
            sz = entry.stat().st_size
        except OSError:
            sz = -1
        size_counts[sz] = size_counts.get(sz, 0) + 1

    # Plan moves and detect duplicates
    for entry in entries:
        src_path = Path(entry.path)
        try:
            sz = entry.stat().st_size
        except OSError:
            sz = -1

        if sz != -1 and size_counts.get(sz, 0) == 1:
            file_hash = ""
        else:
            file_hash = _sha256(src_path)

        category = categorize(entry.name)
        dest_dir = root / category
        dest_path = _unique_dest(dest_dir, entry.name, reserved)

        if file_hash and file_hash in seen_hashes:
            # Duplicate detected
            original_dest = seen_hashes[file_hash]
            dup_info = {
                "file": entry.name,
                "duplicate_of": str(original_dest.relative_to(root)),
                "policy": dedup_policy,
            }
            summary.duplicates.append(dup_info)

            if dedup_policy == "skip":
                summary.skipped += 1
                continue
            elif dedup_policy == "delete":
                moves.append((src_path, Path(""), "delete"))
            elif dedup_policy == "symlink":
                reserved.add(dest_path)
                moves.append((src_path, dest_path, f"symlink:{original_dest}"))
                summary.by_category[category] = summary.by_category.get(category, 0) + 1
            else:  # "rename"
                reserved.add(dest_path)
                moves.append((src_path, dest_path, "move"))
                seen_hashes[file_hash] = dest_path
                summary.by_category[category] = summary.by_category.get(category, 0) + 1
        else:
            if file_hash:
                seen_hashes[file_hash] = dest_path
            reserved.add(dest_path)
            moves.append((src_path, dest_path, "move"))
            summary.by_category[category] = summary.by_category.get(category, 0) + 1

    if dry_run:
        summary.moved = len([m for m in moves if m[2] != "delete" and m[2] != "skip"])
        summary.planned_moves = [
            {
                "from": str(src.relative_to(root)),
                "to": str(dest.relative_to(root)) if dest and str(dest) != "." and dest != Path("") else "",
                "type": move_type.split(":", 1)[0]
            }
            for src, dest, move_type in moves
        ]
        return summary

    executed_moves: list[tuple[str, str]] = []

    for src, dest, move_type in moves:
        try:
            if move_type == "delete":
                src.unlink(missing_ok=True)
                executed_moves.append((str(src.relative_to(root)), ""))
                summary.moved += 1
            elif move_type.startswith("symlink:"):
                original_dest = Path(move_type.split(":", 1)[1])
                dest.parent.mkdir(exist_ok=True)

                if dest.exists() or dest.is_symlink():
                    if dest.is_dir() and not dest.is_symlink():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()

                try:
                    target_rel = os.path.relpath(original_dest, dest.parent)
                    os.symlink(target_rel, dest)
                except OSError:
                    # Fallback to copy/move if symlink is not allowed
                    if _is_cross_device(src, dest.parent):
                        _move_cross_device(src, dest)
                    else:
                        shutil.move(str(src), str(dest))

                if src.exists():
                    src.unlink()

                executed_moves.append((str(src.relative_to(root)), str(dest.relative_to(root))))
                summary.moved += 1
            else:  # "move"
                dest.parent.mkdir(exist_ok=True)
                if _is_cross_device(src, dest.parent):
                    _move_cross_device(src, dest)
                else:
                    shutil.move(str(src), str(dest))
                executed_moves.append((str(src.relative_to(root)), str(dest.relative_to(root))))
                summary.moved += 1
        except Exception as e:
            # Let other moves proceed but keep track or re-raise if fatal.
            # In a production app we'd log this; here we re-raise to trigger rollback.
            raise e

    if executed_moves:
        # Write legacy JSON undo log for backwards compatibility
        _write_undo_log(root, [(root / src, root / dest) for src, dest in executed_moves if dest])
        # Write to centralized SQLite database
        from afow.history import log_run
        log_run(root, executed_moves, dry_run=False)

    return summary


def _should_skip(entry: os.DirEntry) -> bool:
    """Skip directories, the undo log, hidden files, and our own category folders."""
    name = entry.name
    if name == UNDO_FILENAME:
        return True
    if name.startswith("."):
        return True
    if entry.is_dir(follow_symlinks=False):
        return True
    if name in _CATEGORY_NAMES:
        return True
    return not entry.is_file(follow_symlinks=False)


def _unique_dest(dest_dir: Path, filename: str, reserved: set[Path]) -> Path:
    """Return a non-colliding destination Path inside *dest_dir*."""
    candidate = dest_dir / filename
    if candidate not in reserved and not candidate.exists():
        return candidate

    stem, dot, ext = filename.rpartition(".")
    if not dot:
        stem, ext = filename, ""
        suffix = ""
    else:
        suffix = f".{ext}"

    n = 1
    while True:
        candidate = dest_dir / f"{stem} ({n}){suffix}"
        if candidate not in reserved and not candidate.exists():
            return candidate
        n += 1


def _write_undo_log(root: Path, moves: list[tuple[Path, Path]]) -> None:
    log = {
        "version": UNDO_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "moves": [
            {
                "from": str(src.relative_to(root)),
                "to": str(dest.relative_to(root)),
            }
            for src, dest in moves
        ],
    }
    (root / UNDO_FILENAME).write_text(json.dumps(log, indent=2), encoding="utf-8")

