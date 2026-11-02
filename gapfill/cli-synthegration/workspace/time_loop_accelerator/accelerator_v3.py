#!/usr/bin/env python3
"""Accelerator using tight_clean.json (only clean source files)."""
import json, statistics
from pathlib import Path

HOME = Path.home()
PROV = HOME / "cli-synthegration/workspace/provenance/tight_clean.json"
OUT = HOME / "cli-synthegration/workspace/time_loop_accelerator"

with open(PROV) as f:
    data = json.load(f)

delays = [v['delay_seconds'] for v in data.values()]
report = {
    'files': len(data),
    'median_delay_s': statistics.median(delays) if delays else None,
    'mean_delay_s': statistics.mean(delays) if delays else None,
    'min_s': min(delays) if delays else None,
    'max_s': max(delays) if delays else None,
}
with open(OUT / "clean_timing.json", 'w') as f:
    json.dump(report, f, indent=2)
print(report)