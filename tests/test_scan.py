import os
import subprocess
from pathlib import Path

import pytest

from folder_size_tui.app import compute_dir_size, is_link_like


def _make_junction(link: Path, target: Path) -> bool:
    if os.name != "nt":
        return False
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and link.exists()


def test_compute_dir_size_counts_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"abcd")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "b.txt").write_bytes(b"xy")
    result = compute_dir_size(tmp_path, follow_links=False)
    assert result.files == 2
    assert result.bytes_total == 6


def test_compute_dir_size_skips_junction_cycles(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "f.txt").write_bytes(b"hello")
    if os.name == "nt":
        if not _make_junction(real / "back", tmp_path):
            pytest.skip("could not create directory junction")
    else:
        try:
            os.symlink(tmp_path, real / "back", target_is_directory=True)
        except OSError:
            pytest.skip("could not create directory symlink")

    result = compute_dir_size(tmp_path, follow_links=False)
    assert result.files == 1
    assert result.bytes_total == 5


def test_is_link_like_detects_junction_or_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    if os.name == "nt":
        if not _make_junction(link, target):
            pytest.skip("could not create directory junction")
    else:
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError:
            pytest.skip("could not create directory symlink")

    found = False
    with os.scandir(tmp_path) as it:
        for entry in it:
            if entry.name == "link":
                found = True
                assert is_link_like(entry, follow_links=False) is True
                assert is_link_like(entry, follow_links=True) is False
    assert found
