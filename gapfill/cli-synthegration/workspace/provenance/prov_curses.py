#!/usr/bin/env python3
"""Curses-based file provenance browser. Arrow keys, Enter for detail, q to quit."""
import curses
import json
from pathlib import Path

PROV_FILE = Path.home() / "cli-synthegration/workspace/provenance/temporal_provenance.json"
if not PROV_FILE.exists():
    PROV_FILE = Path.home() / "cli-synthegration/workspace/provenance/file_provenance.json"

with open(PROV_FILE) as f:
    data = json.load(f)

items = list(data.items())  # [(file, entry), ...]

def format_line(fname, entry, width=80):
    delay = entry.get('delay_seconds')
    delay_str = f"{delay:.0f}s" if delay is not None else "N/A"
    session = entry.get('session', '')[:30]
    return f"{fname:<50} {session:<30} {delay_str:>8}"

def detail_screen(stdscr, fname, entry):
    stdscr.clear()
    stdscr.addstr(0, 0, f"File: {fname}")
    stdscr.addstr(1, 0, f"Session: {entry.get('session')}")
    stdscr.addstr(2, 0, f"Block index: {entry.get('block_idx')}")
    stdscr.addstr(3, 0, f"Delay: {entry.get('delay_seconds', 'N/A')}s")
    snippet = entry.get('snippet', '')
    stdscr.addstr(5, 0, "Snippet:")
    for i, line in enumerate(snippet.split('\n')[:10]):
        stdscr.addstr(6 + i, 0, line[:80])
    stdscr.addstr(18, 0, "Press Enter to return to list, q to quit")
    stdscr.refresh()
    while True:
        key = stdscr.getch()
        if key in [10, 13, ord('q'), 27]:  # Enter or q or Esc
            return key == ord('q')

def main(stdscr):
    curses.curs_set(0)
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
    current = 0
    scroll = 0
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        header = f"File Provenance Browser ({len(items)} files) – ↑↓:move  Enter:details  q:quit"
        stdscr.addstr(0, 0, header[:width-1], curses.color_pair(1))
        for i in range(scroll, min(scroll + height - 2, len(items))):
            fname, entry = items[i]
            line = format_line(fname, entry, width-1)
            attr = curses.color_pair(2) if i == current else curses.A_NORMAL
            stdscr.addstr(i - scroll + 1, 0, line[:width-1], attr)
        stdscr.refresh()
        key = stdscr.getch()
        if key == ord('q'):
            break
        elif key == curses.KEY_UP and current > 0:
            current -= 1
            if current < scroll:
                scroll = current
        elif key == curses.KEY_DOWN and current < len(items) - 1:
            current += 1
            if current >= scroll + height - 2:
                scroll = current - (height - 3)
        elif key in [10, 13]:  # Enter
            fname, entry = items[current]
            want_quit = detail_screen(stdscr, fname, entry)
            if want_quit:
                break

if __name__ == '__main__':
    curses.wrapper(main)