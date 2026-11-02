#!/usr/bin/env python3
"""provenance_api.py – Importable file‑provenance queries."""
import json
from pathlib import Path

_HOME = Path.home()
_COMPREHENSIVE = _HOME / "cli-synthegration/workspace/provenance/comprehensive_provenance.json"
_TRUE = _HOME / "cli-synthegration/workspace/provenance/true_versions.json"
_TIGHT = _HOME / "cli-synthegration/workspace/provenance/tight_provenance.json"

_data = None
def _load():
    global _data
    if _data is not None: return
    for src in [_COMPREHENSIVE, _TRUE, _TIGHT]:
        if src.exists():
            with open(src) as f:
                _data = json.load(f)
            return
    _data = {}

def get_origin(relative_path: str):
    _load()
    return _data.get(relative_path)

def summary():
    _load()
    delays = []
    for v in _data.values():
        entries = v if isinstance(v, list) else [v]
        for e in entries:
            d = e.get('delay_s') or e.get('delay_seconds')
            if d is not None: delays.append(d)
    if not delays: return {}
    import statistics
    return {
        'files': len(_data),
        'min_s': min(delays), 'max_s': max(delays),
        'mean_s': statistics.mean(delays), 'median_s': statistics.median(delays)
    }

def search(session_id: str):
    _load()
    results = []
    for f, v in _data.items():
        for e in (v if isinstance(v, list) else [v]):
            if e.get('session') == session_id:
                results.append((f, e))
    return results

def all_files():
    _load()
    return list(_data.keys())