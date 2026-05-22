"""Fixed extension-based category map.

Single source of truth: CATEGORIES.  EXT_TO_CATEGORY is built once at import
time so per-file lookups are O(1).
"""

from __future__ import annotations

OTHERS = "Others"

CATEGORIES: dict[str, tuple[str, ...]] = {
    "Images": (
        "jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "heic", "tiff", "ico",
    ),
    "Videos": (
        "mp4", "mov", "avi", "mkv", "webm", "flv", "wmv", "m4v",
    ),
    "Audio": (
        "mp3", "wav", "flac", "aac", "ogg", "m4a", "opus",
    ),
    "Documents": (
        "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
        "txt", "rtf", "md", "csv", "odt", "ods",
    ),
    "Archives": (
        "zip", "tar", "gz", "rar", "7z", "bz2", "xz", "tgz",
    ),
    "Code": (
        "py", "js", "ts", "jsx", "tsx", "html", "css", "java",
        "c", "cpp", "h", "hpp", "go", "rs", "rb", "php", "sh", "ps1",
        "json", "yml", "yaml", "xml", "sql",
    ),
    "Executables": (
        "exe", "msi", "dmg", "deb", "rpm", "appimage", "bat",
    ),
}

EXT_TO_CATEGORY: dict[str, str] = {
    ext: category
    for category, exts in CATEGORIES.items()
    for ext in exts
}

ALL_CATEGORIES: tuple[str, ...] = (*CATEGORIES.keys(), OTHERS)


def categorize(filename: str) -> str:
    """Return the category for a filename based on its extension."""
    _, _, ext = filename.rpartition(".")
    if not ext or ext == filename:
        return OTHERS
    return EXT_TO_CATEGORY.get(ext.lower(), OTHERS)
