# Changelog

## 0.1.2 - 2026-10-28
- Treat Ctrl+C as a clean quit (no KeyboardInterrupt traceback)

## 0.1.1 - 2026-10-28
- Make `python folder_size_explorer.py` work without `pip install -e .` by putting `src/` on `sys.path`
- If a project `.venv` exists, the shim re-executes with that interpreter so a system Python (including 3.15, which has no `windows-curses` wheel) can still launch the TUI

## 0.1.0 - 2026-01-06
- Initial packaging and project scaffolding
- Move existing `folder_size_explorer.py` code into package `folder_size_tui`
- Add CLI entry point `folder-size-tui`
- Add tests and CI

**Release:** packaged and tagged as `v0.1.0`
