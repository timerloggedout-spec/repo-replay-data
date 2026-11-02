#!/usr/bin/env python3
"""Textual TUI to explore file provenance."""
import sys
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, DataTable, Static
from textual.binding import Binding

HOME = Path.home()
sys.path.insert(0, str(HOME / "cli-synthegration/workspace/provenance"))
from provenance_api import _data as load_data

PROV_FILE = HOME / "cli-synthegration/workspace/provenance/true_file_provenance.json"
if not PROV_FILE.exists():
    PROV_FILE = HOME / "cli-synthegration/workspace/provenance/file_provenance.json"

import json
with open(PROV_FILE) as f:
    provenance = json.load(f)

class ProvenanceExplorer(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "show_detail", "Detail"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("File Provenance Explorer – [bold]Q[/] Quit  [bold]D[/] Detail", id="status")
        table = DataTable()
        table.add_column("File", width=40)
        table.add_column("Session", width=30)
        table.add_column("Delay", width=10)
        table.add_column("Timestamp", width=25)
        self.table = table
        self.detail_view = Static("", id="detail")
        yield table
        yield Footer()

    def on_mount(self):
        for fname, entry in provenance.items():
            delay = entry.get('delay_seconds')
            delay_str = f"{delay:.0f}s" if delay is not None else "N/A"
            ts = entry.get('timestamp_utc', '')[:19]
            self.table.add_row(fname, entry.get('session',''), delay_str, ts)

    def action_show_detail(self):
        row = self.table.cursor_coordinate
        if row is not None:
            fname = self.table.get_cell_at(row)[0]
            entry = provenance.get(fname)
            if entry:
                self.detail_view.update(
                    f"[bold]File:[/bold] {fname}\n"
                    f"[bold]Session:[/bold] {entry.get('session')}\n"
                    f"[bold]Block:[/bold] {entry.get('block_idx')}\n"
                    f"[bold]Delay:[/bold] {entry.get('delay_seconds')}s\n"
                    f"[bold]Snippet:[/bold]\n{entry.get('snippet','')}"
                )
                self.mount(self.detail_view)

if __name__ == "__main__":
    app = ProvenanceExplorer()
    app.run()