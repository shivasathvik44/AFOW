"""Configuration management for AFOW."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def get_config_dir() -> Path:
    """Return the configuration directory following XDG/OS standards."""
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        cfg_dir = Path(base) / "afow" if base else Path.home() / "AppData" / "Roaming" / "afow"
    elif sys.platform == "darwin":
        cfg_dir = Path.home() / "Library" / "Application Support" / "afow"
    else:
        xdg_config = os.getenv("XDG_CONFIG_HOME")
        cfg_dir = Path(xdg_config) / "afow" if xdg_config else Path.home() / ".config" / "afow"

    try:
        cfg_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        for fallback in (Path("/tmp") / "afow", Path.home()):
            try:
                fallback.mkdir(parents=True, exist_ok=True)
                cfg_dir = fallback
                break
            except OSError:
                continue

    return cfg_dir


def get_config_file() -> Path:
    return get_config_dir() / "config.json"


def load_config() -> dict:
    cfg_file = get_config_file()
    if cfg_file.exists():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_config(cfg: dict) -> None:
    cfg_file = get_config_file()
    try:
        cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_default_directory() -> Path:
    """Return the configured default directory, or standard Downloads folder."""
    cfg = load_config()
    if "default_directory" in cfg:
        p = Path(os.path.expandvars(cfg["default_directory"])).expanduser().resolve()
        if p.is_dir():
            return p

    # Fallback to standard Downloads folder
    home = Path.home()
    downloads = home / "Downloads"
    if downloads.is_dir():
        return downloads
    return home


def set_default_directory(path: str | os.PathLike) -> Path:
    """Save the default directory to configuration."""
    resolved = Path(os.path.expandvars(str(path))).expanduser().resolve()
    if not resolved.is_dir():
        raise NotADirectoryError(f"Not a directory: {resolved}")
    cfg = load_config()
    cfg["default_directory"] = str(resolved)
    save_config(cfg)
    return resolved
