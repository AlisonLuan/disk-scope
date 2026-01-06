#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


# ---------------------------
# Core scanning logic
# ---------------------------

@dataclass(frozen=True)
class SizeResult:
    path: Path
    bytes_total: int
    files: int
    dirs: int
    errors: int


def human_size(num_bytes: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    n = float(num_bytes)
    for u in units:
        if n < 1024.0 or u == units[-1]:
            if u == "B":
                return f"{int(n)} {u}"
            return f"{n:.2f} {u}"
        n /= 1024.0
    return f"{num_bytes} B"


def iter_subdirs(base: Path, follow_links: bool) -> List[Path]:
    subdirs: List[Path] = []
    try:
        with os.scandir(base) as it:
            for e in it:
                try:
                    if not e.is_dir(follow_symlinks=follow_links):
                        continue
                    if (not follow_links) and e.is_symlink():
                        continue
                    subdirs.append(Path(e.path))
                except OSError:
                    continue
    except OSError:
        return []
    return subdirs


def compute_dir_size(root: Path, follow_links: bool) -> SizeResult:
    total = 0
    files = 0
    dirs = 0
    errors = 0

    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for e in it:
                    try:
                        if (not follow_links) and e.is_symlink():
                            continue

                        if e.is_dir(follow_symlinks=follow_links):
                            dirs += 1
                            stack.append(Path(e.path))
                        else:
                            st = e.stat(follow_symlinks=follow_links)
                            total += int(st.st_size)
                            files += 1
                    except OSError:
                        errors += 1
                        continue
        except OSError:
            errors += 1
            continue

    return SizeResult(path=root, bytes_total=total, files=files, dirs=dirs, errors=errors)


def compute_sizes_parallel(paths: Iterable[Path], follow_links: bool, workers: int) -> List[SizeResult]:
    paths_list = list(paths)
    if not paths_list:
        return []

    results: List[SizeResult] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(compute_dir_size, p, follow_links): p for p in paths_list}
        for fut in as_completed(futs):
            results.append(fut.result())

    return results


def scan_children_dirs(base: Path, follow_links: bool, workers: int) -> List[SizeResult]:
    subdirs = iter_subdirs(base, follow_links)
    results = compute_sizes_parallel(subdirs, follow_links, workers)
    results.sort(key=lambda r: r.bytes_total, reverse=True)
    return results


def scan_files_nonrecursive(base: Path, follow_links: bool) -> Tuple[List[Tuple[int, str]], int]:
    """
    Returns: ([(size_bytes, filename), ...] sorted desc, errors_count)
    """
    files: List[Tuple[int, str]] = []
    errors = 0
    try:
        with os.scandir(base) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=follow_links):
                        continue
                    if (not follow_links) and e.is_symlink():
                        continue
                    st = e.stat(follow_symlinks=follow_links)
                    files.append((int(st.st_size), e.name))
                except OSError:
                    errors += 1
                    continue
    except OSError:
        errors += 1

    files.sort(key=lambda x: x[0], reverse=True)
    return files, errors


def msys_to_windows_path(s: str) -> str:
    """
    Allow Git Bash style paths like /c/Users/Name to work on Windows.
    """
    if os.name == "nt" and len(s) >= 2 and s[0] == "/" and s[1].isalpha() and (len(s) == 2 or s[2] == "/"):
        drive = s[1].upper() + ":\\"
        rest = s[2:].lstrip("/").replace("/", "\\")
        return drive + rest
    return s


# ---------------------------
# Curses TUI
# ---------------------------

