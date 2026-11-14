# AFOW

A fast, cross-platform file organizer for Linux (Fedora), Windows, and macOS. Point it at a directory and it sorts top-level files into clean category folders.

Does one thing: organize files. That's it.

## Install

```bash
pip install -r requirements.txt
# Or install in editable / user mode:
pip install .
```
## Usage

```bash
afow <directory>                     # organize (or: python -m afow <directory>)
afow ~/Downloads                     # supports tilde and environment variables
afow --xdg-folders ~/Downloads       # use XDG folders (Pictures, Music, etc.)
afow --dry-run ~/Downloads           # preview without moving
afow --interactive ~/Downloads       # confirm plan before moving
afow --undo ~/Downloads              # reverse the last organize
afow --history                       # view history of organize runs
afow --serve                         # launch web UI on 127.0.0.1:5000
afow --serve --port 8080             # custom port
```

### Fedora & Linux Desktop Integration

```bash
afow --install-desktop               # add to GNOME/KDE Application grid
afow --install-nautilus              # right-click folder in GNOME Files -> "Organize with AFOW"
afow --install-service               # enable systemd user background service
```

## How it works

- Walks the top level of the target directory (subfolders are left alone).
- Categorizes each file: **Images, Videos, Audio, Documents, Archives, Code, Executables, Others**.
  - Recognizes multi-OS packages (`.rpm`, `.flatpak`, `.appimage`, `.deb`, `.exe`, `.dmg`).
  - Recognizes modern archives (Zstandard `.zst`, `.tar.zst`, `.cpio`, `.iso`, `.zip`, `.tar.gz`).
  - Recognizes Linux desktop formats (`.desktop`, `.odp`, `.ods`, `.odt`, `.toml`, `.spec`).
  - Detects extensionless compiled Linux binaries (ELF magic) and shebang scripts.
- Moves files into matching subfolders. On the same filesystem or Btrfs subvolume, this is near-instant.
- Fully compliant with XDG Base Directory specification on Linux (`~/.local/share/afow/history.db`).
- Writes `.afow_undo.json` and records to centralized SQLite so `--undo` can put everything back.
- On filename collision, the incoming file is auto-renamed to `name (1).ext`. Nothing is ever overwritten.

## Web UI

`afow --serve` opens a lightweight local UI. Automatically detects your OS, suggests standard directories (Downloads, Documents, Desktop), and lets you Preview, Organize, and Undo.

## Tests

Run the zero-dependency test runner on any system:
```bash
python3 tests/run_tests.py
# Or with pytest:
pytest
```
