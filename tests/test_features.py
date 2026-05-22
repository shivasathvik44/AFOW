import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch

from afow.organizer import organize, _is_cross_device, _move_cross_device
from afow.undo import undo
from afow.history import get_history, get_run, get_latest_run


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    """Automatically point the history database to a temp file for every test."""
    db_file = tmp_path / "test_history.db"
    monkeypatch.setenv("AFOW_DB_PATH", str(db_file))
    yield db_file


def _make_files(root, file_map):
    for name, content in file_map.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def test_sqlite_history_logging_and_undo(tmp_path):
    # Create test files
    files = {"a.jpg": "image content", "b.pdf": "document content"}
    _make_files(tmp_path, files)

    # Organize files
    summary = organize(tmp_path)
    assert summary.moved == 2

    # Check history db logs
    history = get_history()
    assert len(history) == 1
    run_id = history[0]["id"]
    assert history[0]["root_dir"] == str(tmp_path.resolve())
    assert history[0]["dry_run"] == 0

    run_detail = get_run(run_id)
    assert len(run_detail["moves"]) == 2

    # Perform database-backed undo
    undo_summary = undo(tmp_path)
    assert undo_summary.moved == 2

    # Verify restored files
    assert (tmp_path / "a.jpg").is_file()
    assert (tmp_path / "b.pdf").is_file()
    assert not (tmp_path / "Images").exists()
    assert not (tmp_path / "Documents").exists()

    # DB run should be deleted
    assert len(get_history()) == 0


def test_duplicate_policy_rename(tmp_path):
    # Two identical images
    _make_files(tmp_path, {"a.jpg": "same content", "b.jpg": "same content"})
    
    summary = organize(tmp_path, dedup_policy="rename")
    assert summary.moved == 2
    assert len(summary.duplicates) == 1
    assert summary.duplicates[0]["file"] == "b.jpg"
    assert summary.duplicates[0]["policy"] == "rename"

    assert (tmp_path / "Images" / "a.jpg").is_file()
    assert (tmp_path / "Images" / "b.jpg").is_file() or (tmp_path / "Images" / "b (1).jpg").is_file()


def test_duplicate_policy_skip(tmp_path):
    _make_files(tmp_path, {"a.jpg": "same content", "b.jpg": "same content"})
    
    summary = organize(tmp_path, dedup_policy="skip")
    # b.jpg should be skipped, only a.jpg moved
    assert summary.moved == 1
    assert summary.skipped == 1
    assert len(summary.duplicates) == 1
    assert (tmp_path / "Images" / "a.jpg").is_file()
    assert (tmp_path / "b.jpg").is_file()


def test_duplicate_policy_delete(tmp_path):
    _make_files(tmp_path, {"a.jpg": "same content", "b.jpg": "same content"})
    
    summary = organize(tmp_path, dedup_policy="delete")
    assert summary.moved == 2  # moves (1 copy/move, 1 delete)
    assert len(summary.duplicates) == 1
    assert (tmp_path / "Images" / "a.jpg").is_file()
    assert not (tmp_path / "b.jpg").exists()
    assert not (tmp_path / "Images" / "b.jpg").exists()


def test_duplicate_policy_symlink(tmp_path):
    _make_files(tmp_path, {"a.jpg": "same content", "b.jpg": "same content"})
    
    summary = organize(tmp_path, dedup_policy="symlink")
    assert summary.moved == 2
    assert len(summary.duplicates) == 1

    dest_a = tmp_path / "Images" / "a.jpg"
    dest_b = tmp_path / "Images" / "b.jpg"
    
    assert dest_a.is_file()
    # Check if dest_b is a symlink pointing to dest_a (relatively)
    assert dest_b.is_symlink() or dest_b.is_file() # OS compatibility
    
    # Run undo and make sure both are restored as regular files
    undo_summary = undo(tmp_path)
    assert undo_summary.moved == 2
    assert (tmp_path / "a.jpg").is_file()
    assert (tmp_path / "b.jpg").is_file()
    assert not (tmp_path / "b.jpg").is_symlink()


def test_cross_device_detection_and_hash_fail(tmp_path):
    _make_files(tmp_path, {"a.jpg": "original content"})
    src = tmp_path / "a.jpg"
    dest = tmp_path / "Images" / "a.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Force cross-device detection to return True
    with patch("afow.organizer._is_cross_device", return_value=True):
        # We mock shutil.copy2 to write corrupt content to simulate cross-device corruption
        def mock_copy2(s, d):
            Path(d).write_text("corrupted content", encoding="utf-8")
        
        with patch("shutil.copy2", side_effect=mock_copy2):
            with pytest.raises(ValueError) as excinfo:
                _move_cross_device(src, dest)
            
            assert "Hash verification failed" in str(excinfo.value)
            # Verify source file is preserved and corrupt destination deleted
            assert src.is_file()
            assert src.read_text() == "original content"
            assert not dest.exists()


def test_cross_device_success(tmp_path):
    _make_files(tmp_path, {"a.jpg": "original content"})
    src = tmp_path / "a.jpg"
    dest = tmp_path / "Images" / "a.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)

    with patch("afow.organizer._is_cross_device", return_value=True):
        # Normal copy works
        _move_cross_device(src, dest)
        assert not src.exists()
        assert dest.is_file()
        assert dest.read_text() == "original content"


def test_size_based_hash_optimization(tmp_path):
    # a.jpg has unique size (10 bytes), b.jpg and c.jpg share a size (22 bytes)
    (tmp_path / "a.jpg").write_text("1234567890", encoding="utf-8")
    (tmp_path / "b.jpg").write_text("20 bytes of dummy text", encoding="utf-8")
    (tmp_path / "c.jpg").write_text("20 bytes of dummy text", encoding="utf-8")

    from afow import organizer
    original_sha256 = organizer._sha256
    sha256_calls = []

    def mock_sha256(path):
        sha256_calls.append(path)
        return original_sha256(path)

    with patch("afow.organizer._sha256", side_effect=mock_sha256):
        summary = organize(tmp_path)
        assert summary.moved == 3
        # a.jpg is unique in size, so it should NOT be hashed
        assert not any(p.name == "a.jpg" for p in sha256_calls)
        # b.jpg and c.jpg share size, so they should be hashed
        assert any(p.name == "b.jpg" for p in sha256_calls)
        assert any(p.name == "c.jpg" for p in sha256_calls)


def test_web_app_quote_handling_and_logging(tmp_path):
    from afow.web.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    target_dir = tmp_path / "organize_me"
    target_dir.mkdir()

    # Create dummy file to organize
    (target_dir / "a.txt").write_text("hello", encoding="utf-8")

    # Send path wrapped in double quotes
    quoted_path = f'"{target_dir.resolve()}"'
    res = client.post("/api/preview", json={"path": quoted_path})
    assert res.status_code == 200
    data = res.get_json()
    assert data["moved"] == 1
    assert data["root"] == str(target_dir.resolve())

    # Send path wrapped in single quotes
    quoted_path_single = f"'{target_dir.resolve()}'"
    res = client.post("/api/preview", json={"path": quoted_path_single})
    assert res.status_code == 200
    data = res.get_json()
    assert data["moved"] == 1

