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


def test_linux_and_multi_os_formats():
    # Fedora / Linux packages
    assert categorize("fedora-release.rpm") == "Executables"
    assert categorize("package.srpm") == "Executables"
    assert categorize("org.gnome.App.flatpak") == "Executables"
    assert categorize("org.gnome.App.flatpakref") == "Executables"
    assert categorize("discord.AppImage") == "Executables"
    assert categorize("app.desktop") == "Executables"

    # Linux / Fedora archives (Zstandard, cpio, iso)
    assert categorize("archive.tar.zst") == "Archives"
    assert categorize("payload.cpio") == "Archives"
    assert categorize("Fedora-Workstation-41.iso") == "Archives"

    # Linux shell & modern configuration
    assert categorize("script.bash") == "Code"
    assert categorize("setup.fish") == "Code"
    assert categorize("setup.zsh") == "Code"
    assert categorize("Cargo.toml") == "Code"
    assert categorize("package.spec") == "Code"
    assert categorize("app.env") == "Code"

    # Linux / LibreOffice documents
    assert categorize("presentation.odp") == "Documents"
    assert categorize("drawing.odg") == "Documents"
    assert categorize("book.epub") == "Documents"


def test_categorize_file_elf_and_shebang(tmp_path):
    from afow.categories import categorize_file

    # Known extension works directly
    p_rpm = tmp_path / "test.rpm"
    p_rpm.write_bytes(b"dummy")
    assert categorize_file(p_rpm) == "Executables"

    # Extensionless ELF binary
    p_elf = tmp_path / "my_elf_tool"
    p_elf.write_bytes(b"\x7fELF\x02\x01\x01\x00extra data")
    assert categorize_file(p_elf) == "Executables"

    # Extensionless Shebang script
    p_sh = tmp_path / "myscript"
    p_sh.write_bytes(b"#!/bin/bash\necho 'hello'\n")
    assert categorize_file(p_sh) == "Code"

    # Normal text file without extension
    p_txt = tmp_path / "LICENSE"
    p_txt.write_bytes(b"MIT License Copyright...")
    assert categorize_file(p_txt) == OTHERS
