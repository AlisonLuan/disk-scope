import os
from folder_size_tui import human_size, msys_to_windows_path


def test_human_size_bytes():
    assert human_size(0) == "0 B"
    assert human_size(512) == "512 B"
    assert human_size(1024) == "1.00 KiB"
    assert human_size(1024 * 1024) == "1.00 MiB"


def test_msys_to_windows_path_behavior():
    inp = "/c/Users/Test"
    out = msys_to_windows_path(inp)
    if os.name == "nt":
        assert out.startswith("C:") or out.startswith("C:\\")
        # Check drive and path conversion
        assert out.upper().startswith("C:")
    else:
        # Non-Windows should be unchanged
        assert out == inp
