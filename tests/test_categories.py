from afow.categories import OTHERS, categorize


def test_known_extensions():
    assert categorize("photo.jpg") == "Images"
    assert categorize("clip.mp4") == "Videos"
    assert categorize("song.mp3") == "Audio"
    assert categorize("notes.pdf") == "Documents"
    assert categorize("backup.zip") == "Archives"
    assert categorize("script.py") == "Code"
    assert categorize("installer.exe") == "Executables"


def test_case_insensitive():
    assert categorize("PHOTO.JPG") == "Images"
    assert categorize("Notes.PDF") == "Documents"


def test_unknown_extension_is_others():
    assert categorize("strange.qwerty") == OTHERS


def test_no_extension_is_others():
    assert categorize("README") == OTHERS
    assert categorize("Makefile") == OTHERS


def test_dotfile_extension_treated_as_extension():
    # ".gitignore" -> stem "", ext "gitignore" -> not a known ext -> Others
    assert categorize(".gitignore") == OTHERS
