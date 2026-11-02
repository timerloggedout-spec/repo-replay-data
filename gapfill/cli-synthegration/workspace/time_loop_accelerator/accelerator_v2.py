#!/usr/bin/env python3
"""Accelerator using clean true_versions.json."""
import json, statistics
from pathlib import Path
from collections import defaultdict

HOME = Path.home()
VERSIONED = HOME / "cli-synthegration/workspace/provenance/true_versions.json"
OUT = HOME / "cli-synthegration/workspace/time_loop_accelerator"

with open(VERSIONED) as f:
    data = json.load(f)

# First-write delays vs iteration delays
first_delays = []
iter_delays = []
for versions in data.values():
    if len(versions) >= 2:
        first_delays.append(versions[0]['delay_s'])
        for v in versions[1:]:
            iter_delays.append(v['delay_s'])
    elif versions:
        first_delays.append(versions[0]['delay_s'])

report = {
    'files_with_versions': len(data),
    'first_write_median_s': statistics.median(first_delays) if first_delays else None,
    'iteration_median_s': statistics.median(iter_delays) if iter_delays else None,
    'speedup_factor': round(statistics.median(first_delays) / statistics.median(iter_delays), 2) if (first_delays and iter_delays and statistics.median(iter_delays) > 0) else None,
    'total_iterations': len(iter_delays)
}
with open(OUT / "clean_acceleration.json", 'w') as f:
    json.dump(report, f, indent=2)
print(f"Clean acceleration: {report}")