from afow.organizer import UNDO_FILENAME, organize
from afow.undo import undo


def _make_files(root, names):
    for name in names:
        (root / name).write_text(f"content of {name}", encoding="utf-8")


def test_undo_restores_original_layout(tmp_path):
    files = ["a.jpg", "b.png", "c.mp4", "d.pdf"]
    _make_files(tmp_path, files)

    organize(tmp_path)
    summary = undo(tmp_path)

    assert summary.moved == 4
    for name in files:
        assert (tmp_path / name).is_file()
    assert not (tmp_path / "Images").exists()
    assert not (tmp_path / "Videos").exists()
    assert not (tmp_path / "Documents").exists()
    assert not (tmp_path / UNDO_FILENAME).exists()


def test_undo_with_no_log_is_noop(tmp_path):
    _make_files(tmp_path, ["a.jpg"])
    summary = undo(tmp_path)
    assert summary.moved == 0
    assert (tmp_path / "a.jpg").is_file()


def test_undo_preserves_unrelated_subfolders(tmp_path):
    (tmp_path / "keep_me").mkdir()
    (tmp_path / "keep_me" / "x.txt").write_text("x")
    _make_files(tmp_path, ["top.jpg"])

    organize(tmp_path)
    undo(tmp_path)

    assert (tmp_path / "top.jpg").is_file()
    assert (tmp_path / "keep_me" / "x.txt").is_file()