def run_tui(start_path: Path, follow_links: bool, workers: int) -> int:
    try:
        import curses
    except Exception:
        print(
            "This interactive arrow-key UI requires 'curses'.\n"
            "On Windows, install it with:\n"
            "  python -m pip install --user windows-curses\n"
            "\nRun in Windows Terminal / PowerShell (recommended), or in Git Bash using:\n"
            "  winpty python ./folder_size_explorer.py /c\n",
            file=sys.stderr,
        )
        return 2

    dir_cache: Dict[Path, List[SizeResult]] = {}
    file_cache: Dict[Path, Tuple[List[Tuple[int, str]], int]] = {}  # path -> (files, errors)
    selection: Dict[Path, int] = {}
    offset: Dict[Path, int] = {}
    stack: List[Path] = [start_path]

    def show_message(stdscr, msg: str) -> None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        stdscr.addnstr(0, 0, msg[: max(0, w - 1)], w - 1)
        stdscr.addnstr(2, 0, "Please wait...", w - 1)
        stdscr.refresh()

    def get_dir_listing(path: Path, force: bool, stdscr) -> List[SizeResult]:
        if (not force) and path in dir_cache:
            return dir_cache[path]
        show_message(stdscr, f"Scanning folder sizes: {path} ...")
        listing = scan_children_dirs(path, follow_links, workers)
        dir_cache[path] = listing
        selection.setdefault(path, 0)
        offset.setdefault(path, 0)
        return listing

    def get_file_listing(path: Path, force: bool, stdscr) -> Tuple[List[Tuple[int, str]], int]:
        if (not force) and path in file_cache:
            return file_cache[path]
        # Do not show a blocking scan message for files; it is usually quick.
        files, errs = scan_files_nonrecursive(path, follow_links)
        file_cache[path] = (files, errs)
        return files, errs

    def clamp(n: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, n))

    def ensure_visible(sel: int, off: int, visible: int) -> int:
        if sel < off:
            return sel
        if sel >= off + visible:
            return sel - visible + 1
        return off

    def render(stdscr) -> None:
        import curses

        stdscr.erase()
        cur = stack[-1]

        listing = get_dir_listing(cur, force=False, stdscr=stdscr)
        files, file_errs = get_file_listing(cur, force=False, stdscr=stdscr)

        h, w = stdscr.getmaxyx()

        # Layout: two panes split by a vertical separator.
        # Keep it simple: ~55% left, ~45% right.
        left_w = max(35, int(w * 0.55))
        left_w = min(left_w, w - 20) if w > 60 else w // 2
        sep_x = min(left_w, w - 2)
        right_x = sep_x + 1
        right_w = max(0, w - right_x)

        header_lines = 4
        footer_lines = 2
        visible = max(1, h - header_lines - footer_lines)

        sel = selection.get(cur, 0)
        sel = clamp(sel, 0, max(0, len(listing) - 1))
        selection[cur] = sel

        off = offset.get(cur, 0)
        off = clamp(off, 0, max(0, len(listing) - 1))
        off = ensure_visible(sel, off, visible)
        offset[cur] = off

        # Global header (full width)
        stdscr.addnstr(0, 0, f"Current: {cur}", w - 1)
        stdscr.addnstr(
            1, 0,
            "Up/Down=move  Enter=drill in  Esc/Backspace=back  r=rescan  d=details  q=quit",
            w - 1,
        )
        stdscr.addnstr(
            2, 0,
            "Folders (left) are recursive sizes; Files (right) are immediate files in current folder.",
            w - 1,
        )
        stdscr.addnstr(3, 0, "-" * (w - 1), w - 1)

        # Draw vertical separator
        for y in range(4, h - footer_lines):
            if 0 <= sep_x < w:
                try:
                    stdscr.addch(y, sep_x, ord("|"))
                except curses.error:
                    pass

        # Pane headers (line 4)
        y0 = 4
        # Left header
        if left_w > 0:
            left_title = "FOLDERS (sorted by size)"
            stdscr.addnstr(y0, 0, left_title[: max(0, left_w - 1)], max(0, left_w - 1))
        # Right header
        if right_w > 0:
            right_title = "FILES (sorted by size)"
            stdscr.addnstr(y0, right_x, right_title[: max(0, right_w - 1)], max(0, right_w - 1))

        # Column headers (line 5)
        y1 = 5
        # Left columns
        if left_w > 0:
            # ID, SIZE, ERR, NAME
            id_w = 4
            size_w = 12
            err_w = 5
            fixed = id_w + 1 + size_w + 1 + err_w + 2
            name_w = max(5, left_w - fixed - 1)

            left_cols = f"{'ID':<4} {'SIZE':>{size_w}} {'ERR':>{err_w}}  NAME"
            stdscr.addnstr(y1, 0, left_cols[: max(0, left_w - 1)], max(0, left_w - 1))
        # Right columns
        if right_w > 0:
            r_size_w = 12
            r_fixed = r_size_w + 2
            r_name_w = max(5, right_w - r_fixed - 1)
            right_cols = f"{'SIZE':>{r_size_w}}  NAME"
            stdscr.addnstr(y1, right_x, right_cols[: max(0, right_w - 1)], max(0, right_w - 1))

        # Rows start (line 6)
        row_start = 6

        # Render rows for both panes
        for i in range(visible):
            y = row_start + i
            if y >= h - footer_lines:
                break

            # Left pane row (folders)
            idx = off + i
            if left_w > 0:
                if idx < len(listing):
                    r = listing[idx]
                    name = r.path.name or str(r.path)
                    if len(name) > name_w:
                        name = name[: max(0, name_w - 1)] + "…"

                    line = f"{idx+1:<4} {human_size(r.bytes_total):>{size_w}} {r.errors:>{err_w}}  {name}"
                    line = line[: max(0, left_w - 1)]

                    if idx == sel:
                        stdscr.attron(curses.A_REVERSE)
                        stdscr.addnstr(y, 0, line, max(0, left_w - 1))
                        stdscr.attroff(curses.A_REVERSE)
                    else:
                        stdscr.addnstr(y, 0, line, max(0, left_w - 1))
                else:
                    # Clear leftover space
                    stdscr.addnstr(y, 0, " " * max(0, left_w - 1), max(0, left_w - 1))

            # Right pane row (files in current folder)
            if right_w > 0:
                if i < len(files):
                    fsz, fname = files[i]
                    if len(fname) > r_name_w:
                        fname = fname[: max(0, r_name_w - 1)] + "…"
                    rline = f"{human_size(fsz):>{r_size_w}}  {fname}"
                    rline = rline[: max(0, right_w - 1)]
                    stdscr.addnstr(y, right_x, rline, max(0, right_w - 1))
                else:
                    stdscr.addnstr(y, right_x, " " * max(0, right_w - 1), max(0, right_w - 1))

        # Footer
        stdscr.addnstr(h - 2, 0, "-" * (w - 1), w - 1)

        folder_count = len(listing)
        file_count = len(files)
        sel_display = (sel + 1) if folder_count else 0

        footer = (
            f"Folders: {folder_count}  Selected: {sel_display}  "
            f"Files: {file_count}  FileErr: {file_errs}  "
            f"Path depth: {len(stack)}"
        )
        stdscr.addnstr(h - 1, 0, footer[: max(0, w - 1)], w - 1)

        stdscr.refresh()

    def details_popup(stdscr, folder: Path) -> None:
        import curses

        h, w = stdscr.getmaxyx()
        win_h = min(22, max(10, h - 4))
        win_w = min(110, max(40, w - 4))
        top = (h - win_h) // 2
        left = (w - win_w) // 2

        win = curses.newwin(win_h, win_w, top, left)
        win.keypad(True)
        win.border()

        win.addnstr(1, 2, f"Details: {folder}", win_w - 4)
        win.addnstr(2, 2, "Computing...", win_w - 4)
        win.refresh()

        total = compute_dir_size(folder, follow_links)

        # Largest immediate subfolders
        subdirs = iter_subdirs(folder, follow_links)
        sub_sizes = compute_sizes_parallel(subdirs, follow_links, workers)
        sub_sizes.sort(key=lambda r: r.bytes_total, reverse=True)
        sub_sizes = sub_sizes[:10]

        # Largest immediate files
        files, ferrs = scan_files_nonrecursive(folder, follow_links)
        files = files[:10]

        win.erase()
        win.border()
        y = 1
        win.addnstr(y, 2, f"Details: {folder}", win_w - 4)
        y += 1
        win.addnstr(y, 2, f"Total (recursive): {human_size(total.bytes_total)} ({total.bytes_total} bytes)", win_w - 4)
        y += 1
        win.addnstr(y, 2, f"Counts: {total.dirs} dirs, {total.files} files, {total.errors} errors", win_w - 4)
        y += 2

        win.addnstr(y, 2, "Top subfolders (recursive size):", win_w - 4)
        y += 1
        if not sub_sizes:
            win.addnstr(y, 4, "(none)", win_w - 6)
            y += 1
        else:
            for r in sub_sizes:
                if y >= win_h - 6:
                    break
                win.addnstr(y, 4, f"{human_size(r.bytes_total):>12}  {r.path.name}", win_w - 6)
                y += 1

        y += 1
        if y < win_h - 4:
            win.addnstr(y, 2, f"Top files (immediate, fileErr={ferrs}):", win_w - 4)
            y += 1
            if not files:
                win.addnstr(y, 4, "(none)", win_w - 6)
                y += 1
            else:
                for sz, name in files:
                    if y >= win_h - 3:
                        break
                    win.addnstr(y, 4, f"{human_size(sz):>12}  {name}", win_w - 6)
                    y += 1

        win.addnstr(win_h - 2, 2, "Press any key to close", win_w - 4)
        win.refresh()
        win.getch()

    def curses_main(stdscr) -> int:
        import curses

        curses.curs_set(0)
        stdscr.keypad(True)

        # Initial scan
        get_dir_listing(stack[-1], force=True, stdscr=stdscr)
        get_file_listing(stack[-1], force=True, stdscr=stdscr)

        while True:
            render(stdscr)
            ch = stdscr.getch()

            cur = stack[-1]
            listing = get_dir_listing(cur, force=False, stdscr=stdscr)
            sel = selection.get(cur, 0)

            if ch in (ord('q'), ord('Q')):
                return 0

            if ch in (curses.KEY_UP,):
                selection[cur] = clamp(sel - 1, 0, max(0, len(listing) - 1))

            elif ch in (curses.KEY_DOWN,):
                selection[cur] = clamp(sel + 1, 0, max(0, len(listing) - 1))

            elif ch in (curses.KEY_NPAGE,):  # Page Down
                h, _ = stdscr.getmaxyx()
                visible = max(1, h - 4 - 2 - 2)  # approx
                selection[cur] = clamp(sel + visible, 0, max(0, len(listing) - 1))

            elif ch in (curses.KEY_PPAGE,):  # Page Up
                h, _ = stdscr.getmaxyx()
                visible = max(1, h - 4 - 2 - 2)
                selection[cur] = clamp(sel - visible, 0, max(0, len(listing) - 1))

            elif ch in (10, 13, curses.KEY_ENTER, curses.KEY_RIGHT):  # Enter / Right
                if not listing:
                    continue
                chosen = listing[selection[cur]].path
                if chosen.is_dir():
                    stack.append(chosen)
                    # Force scan on enter (folders + files)
                    get_dir_listing(chosen, force=True, stdscr=stdscr)
                    file_cache.pop(chosen, None)
                    get_file_listing(chosen, force=True, stdscr=stdscr)

            elif ch in (27, curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, 8, ord('u'), ord('U')):  # Esc / Left / Backspace / u
                if len(stack) > 1:
                    stack.pop()

            elif ch in (ord('r'), ord('R')):
                # Force rescan current folder (folders + files)
                dir_cache.pop(cur, None)
                file_cache.pop(cur, None)
                get_dir_listing(cur, force=True, stdscr=stdscr)
                get_file_listing(cur, force=True, stdscr=stdscr)

            elif ch in (ord('d'), ord('D')):
                if listing:
                    details_popup(stdscr, listing[selection[cur]].path)

            elif ch == curses.KEY_RESIZE:
                pass

    try:
        return curses.wrapper(curses_main)
    except Exception as e:
        if "Redirection is not supported" in str(e):
            print(
                "Your terminal does not support curses on Windows (Git Bash/mintty).\n"
                "Run in Windows Terminal / PowerShell instead, OR from Git Bash use:\n"
                "  winpty python ./folder_size_explorer.py /c\n",
                file=sys.stderr,
            )
            return 2
        raise


# ---------------------------
# Entry point
# ---------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Folder size explorer (two-pane TUI).")
    p.add_argument("path", nargs="?", default=".", help="Root path to start (supports /c/... on Windows).")
    p.add_argument("--workers", type=int, default=8, help="Thread workers for folder size calculation (default: 8).")
    p.add_argument("--follow-links", action="store_true", help="Follow symlinks/junctions (default: off).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    follow_links = bool(args.follow_links)
    workers = max(1, int(args.workers))

    raw = msys_to_windows_path(str(args.path))
    start = Path(raw).expanduser()

    try:
        start = start.resolve()
    except Exception:
        start = Path(os.path.abspath(str(start)))

    if not start.exists():
        print(f"Error: path does not exist: {start}", file=sys.stderr)
        return 2
    if not start.is_dir():
        print(f"Error: path is not a directory: {start}", file=sys.stderr)
        return 2

    return run_tui(start, follow_links, workers)


if __name__ == "__main__":
    raise SystemExit(main())
