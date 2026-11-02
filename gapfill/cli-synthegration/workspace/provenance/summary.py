#!/usr/bin/env python3
"""Regenerate the summary JSON (can be called periodically)."""
from provenance_api import summary
import json
with open("provenance_summary.json", 'w') as f:
    json.dump(summary(), f, indent=2)
print("Summary written to provenance_summary.json")