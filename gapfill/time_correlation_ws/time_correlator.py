#!/usr/bin/env python3
"""
Time‑Correlation Index for file writes vs. cache exports, searches, etc.
Works in its own workspace directory (default: .).
Logs file modifications and arbitrary events, then computes a correlation report.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent   # all data stored here
EVENTS_LOG = WORKSPACE / "events.jsonl"
INDEX_FILE = WORKSPACE / "correlation_index.json"
# poll interval for watching
POLL_SECONDS = 5

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def log_event(event_type, path=None):
    entry = {
        "timestamp": now_iso(),
        "type": event_type,
        "path": str(path) if path else None
    }
    with open(EVENTS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"Logged {event_type}" + (f" for {path}" if path else ""))

def load_events():
    events = []
    if EVENTS_LOG.exists():
        with open(EVENTS_LOG) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return events

def watch_dir(target_dir):
    """Poll target_dir for modified files and log 'file_modified' events."""
    target = Path(target_dir).resolve()
    print(f"Watching {target} for file modifications (polling every {POLL_SECONDS}s)... Press Ctrl+C to stop.")
    # Initial state: file paths -> (mtime, size)
    state = {}
    try:
        while True:
            new_state = {}
            for fp in target.rglob("*"):
                if fp.is_file():
                    try:
                        stat = fp.stat()
                        mtime = stat.st_mtime
                        size = stat.st_size
                        new_state[str(fp)] = (mtime, size)
                    except OSError:
                        continue
            # Compare with previous state
            for fpath, (mtime, size) in new_state.items():
                prev = state.get(fpath)
                if prev is None or prev != (mtime, size):
                    log_event("file_modified", fpath)
            state = new_state
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("Stopped watching.")

def generate_report():
    """Read all events and produce correlation index."""
    events = load_events()
    if not events:
        print("No events recorded.")
        return

    # Last write time per file (file_modified events)
    file_last_write = {}
    for ev in events:
        if ev["type"] == "file_modified" and ev["path"]:
            file_last_write[ev["path"]] = ev["timestamp"]

    # Last occurrence of each event type (excluding file_modified)
    last_event = {}
    for ev in events:
        if ev["type"] != "file_modified":
            last_event[ev["type"]] = ev["timestamp"]

    # Build index
    index = {
        "generated": now_iso(),
        "last_events": last_event,
        "files": []
    }
    for fpath, last_ts in file_last_write.items():
        file_entry = {"path": fpath, "last_write": last_ts, "deltas": {}}
        last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        for etype, ets in last_event.items():
            ev_dt = datetime.fromisoformat(ets.replace("Z", "+00:00"))
            diff = last_dt - ev_dt   # positive means file was written after the event
            file_entry["deltas"][etype] = {
                "last_event_time": ets,
                "seconds_since_event": diff.total_seconds()
            }
        index["files"].append(file_entry)

    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)
    print(f"Correlation index written to {INDEX_FILE}")
    print("Summary:")
    for f in index["files"]:
        print(f"  {f['path']} (last write: {f['last_write']})")
        for etype, delta in f["deltas"].items():
            print(f"    vs {etype}: {delta['seconds_since_event']:.0f} sec later")

def main():
    parser = argparse.ArgumentParser(description="Time‑Correlation Index tool")
    sub = parser.add_subparsers(dest="command", required=True)

    watch_parser = sub.add_parser("watch", help="Monitor a directory for file modifications")
    watch_parser.add_argument("directory", help="Path to watch")

    event_parser = sub.add_parser("log-event", help="Record a manual event")
    event_parser.add_argument("event_type", help="Event label (e.g., cache_export, search_performed)")

    sub.add_parser("report", help="Generate correlation index from all events")

    args = parser.parse_args()

    if args.command == "watch":
        watch_dir(args.directory)
    elif args.command == "log-event":
        log_event(args.event_type)
    elif args.command == "report":
        generate_report()

if __name__ == "__main__":
    main()