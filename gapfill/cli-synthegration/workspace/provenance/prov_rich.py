#!/usr/bin/env python3
"""
Rich‑based file provenance browser. Beautiful, navigable, fast.
Arrow keys to scroll, Enter for details, q to quit.
"""
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box
import os, sys

PROV_FILE = Path.home() / "cli-synthegration/workspace/provenance/recent_provenance.json"
if not PROV_FILE.exists():
    PROV_FILE = Path.home() / "cli-synthegration/workspace/provenance/temporal_provenance.json"
if not PROV_FILE.exists():
    PROV_FILE = Path.home() / "cli-synthegration/workspace/provenance/file_provenance.json"

with open(PROV_FILE) as f:
    data = json.load(f)

items = list(data.items())  # [(file, entry), ...]

console = Console()
current = 0
detail_mode = False

def make_table():
    table = Table(title="File Provenance Map", box=box.SIMPLE, expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan", no_wrap=False, width=45)
    table.add_column("Session", style="yellow", width=36)
    table.add_column("Delay", style="green", width=10, justify="right")
    for i, (fname, entry) in enumerate(items):
        delay = entry.get('delay_seconds')
        delay_str = f"{delay:.0f}s" if delay is not None else "—"
        style = "bold" if i == current else ""
        table.add_row(str(i), fname, entry.get('session', '')[:36], delay_str, style=style)
    return table

def show_detail():
    fname, entry = items[current]
    content = f"[bold cyan]File:[/] {fname}\n"
    content += f"[bold yellow]Session:[/] {entry.get('session')}\n"
    content += f"[bold green]Block index:[/] {entry.get('block_idx')}\n"
    delay = entry.get('delay_seconds')
    content += f"[bold green]Delay:[/] {delay:.0f}s\n" if delay is not None else "Delay: N/A\n"
    snippet = entry.get('snippet', '')
    content += f"\n[bold]Snippet:[/]\n{snippet[:500]}"
    console.clear()
    console.print(Panel(content, title="File Detail", border_style="cyan"))
    console.print("\n[dim]Press Enter/Backspace to return to list, q to quit[/]")

def main():
    global current, detail_mode
    with Live(make_table(), console=console, refresh_per_second=10, screen=True) as live:
        while True:
            if detail_mode:
                show_detail()
                key = console.input("").strip().lower()
                if key == 'q':
                    break
                elif key in ['', '\x08']:  # Enter or Backspace
                    detail_mode = False
                    live.update(make_table())
            else:
                live.update(make_table())
                # Manual input for keys (rich Live doesn't support getch well)
                key = console.input("↑↓:navigate  Enter:detail  q:quit ").strip().lower()
                if key == 'q':
                    break
                elif key == 'j' and current < len(items) - 1:  # down
                    current += 1
                elif key == 'k' and current > 0:  # up
                    current -= 1
                elif key == 'l' or key == '':  # Enter
                    detail_mode = True
                elif key.startswith('g'):
                    parts = key.split()
                    if len(parts) > 1 and parts[1].isdigit():
                        current = min(int(parts[1]), len(items)-1)
    console.clear()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass