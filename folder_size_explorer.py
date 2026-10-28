#!/usr/bin/env python3
"""Backward-compatible shim to the package entrypoint.

This file delegates to the packaged `folder_size_tui` entrypoint so users can still
run `python folder_size_explorer.py` if they prefer.
"""
from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
_src = _root / "src"
_venv_python = (
    _root / ".venv" / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else _root / ".venv" / "bin" / "python"
)

# Prefer the project venv (Python 3.14 + windows-curses) over a system interpreter
# that cannot import the package or lacks a curses wheel (e.g. Python 3.15).
if _venv_python.is_file() and Path(sys.executable).resolve() != _venv_python.resolve():
    # Ignore Ctrl+C in this wrapper process; the venv child handles it and
    # exits cleanly. Otherwise both processes print a KeyboardInterrupt traceback.
    prev_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        raise SystemExit(subprocess.call([str(_venv_python), str(Path(__file__).resolve()), *sys.argv[1:]]))
    except KeyboardInterrupt:
        raise SystemExit(0)
    finally:
        signal.signal(signal.SIGINT, prev_handler)

# Allow `python folder_size_explorer.py` without a prior `pip install -e .`.
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from folder_size_tui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
