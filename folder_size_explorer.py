#!/usr/bin/env python3
"""Backward-compatible shim to the package entrypoint.

This file delegates to the packaged `folder_size_tui` entrypoint so users can still
run `python folder_size_explorer.py` if they prefer.
"""
from __future__ import annotations

from folder_size_tui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
