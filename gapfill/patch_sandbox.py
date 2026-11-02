#!/usr/bin/env python3
from pathlib import Path
from cedarscript_editor import CEDARScriptEditor

HOME = Path.home()
SANDBOX = HOME / "cli-synthegration/workspace/compression_sandbox"
editor = CEDARScriptEditor(root_path=str(SANDBOX))

patches = {
    "build_correlation.py": [
        {"command": "insert_after_marker", "marker": "from pathlib import Path", "new_lines": ["from cli_synthegration.json_gz_utils import save_json_gz"]},
        {"command": "replace_text", "old_text": '"correlation_index.json"', "new_text": '"correlation_index.json.gz"'},
        {"command": "replace_text", "old_text": 'with open(output_path, "w") as f:\n    json.dump(index, f, indent=2)', "new_text": 'save_json_gz(output_path, index, indent=2)'},
    ],
    "build_all_versions.py": [
        {"command": "insert_after_marker", "marker": "from pathlib import Path", "new_lines": ["from cli_synthegration.json_gz_utils import save_json_gz"]},
        {"command": "replace_text", "old_text": 'with open(OUT / "versioned_provenance_full.json", \'w\') as f:\n    json.dump(file_versions, f, indent=2)', "new_text": 'save_json_gz(OUT / "versioned_provenance_full.json", file_versions, indent=2)'},
        {"command": "replace_text", "old_text": '"versioned_provenance_full.json"', "new_text": '"versioned_provenance_full.json.gz"'},
    ],
    "accelerator_time.py": [
        {"command": "insert_after_marker", "marker": "from pathlib import Path", "new_lines": ["from cli_synthegration.json_gz_utils import load_json_gz"]},
        {"command": "replace_text", "old_text": 'versioned_provenance_full.json', "new_text": 'versioned_provenance_full.json.gz'},
        {"command": "replace_text", "old_text": 'with open(VERSIONED) as f:\n    data = json.load(f)', "new_text": 'data = load_json_gz(VERSIONED)'},
    ],
    "generate_handoff.py": [
        {"command": "insert_after_marker", "marker": "import sys", "new_lines": ["from cli_synthegration.json_gz_utils import load_json_gz"]},
        {"command": "replace_text", "old_text": "'codex' / 'message_index.json'", "new_text": "'codex' / 'message_index.json.gz'"},
        {"command": "replace_text", "old_text": 'len(json.loads(msg_idx.read_text()))', "new_text": 'len(load_json_gz(msg_idx))'},
    ],
    "synthegration_index_ref.py": [
        {"command": "insert_after_marker", "marker": "from datetime import datetime, timezone, timedelta", "new_lines": ["from cli_synthegration.json_gz_utils import save_json_gz, load_json_gz"]},
        {"command": "replace_text", "old_text": '"message_index.json"', "new_text": '"message_index.json.gz"'},
        {"command": "replace_text", "old_text": '(self.index_dir / "message_index.json.gz").write_text(json.dumps(serializable, indent=2))', "new_text": 'save_json_gz(self.index_dir / "message_index.json.gz", serializable, indent=2)'},
        {"command": "replace_text", "old_text": 'data = json.loads(idx_file.read_text())', "new_text": 'data = load_json_gz(idx_file)'},
    ],
    "time_loop_accelerator_staging.py": [
        {"command": "insert_after_marker", "marker": "import sys", "new_lines": ["from cli_synthegration.json_gz_utils import load_json_gz"]},
        {"command": "replace_text", "old_text": '"message_index.json"', "new_text": '"message_index.json.gz"'},
        {"command": "replace_text", "old_text": 'len(json.loads(mi_file.read_text()))', "new_text": 'len(load_json_gz(mi_file))'},
    ],
    "generate_loop.py": [
        {"command": "insert_after_marker", "marker": "import sys", "new_lines": ["from cli_synthegration.json_gz_utils import load_json_gz"]},
        {"command": "replace_text", "old_text": '"message_index.json"', "new_text": '"message_index.json.gz"'},
        {"command": "replace_text", "old_text": 'len(json.loads(mi_file.read_text())) if mi_file.exists() else 0', "new_text": 'len(load_json_gz(mi_file)) if mi_file.exists() else 0'},
    ],
    "Chronos_accelerator.py": [
        {"command": "insert_after_marker", "marker": "import sys", "new_lines": ["from cli_synthegration.json_gz_utils import load_json_gz"]},
        {"command": "replace_text", "old_text": '"message_index.json"', "new_text": '"message_index.json.gz"'},
        {"command": "replace_text", "old_text": 'len(json.loads(mi_file.read_text()))', "new_text": 'len(load_json_gz(mi_file))'},
    ],
    "generate_handoff_root.py": [
        {"command": "insert_after_marker", "marker": "import sys", "new_lines": ["from cli_synthegration.json_gz_utils import load_json_gz"]},
        {"command": "replace_text", "old_text": "'codex' / 'message_index.json'", "new_text": "'codex' / 'message_index.json.gz'"},
        {"command": "replace_text", "old_text": 'len(json.loads(msg_idx.read_text()))', "new_text": 'len(load_json_gz(msg_idx))'},
    ],
    "synthegration_index.py": [
        {"command": "insert_after_marker", "marker": "from datetime import datetime, timezone, timedelta", "new_lines": ["from cli_synthegration.json_gz_utils import save_json_gz, load_json_gz"]},
        {"command": "replace_text", "old_text": '"message_index.json"', "new_text": '"message_index.json.gz"'},
        {"command": "replace_text", "old_text": '(self.index_dir / "message_index.json.gz").write_text(json.dumps(serializable, indent=2))', "new_text": 'save_json_gz(self.index_dir / "message_index.json.gz", serializable, indent=2)'},
        {"command": "replace_text", "old_text": 'data = json.loads(idx_file.read_text())', "new_text": 'data = load_json_gz(idx_file)'},
    ],
}

for fname, cmds in patches.items():
    fp = SANDBOX / fname
    if fp.exists():
        for cmd in cmds:
            try:
                editor.apply_commands([{**cmd, "path": str(fp)}])
                print(f"  ✓ {fname}: {cmd['command']}")
            except Exception as e:
                print(f"  ✗ {fname}: {e}")
    else:
        print(f"⚠ Missing: {fname}")