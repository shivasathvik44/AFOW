"""Fixed extension-based category map.

Single source of truth: CATEGORIES.  EXT_TO_CATEGORY is built once at import
time so per-file lookups are O(1).
"""

from __future__ import annotations

import os
from pathlib import Path

OTHERS = "Others"

CATEGORIES: dict[str, tuple[str, ...]] = {
    "Images": (
        "jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "heic", "tiff", "ico",
        "avif", "jxl", "raw", "cr2", "nef",
    ),
    "Videos": (
        "mp4", "mov", "avi", "mkv", "webm", "flv", "wmv", "m4v",
    ),
    "Audio": (
        "mp3", "wav", "flac", "aac", "ogg", "m4a", "opus",
    ),
    "Documents": (
        "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
        "txt", "rtf", "md", "csv", "odt", "ods", "odp", "odg",
        "epub", "tex", "rst", "log",
    ),
    "Archives": (
        "zip", "tar", "gz", "rar", "7z", "bz2", "xz", "tgz",
        "zst", "zstd", "tzst", "txz", "tbz2", "cpio", "iso", "img", "qcow2", "lzma", "lz4",
    ),
    "Code": (
        "py", "js", "ts", "jsx", "tsx", "html", "css", "java",
        "c", "cpp", "h", "hpp", "go", "rs", "rb", "php", "sh", "ps1",
        "bash", "zsh", "fish", "ksh", "lua", "r",
        "json", "yml", "yaml", "xml", "sql", "toml", "ini", "conf", "cfg", "env",
        "spec", "diff", "patch",
    ),
    "Executables": (
        "exe", "msi", "dmg", "deb", "rpm", "srpm", "appimage", "bat", "cmd", "com",
        "flatpak", "flatpakref", "flatpakrepo", "run", "bin", "desktop", "pkg",
    ),
}

EXT_TO_CATEGORY: dict[str, str] = {
    ext: category
    for category, exts in CATEGORIES.items()
    for ext in exts
}

ALL_CATEGORIES: tuple[str, ...] = (*CATEGORIES.keys(), OTHERS)

# XDG Standard User Directory mapping
XDG_CATEGORY_MAP: dict[str, str] = {
    "Images": "Pictures",
    "Audio": "Music",
}


def categorize(filename: str) -> str:
    """Return the category for a filename based on its extension."""
    _, _, ext = filename.rpartition(".")
    if not ext or ext == filename:
        return OTHERS
    return EXT_TO_CATEGORY.get(ext.lower(), OTHERS)


def categorize_file(entry_or_path: os.DirEntry | str | Path) -> str:
    """Categorize a file using its extension, or header inspection for extensionless files.

    On Linux / POSIX systems, standalone binaries (ELF executables) and script files
    often have no extension. If extension-based categorization yields 'Others',
    inspect the first few bytes for ELF magic (\x7fELF) or shebang (#!).
    """
    if isinstance(entry_or_path, os.DirEntry):
        filename = entry_or_path.name
        file_path = Path(entry_or_path.path)
    else:
        file_path = Path(entry_or_path)
        filename = file_path.name

    cat = categorize(filename)
    if cat != OTHERS:
        return cat

    # Inspect extensionless or unrecognized files on disk
    try:
        if file_path.is_file():
            with open(file_path, "rb") as f:
                header = f.read(4)

            # Linux / POSIX ELF executable or library
            if header == b"\x7fELF":
                return "Executables"

            # Shebang script (e.g. #!/bin/bash, #!/usr/bin/env python)
            if header.startswith(b"#!"):
                return "Code"
    except OSError:
        pass

    return OTHERS
