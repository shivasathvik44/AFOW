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
    parser.add_argument(
        "--xdg-folders",
        action="store_true",
        help="Use XDG standard folder names (e.g. Pictures instead of Images, Music instead of Audio).",
    )
    parser.add_argument("--serve", action="store_true", help="Launch the web UI.")
    parser.add_argument("--port", type=int, default=5000, help="Port for --serve (default 5000).")
    parser.add_argument(
        "--install-desktop", action="store_true", help="Install .desktop launcher for GNOME/KDE."
    )
    parser.add_argument(
        "--install-nautilus", action="store_true", help="Install right-click script for GNOME Files (Nautilus)."
    )
    parser.add_argument(
        "--install-service", action="store_true", help="Install systemd user service unit for background web UI."
    )
    parser.add_argument(
        "--set-default",
        metavar="DIR",
        help="Set the default directory to organize (saved to config).",
    )
    parser.add_argument(
        "--get-default",
        action="store_true",
        help="Display the currently configured default directory.",
    )
    parser.add_argument("--version", action="version", version=f"afow {__version__}")

    args = parser.parse_args(argv)

    if args.set_default:
        from afow.config import set_default_directory
        resolved = set_default_directory(args.set_default)
        print(f"Default directory set to: {resolved}")
        return 0

    if args.get_default:
        from afow.config import get_default_directory
        print(f"Default directory: {get_default_directory()}")
        return 0

    if args.install_desktop:
        return _install_desktop()

    if args.install_nautilus:
        return _install_nautilus()

    if args.install_service:
        return _install_service(port=args.port)

    if args.serve:
        from afow.web.app import run_server
        run_server(port=args.port)
        return 0

    if args.history:
        _print_history()
        return 0

    # Path resolution: use explicit argument, run_data, or configured default
    run_path = args.path
    if run_path:
        run_path = run_path.strip().strip("'\"")

    if args.undo and not run_path and args.run_id:
        from afow.history import get_run
        run_data = get_run(args.run_id)
        if run_data:
            run_path = run_data["root_dir"]

    if not run_path:
        from afow.config import get_default_directory
        default_dir = get_default_directory()
        if default_dir and default_dir.is_dir():
            run_path = str(default_dir)
            print(f"Using default directory: {run_path}")
        else:
            parser.error("path is required (unless --serve, --history, or --undo with --run-id is used)")

    try:
        start = time.perf_counter()
        if args.undo:
            summary = undo(run_path, run_id=args.run_id)
            _print_undo(summary, time.perf_counter() - start)
        else:
            # Interactive confirmation flow
            if args.interactive and not args.dry_run:
                preview = organize(
                    run_path,
                    dry_run=True,
                    dedup_policy=args.dedup_policy,
                    use_xdg_folders=args.xdg_folders,
                )
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

            summary = organize(
                run_path,
                dry_run=args.dry_run,
                dedup_policy=args.dedup_policy,
                use_xdg_folders=args.xdg_folders,
            )
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


def _install_desktop() -> int:
    """Install .desktop launcher for GNOME/KDE desktop environments."""
    apps_dir = Path.home() / ".local" / "share" / "applications"
    try:
        apps_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating applications directory: {e}", file=sys.stderr)
        return 1

    desktop_file = apps_dir / "afow.desktop"
    content = """[Desktop Entry]
Name=AFOW File Organizer
GenericName=File Organizer
Comment=Organize files into clean category folders
Exec=python3 -m afow --serve
Icon=system-file-manager
Terminal=false
Type=Application
Categories=Utility;FileManager;
StartupNotify=true
"""
    try:
        desktop_file.write_text(content, encoding="utf-8")
        desktop_file.chmod(0o755)
        print(f"Installed desktop entry to {desktop_file}")
        import subprocess
        subprocess.run(["update-desktop-database", str(apps_dir)], capture_output=True)
        return 0
    except OSError as e:
        print(f"Error writing desktop file: {e}", file=sys.stderr)
        return 1


def _install_nautilus() -> int:
    """Install right-click script for GNOME Files (Nautilus)."""
    scripts_dir = Path.home() / ".local" / "share" / "nautilus" / "scripts"
    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating Nautilus scripts directory: {e}", file=sys.stderr)
        return 1

    script_file = scripts_dir / "Organize with AFOW"
    content = """#!/bin/bash
# Nautilus script to organize selected directories with AFOW
for target in "$@"; do
    if [ -d "$target" ]; then
        python3 -m afow "$target"
    fi
done
"""
    try:
        script_file.write_text(content, encoding="utf-8")
        script_file.chmod(0o755)
        print(f"Installed Nautilus script to {script_file}")
        print("Usage: Right-click any folder in GNOME Files (Nautilus) -> Scripts -> 'Organize with AFOW'.")
        return 0
    except OSError as e:
        print(f"Error writing Nautilus script: {e}", file=sys.stderr)
        return 1


def _install_service(port: int = 5000) -> int:
    """Install systemd user service unit for background web UI."""
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    try:
        systemd_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error creating systemd directory: {e}", file=sys.stderr)
        return 1

    service_file = systemd_dir / "afow.service"
    content = f"""[Unit]
Description=AFOW File Organizer Web Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m afow --serve --port {port}
Restart=on-failure

[Install]
WantedBy=default.target
"""
    try:
        service_file.write_text(content, encoding="utf-8")
        print(f"Installed systemd unit to {service_file}")
        print("To enable and start the service on Fedora:")
        print("  systemctl --user daemon-reload")
        print("  systemctl --user enable --now afow.service")
        return 0
    except OSError as e:
        print(f"Error writing systemd service: {e}", file=sys.stderr)
        return 1
