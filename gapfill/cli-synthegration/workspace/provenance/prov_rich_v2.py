#!/usr/bin/env python3
"""
Rich TUI for versioned file provenance.
Keys: ↑↓/j k – navigate, Enter – details & version chain, q – quit,
      s – sort by (name/delay/iterations), f – filter by session
"""
import json, sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box
from datetime import datetime

PROV_FILE = Path.home() / "cli-synthegration/workspace/provenance/versioned_provenance.json"
if not PROV_FILE.exists():
    print("Run versioned_provenance.py first.")
    sys.exit(1)

with open(PROV_FILE) as f:
    data = json.load(f)

# Build items list: (fname, entry)
items = [(fname, entry) for fname, entry in data.items()]

SORT_KEY = 'name'  # 'name', 'delay', 'iterations', 'span'
SORT_REVERSE = False

def sort_items():
    global items
    if SORT_KEY == 'name':
        items.sort(key=lambda x: x[0], reverse=SORT_REVERSE)
    elif SORT_KEY == 'delay':
        items.sort(key=lambda x: x[1].get('first_write_delay_s') or 0, reverse=SORT_REVERSE)
    elif SORT_KEY == 'iterations':
        items.sort(key=lambda x: x[1].get('iteration_count', 0), reverse=SORT_REVERSE)
    elif SORT_KEY == 'span':
        items.sort(key=lambda x: x[1].get('total_evolution_span_s') or 0, reverse=SORT_REVERSE)

console = Console()
current = 0
detail_mode = False
filter_session = None

def make_table():
    table = Table(title="Versioned File Provenance", box=box.SIMPLE, expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan", width=42, no_wrap=False)
    table.add_column("Delay", style="green", width=12, justify="right")
    table.add_column("Iters", style="yellow", width=6, justify="right")
    table.add_column("Span", style="magenta", width=12, justify="right")
    
    visible = items
    if filter_session:
        visible = [(f, e) for f, e in items if any(
            v['session'] == filter_session for v in e.get('versions', [])
        )]
    
    for i, (fname, entry) in enumerate(visible):
        delay = entry.get('first_write_delay_s')
        delay_str = f"{delay:.0f}s" if delay is not None else "—"
        iters = str(entry.get('iteration_count', 0))
        span = entry.get('total_evolution_span_s')
        span_str = f"{span:.0f}s" if span is not None else "—"
        style = "bold reverse" if i == current else ""
        table.add_row(str(i), fname, delay_str, iters, span_str, style=style)
    return table

def show_detail():
    fname, entry = items[current]
    content = f"[bold cyan]File:[/] {fname}\n\n"
    content += f"[bold]First‑write delay:[/] {entry.get('first_write_delay_s', 'N/A')}s\n"
    content += f"[bold]Iterations:[/] {entry.get('iteration_count', 0)}\n"
    content += f"[bold]Evolution span:[/] {entry.get('total_evolution_span_s', 'N/A')}s\n"
    content += f"[bold]File mtime:[/] {entry.get('file_mtime_utc', 'N/A')}\n\n"
    content += f"[bold underline]Version chain:[/]\n"
    for i, v in enumerate(entry.get('versions', [])):
        ts = v['timestamp_utc'][:19] if v['timestamp_utc'] else '?'
        content += f"  [yellow]v{i}[/] {ts}  session={v['session'][:20]}...  block={v['block_idx']}\n"
        content += f"      [dim]{v['snippet'][:80]}...[/]\n"
    console.clear()
    console.print(Panel(content, title=f"Detail: {fname}", border_style="cyan"))
    console.print("\n[dim]Enter/Backspace: list | q: quit | v: version graph[/]")

def main():
    global current, detail_mode, SORT_KEY, SORT_REVERSE, filter_session
    sort_items()
    with Live(make_table(), console=console, refresh_per_second=10, screen=True) as live:
        while True:
            if detail_mode:
                show_detail()
                key = console.input("").strip().lower()
                if key == 'q':
                    break
                elif key in ['', '\x08', 'enter']:
                    detail_mode = False
                    live.update(make_table())
                elif key == 'v':
                    # Show version graph
                    fname, entry = items[current]
                    console.clear()
                    console.print(Panel(
                        "\n".join(f"v{i}: {v['timestamp_utc'][:19]} | {v['session'][:30]}" 
                                  for i, v in enumerate(entry.get('versions', []))),
                        title=f"Version Graph: {fname}"
                    ))
                    console.input("Press Enter to continue")
                    console.clear()
            else:
                live.update(make_table())
                key = console.input("j/k:nav s:sort f:filter Enter:detail q:quit ").strip().lower()
                if key == 'q':
                    break
                elif key in ['j', ''] and current < len(items) - 1:
                    current += 1
                elif key == 'k' and current > 0:
                    current -= 1
                elif key in ['l', 'enter', '\r']:
                    detail_mode = True
                elif key == 's':
                    # Cycle sort
                    keys = ['name', 'delay', 'iterations', 'span']
                    idx = keys.index(SORT_KEY)
                    if idx == len(keys) - 1:
                        SORT_REVERSE = not SORT_REVERSE
                        SORT_KEY = keys[0]
                    else:
                        SORT_KEY = keys[idx + 1]
                    sort_items()
                    current = 0
                elif key == 'f':
                    session = console.input("Session filter (empty to clear): ").strip()
                    filter_session = session if session else None
                    current = 0

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass