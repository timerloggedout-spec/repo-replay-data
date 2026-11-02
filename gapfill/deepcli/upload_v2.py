#!/usr/bin/env python3
"""Upload a file to DeepSeek chat using the real API, PoW solver via Node.js."""

import requests, json, os, sys, subprocess, time
from pathlib import Path

BASE = "https://chat.deepseek.com/api/v0"
TOKEN = None  # will be set from deepcli cache or argument

def get_token():
    global TOKEN
    if TOKEN: return TOKEN
    cache = Path.home() / '.deepcli' / 'auth.json'
    if cache.exists():
        with open(cache) as f:
            TOKEN = json.load(f).get('token')
    return TOKEN

def headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "accept": "*/*",
        "x-client-platform": "web",
        "x-client-version": "1.3.0-auto-resume",
        "referer": "https://chat.deepseek.com/",
    }

def pow_solve(challenge, salt, expire_at, difficulty):
    """Call Node.js to solve the PoW using deepterm's WASM."""
    script = Path.home() / 'deepseek-cli' / 'pow_solve_standalone.js'
    cmd = ['node', str(script), challenge, salt, str(expire_at), str(difficulty)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise RuntimeError(f"PoW solver failed: {res.stderr}")
    return res.stdout.strip()

def generate_pow_header(target_path="/api/v0/file/upload_file"):
    resp = requests.post(f"{BASE}/chat/create_pow_challenge",
                         headers={**headers(), "content-type": "application/json"},
                         json={"target_path": target_path})
    data = resp.json()['data']['biz_data']['challenge']
    answer = pow_solve(data['challenge'], data['salt'], data['expire_at'], data['difficulty'])
    payload = {
        "algorithm": data['algorithm'],
        "challenge": data['challenge'],
        "salt": data['salt'],
        "answer": int(answer),
        "signature": data['signature'],
        "target_path": target_path,
    }
    import base64
    return base64.b64encode(json.dumps(payload).encode()).decode()

def upload_file(filepath, token=None):
    global TOKEN
    TOKEN = token or get_token()
    if not TOKEN:
        print("❌ No token. Provide --token or run deepcli first.", file=sys.stderr)
        sys.exit(1)

    pow_resp = generate_pow_header()
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as f:
        files = {'file': (filename, f, 'application/octet-stream')}
        resp = requests.post(f"{BASE}/file/upload_file",
                             headers={**headers(), 'x-ds-pow-response': pow_resp},
                             files=files)
    if resp.status_code == 200:
        data = resp.json()
        fid = data['data'].get('file_id')
        if fid:
            print(json.dumps({"success": True, "file_id": fid, "filename": filename}))
            return fid
    print(f"❌ Upload failed: {resp.status_code} {resp.text}", file=sys.stderr)
    sys.exit(1)

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--file', '-f', required=True)
    p.add_argument('--token', '-t')
    args = p.parse_args()
    upload_file(args.file, args.token)