#!/usr/bin/env python3
"""Patch deepcli.py: replace upload_file with working version using real API + PoW."""
import os, re

DEEPCLI = '/data/data/com.termux/files/home/deepcli/deepcli.py'
with open(DEEPCLI, 'r') as f:
    content = f.read()

# ----------------- new helper functions -------------------
new_imports = '''
import subprocess
import base64
'''

# Inject imports if missing
if 'import subprocess' not in content:
    # add after existing imports, before first function definition
    content = content.replace('import re', 'import re' + new_imports, 1)

# --- Helper to call Node PoW solver ---
pow_helper = '''
def _solve_pow(challenge, salt, expire_at, difficulty):
    """Solve PoW using deepterm's WASM solver via Node.js."""
    script = os.path.expanduser("~/deepseek-cli/pow_solve_standalone.js")
    # create the script if it doesn't exist
    if not os.path.exists(script):
        js_code = """
import { solvePow } from './deepterm/deepterm-core.js';
const args = process.argv.slice(2);
const [challenge, salt, expire_at, difficulty] = args;
solvePow(challenge, salt, expire_at, parseInt(difficulty))
  .then(answer => process.stdout.write(String(answer)))
  .catch(e => { process.stderr.write(e.message); process.exit(1); });
"""
        os.makedirs(os.path.dirname(script), exist_ok=True)
        with open(script, 'w') as f:
            f.write(js_code)
    cmd = ['node', script, challenge, salt, str(expire_at), str(difficulty)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise RuntimeError(f'PoW solver failed: {res.stderr}')
    return int(res.stdout.strip())
'''

# Find the location of the old upload_file function and replace it
# Old function signature: def upload_file(token, sid, filepath):
old_upload = r'def upload_file\(token, sid, filepath\):.*?(?=def |class |\Z)'
# We'll build the full new function
new_upload = '''def upload_file(token, sid, filepath):
    """Upload a file and return its file_id. Uses PoW if required."""
    import requests
    from pathlib import Path

    BASE = "https://chat.deepseek.com/api/v0"
    headers_ = {
        "Authorization": f"Bearer {token}",
        "accept": "*/*",
        "x-client-platform": "web",
        "x-client-version": "1.3.0-auto-resume",
        "referer": "https://chat.deepseek.com/",
        "content-type": "application/json",
    }

    # 1. Get PoW challenge
    pow_resp = None
    try:
        r = requests.post(f"{BASE}/chat/create_pow_challenge",
                          headers=headers_,
                          json={"target_path": "/api/v0/file/upload_file"})
        if r.status_code == 200:
            c = r.json()['data']['biz_data']['challenge']
            answer = _solve_pow(c['challenge'], c['salt'], c['expire_at'], c['difficulty'])
            payload = {
                "algorithm": c['algorithm'],
                "challenge": c['challenge'],
                "salt": c['salt'],
                "answer": answer,
                "signature": c['signature'],
                "target_path": "/api/v0/file/upload_file",
            }
            pow_resp = base64.b64encode(json.dumps(payload).encode()).decode()
    except Exception as e:
        print(f"⚠️  PoW generation failed, trying without: {e}", file=sys.stderr)

    # 2. Upload file
    filename = Path(filepath).name
    with open(filepath, 'rb') as f:
        files = {'file': (filename, f, 'application/octet-stream')}
        upload_headers = {
            "Authorization": f"Bearer {token}",
            "accept": "*/*",
            "x-client-platform": "web",
            "x-client-version": "1.3.0-auto-resume",
            "referer": f"https://chat.deepseek.com/a/chat/s/{sid}",
            "x-thinking-enabled": "0",
        }
        if pow_resp:
            upload_headers["x-ds-pow-response"] = pow_resp
        r = requests.post(f"{BASE}/file/upload_file", headers=upload_headers, files=files)

    if r.status_code == 200:
        data = r.json()
        fid = data.get('data', {}).get('file_id')
        if fid:
            print(f"✅ Uploaded {filename} → file_id {fid}", file=sys.stderr)
            return fid
    print(f"❌ Upload failed: {r.status_code} {r.text}", file=sys.stderr)
    return None

'''

# Replace old upload_file with new one (regex, multiline)
content = re.sub(old_upload, new_upload, content, flags=re.DOTALL)

# Also add _solve_pow helper somewhere before the upload_file function
# Insert it just before the new upload_file definition
if '_solve_pow' not in content:
    insertion_point = 'def upload_file(token, sid, filepath):'
    content = content.replace(insertion_point, pow_helper + insertion_point)

# Add wait_for_file if missing (it probably exists)
if 'wait_for_file' not in content:
    wait_for_file_func = '''
def wait_for_file(token, fid):
    """Poll until file is processed."""
    import time, requests
    for _ in range(30):
        r = requests.get(f"https://chat.deepseek.com/api/v0/file/fetch_files?file_ids={fid}",
                         headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            data = r.json()
            status = data.get('data', [{}])[0].get('status', '')
            if status == 'SUCCESS':
                return True
            elif status == 'FAILED':
                return False
        time.sleep(1)
    return False
'''
    # Insert before main function or at end
    content += wait_for_file_func

with open(DEEPCLI, 'w') as f:
    f.write(content)

print('✅ deepcli.py upload_file patched – uses real API with PoW.')