#!/usr/bin/env python3
"""
progress_tracker.py – Importable checkpoint/progress utility for long‑running scripts.
Writes progress to disk after every batch so work is never lost on crash.
"""
import json, time, signal, sys
from pathlib import Path
from datetime import datetime, timezone

class ProgressTracker:
    def __init__(self, checkpoint_file: str, total_items: int, batch_size: int = 10):
        self.checkpoint_file = Path(checkpoint_file)
        self.total = total_items
        self.batch_size = batch_size
        self.completed = 0
        self.results = {}           # accumulated results
        self.start_time = time.time()
        self._load_checkpoint()
        # Register graceful shutdown
        signal.signal(signal.SIGINT, self._save_and_exit)
        signal.signal(signal.SIGTERM, self._save_and_exit)

    def _load_checkpoint(self):
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file) as f:
                    saved = json.load(f)
                self.results = saved.get('results', {})
                self.completed = saved.get('completed', 0)
                self.start_time = saved.get('start_time', self.start_time)
                print(f"Resumed from checkpoint: {self.completed}/{self.total} items done.")
            except:
                print("Checkpoint corrupt, starting fresh.")

    def _save_checkpoint(self):
        with open(self.checkpoint_file, 'w') as f:
            json.dump({
                'completed': self.completed,
                'total': self.total,
                'start_time': self.start_time,
                'last_update': datetime.now(timezone.utc).isoformat(),
                'results': self.results
            }, f, indent=2)

    def _save_and_exit(self, signum=None, frame=None):
        self._save_checkpoint()
        elapsed = time.time() - self.start_time
        print(f"\nProgress saved: {self.completed}/{self.total} ({elapsed:.0f}s). Resume with same command.")
        sys.exit(0)

    def update(self, key, value):
        self.results[key] = value
        self.completed += 1
        if self.completed % self.batch_size == 0 or self.completed == self.total:
            self._save_checkpoint()
            elapsed = time.time() - self.start_time
            rate = self.completed / elapsed if elapsed > 0 else 0
            eta = (self.total - self.completed) / rate if rate > 0 else 0
            print(f"  [{self.completed}/{self.total}] {self.completed*100//self.total}% — {rate:.1f}/s — ETA {eta:.0f}s")

    def finish(self, final_key=None, final_value=None):
        if final_key:
            self.results[final_key] = final_value
        self.completed = self.total
        self._save_checkpoint()
        elapsed = time.time() - self.start_time
        print(f"Complete: {self.total} items in {elapsed:.0f}s.")
        return self.results