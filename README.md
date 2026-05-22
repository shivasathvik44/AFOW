# afow

A small, fast file organizer. Point it at a directory and it sorts the top-level files into clean category folders.

Does one thing: organize files. That's it.

## Install

```
pip install -r requirements.txt
```

## Usage

```
python -m afow <directory>             # organize
python -m afow --dry-run <directory>   # preview without moving
python -m afow --undo <directory>      # reverse the last organize
python -m afow --serve                 # launch the web UI on 127.0.0.1:5000
python -m afow --serve --port 8080     # custom port
```

## How it works

- Walks the top level of the target directory (subfolders are left alone).
- Categorizes each file by extension: **Images, Videos, Audio, Documents, Archives, Code, Executables, Others**.
- Moves files into matching subfolders. On the same volume, this is a near-instant rename.
- Writes `.afow_undo.json` next to the moved files so `--undo` can put everything back.
- On filename collision, the incoming file is auto-renamed to `name (1).ext`, `name (2).ext`, etc. Nothing is ever overwritten.

## Web UI

`python -m afow --serve` opens a tiny local UI. Paste a folder path, hit **Preview** to see what would move, **Organize** to do it, **Undo** to reverse. Localhost only.

## Tests

```
pytest
```
