import json

import pytest

from afow.organizer import UNDO_FILENAME, organize


def _make_files(root, names):
    for name in names:
        (root / name).write_text(f"content of {name}", encoding="utf-8")


def test_basic_organize(tmp_path):
    _make_files(tmp_path, ["a.jpg", "b.png", "c.mp4", "d.pdf", "e.py", "weird.qwerty"])
    summary = organize(tmp_path)

    assert summary.moved == 6
    assert summary.by_category == {
        "Images": 2,
        "Videos": 1,
        "Documents": 1,
        "Code": 1,
        "Others": 1,
    }
    assert (tmp_path / "Images" / "a.jpg").is_file()
    assert (tmp_path / "Images" / "b.png").is_file()
    assert (tmp_path / "Videos" / "c.mp4").is_file()
    assert (tmp_path / "Documents" / "d.pdf").is_file()
    assert (tmp_path / "Code" / "e.py").is_file()
    assert (tmp_path / "Others" / "weird.qwerty").is_file()
    assert (tmp_path / UNDO_FILENAME).is_file()


def test_dry_run_does_not_move(tmp_path):
    _make_files(tmp_path, ["a.jpg", "b.pdf"])
    summary = organize(tmp_path, dry_run=True)

    assert summary.dry_run is True
    assert summary.moved == 2
    assert (tmp_path / "a.jpg").is_file()
    assert (tmp_path / "b.pdf").is_file()
    assert not (tmp_path / "Images").exists()
    assert not (tmp_path / UNDO_FILENAME).exists()


def test_subdirectories_are_skipped(tmp_path):
    (tmp_path / "existing_subdir").mkdir()
    (tmp_path / "existing_subdir" / "inner.jpg").write_text("x")
    _make_files(tmp_path, ["top.jpg"])

    summary = organize(tmp_path)
    assert summary.moved == 1
    assert (tmp_path / "Images" / "top.jpg").is_file()
    assert (tmp_path / "existing_subdir" / "inner.jpg").is_file()


def test_collision_against_existing_file(tmp_path):
    images = tmp_path / "Images"
    images.mkdir()
    (images / "photo.jpg").write_text("preexisting")
    _make_files(tmp_path, ["photo.jpg"])

    organize(tmp_path)
    assert (images / "photo.jpg").read_text() == "preexisting"
    assert (images / "photo (1).jpg").is_file()


def test_collision_against_planned_destination(tmp_path):
    images = tmp_path / "Images"
    images.mkdir()
    (images / "photo.jpg").write_text("preexisting")
    # Source has both "photo.jpg" AND "photo (1).jpg"
    _make_files(tmp_path, ["photo.jpg", "photo (1).jpg"])

    organize(tmp_path)
    # All three files must coexist with distinct contents
    assert (images / "photo.jpg").read_text() == "preexisting"
    contents = {
        (images / "photo (1).jpg").read_text(),
        (images / "photo (2).jpg").read_text(),
    }
    assert contents == {"content of photo.jpg", "content of photo (1).jpg"}


def test_undo_log_shape(tmp_path):
    _make_files(tmp_path, ["a.jpg", "b.pdf"])
    organize(tmp_path)
    log = json.loads((tmp_path / UNDO_FILENAME).read_text(encoding="utf-8"))
    assert log["version"] == 1
    assert "created_at" in log
    assert {(m["from"], m["to"]) for m in log["moves"]} == {
        ("a.jpg", "Images/a.jpg"),
        ("b.pdf", "Documents/b.pdf"),
    } or {(m["from"], m["to"]) for m in log["moves"]} == {
        # Windows path separator tolerance
        ("a.jpg", "Images\\a.jpg"),
        ("b.pdf", "Documents\\b.pdf"),
    }


def test_hidden_files_skipped(tmp_path):
    (tmp_path / ".hidden").write_text("secret")
    _make_files(tmp_path, ["visible.txt"])

    organize(tmp_path)
    assert (tmp_path / ".hidden").is_file()
    assert (tmp_path / "Documents" / "visible.txt").is_file()


def test_errors_for_nonexistent_path():
    with pytest.raises((NotADirectoryError, FileNotFoundError)):
        organize("/this/path/does/not/exist/hopefully")
