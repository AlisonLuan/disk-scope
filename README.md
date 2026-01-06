# folder-size-tui

A small terminal-based two-pane folder/file size explorer (TUI).

- Left pane: immediate subfolders sorted by *recursive* size.
- Right pane: immediate files in the current folder sorted by size.

## Screenshots

*(Placeholder for screenshots — add images here later.)*

## Install

With pip (system or venv):

- Install runtime (Windows only requires `windows-curses`):

```bash
pip install -r requirements.txt
```

- To install the package locally for development:

```bash
pip install -e .
```

## Usage

Run the CLI command:

```bash
folder-size-tui /c
folder-size-tui "C:\\"  # PowerShell
```

Flags:

- `--workers`  - number of worker threads for folder scanning (default: 8)
- `--follow-links` - follow symlinks/junctions

You can also run as a module:

```bash
python -m folder_size_tui /c
```

### Windows notes

- On Windows, the `windows-curses` package is required for the curses-based TUI.
- In Git Bash / mintty, curses-based programs may not function correctly. Use Windows Terminal or PowerShell instead.
- If you're in Git Bash and need to run here, you can use:

```bash
winpty folder-size-tui /c
```

## Controls

- Up / Down : move selection
- Enter / Right : drill into selected folder
- Esc / Backspace / Left / u : go back
- r : rescan current folder
- d : details popup for selected folder
- q : quit

## Development

Run tests:

```bash
pip install -r requirements-dev.txt
pytest
```

## Contributing

See `CONTRIBUTING.md`.
