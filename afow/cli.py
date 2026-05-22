"""Command-line entry point for afow."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Sequence

from afow import __version__
from afow.organizer import Summary, organize
from afow.undo import undo


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="afow",
        description="Organize the top-level files of a directory into category folders.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Directory to organize (or to undo).",
    )
    parser.add_argument("--undo", action="store_true", help="Reverse a previous organize.")
    parser.add_argument("--run-id", type=int, help="Specific SQLite run ID to undo.")
    parser.add_argument("--history", action="store_true", help="List organization history.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without moving.")
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Confirm the plan before moving files."
    )
    parser.add_argument(
        "--dedup-policy",
        choices=["rename", "skip", "delete", "symlink"],
        default="rename",
        help="Policy for handling duplicate files (default: rename).",
    )
    parser.add_argument("--serve", action="store_true", help="Launch the web UI.")
    parser.add_argument("--port", type=int, default=5000, help="Port for --serve (default 5000).")
    parser.add_argument("--version", action="version", version=f"afow {__version__}")

    args = parser.parse_args(argv)

    if args.serve:
        from afow.web.app import run_server
        run_server(port=args.port)
        return 0

    if args.history:
        _print_history()
        return 0

    # Path is required unless we serve, list history, or undo with a known run_id
    run_path = args.path
    if args.undo and not run_path and args.run_id:
        from afow.history import get_run
        run_data = get_run(args.run_id)
        if run_data:
            run_path = run_data["root_dir"]

    if not run_path:
        parser.error("path is required (unless --serve, --history, or --undo with --run-id is used)")

    try:
        start = time.perf_counter()
        if args.undo:
            summary = undo(run_path, run_id=args.run_id)
            _print_undo(summary, time.perf_counter() - start)
        else:
            # Interactive confirmation flow
            if args.interactive and not args.dry_run:
                preview = organize(run_path, dry_run=True, dedup_policy=args.dedup_policy)
                if preview.moved == 0 and len(preview.duplicates) == 0:
                    print(f"No files to organize in {preview.root}")
                    return 0

                print(f"Organizing {preview.root}:")
                if preview.by_category:
                    for cat, count in sorted(preview.by_category.items()):
                        print(f"  {cat}: {count} file(s)")
                if preview.duplicates:
                    print(f"  Duplicates: {len(preview.duplicates)} file(s) (policy: {args.dedup_policy})")
                if preview.skipped:
                    print(f"  (skipped {preview.skipped} folder(s)/hidden file(s))")

                while True:
                    ans = input("Proceed with organization? [y/N/d (detailed list)]: ").strip().lower()
                    if ans in ("y", "yes"):
                        break
                    elif ans in ("n", "no", ""):
                        print("Cancelled.")
                        return 0
                    elif ans in ("d", "detailed"):
                        print("\nDetailed Plan:")
                        for pm in preview.planned_moves:
                            if pm["type"] == "delete":
                                print(f"  [DELETE] {pm['from']} -> (duplicate content)")
                            elif pm["type"] == "symlink":
                                print(f"  [SYMLINK] {pm['from']} -> {pm['to']} (duplicate link)")
                            else:
                                print(f"  [MOVE] {pm['from']} -> {pm['to']}")
                        print("")
                    else:
                        print("Please enter y, n, or d.")

            summary = organize(run_path, dry_run=args.dry_run, dedup_policy=args.dedup_policy)
            _print_organize(summary, time.perf_counter() - start)
    except (NotADirectoryError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    return 0


def _print_organize(summary: Summary, elapsed: float) -> None:
    verb = "Would move" if summary.dry_run else "Moved"
    print(f"{verb} {summary.moved} file(s) in {summary.root}")
    if summary.by_category:
        width = max(len(c) for c in summary.by_category)
        for category in sorted(summary.by_category, key=lambda k: (-summary.by_category[k], k)):
            print(f"  {category:<{width}}  {summary.by_category[category]}")
    if summary.duplicates:
        print(f"  (handled {len(summary.duplicates)} duplicate(s) via policy)")
    if summary.skipped:
        print(f"  (skipped {summary.skipped} entr(ies): subfolders / hidden / log)")
    print(f"Done in {elapsed * 1000:.1f} ms")
    if not summary.dry_run and summary.moved:
        print("Undo with: afow --undo <dir>")


def _print_undo(summary: Summary, elapsed: float) -> None:
    if summary.moved == 0:
        print(f"Nothing to undo in {summary.root}")
        return
    print(f"Restored {summary.moved} file(s) in {summary.root}")
    if summary.skipped:
        print(f"  (skipped {summary.skipped} missing file(s))")
    print(f"Done in {elapsed * 1000:.1f} ms")


def _print_history() -> None:
    from afow.history import get_history

    runs = get_history()
    if not runs:
        print("No organization history found.")
        return

    print(f"{'ID':<6} {'Timestamp':<25} {'Directory':<40} {'Dry Run':<8}")
    print("-" * 81)
    for run in runs:
        dry_str = "Yes" if run["dry_run"] else "No"
        dir_str = run["root_dir"]
        if len(dir_str) > 37:
            dir_str = dir_str[:34] + "..."
        print(f"{run['id']:<6} {run['timestamp']:<25} {dir_str:<40} {dry_str:<8}")

