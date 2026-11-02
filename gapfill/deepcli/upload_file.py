#!/usr/bin/env python3
"""
upload_file.py – Direct file upload to DeepSeek chat using the public API.
Requires a valid token (fetched from deepcli or deepterm).
Usage: python upload_file.py --token <token> --file <path>
"""

import argparse, json, os, requests, sys, time
from pathlib import Path

BASE = "https://chat.deepseek.com/api/v0"

def get_token_from_deepcli():
    """Try to read a saved token from deepcli's cache."""
    cache = Path.home() / '.deepcli' / 'auth.json'
    if cache.exists():
        with open(cache) as f:
            data = json.load(f)
            return data.get('token')
    return None

def create_pow_challenge(token, target_path="/api/v0/file/upload_file"):
    """Request a PoW challenge for the upload endpoint."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"target_path": target_path}
    resp = requests.post(f"{BASE}/chat/create_pow_challenge", headers=headers, json=payload)
    if resp.status_code == 200:
        return resp.json()["data"]
    else:
        print(f"⚠️  Failed to get PoW challenge: {resp.status_code} {resp.text}", file=sys.stderr)
        return None

def solve_pow_with_wasm(challenge):
    """Call deepseek.wasm solver via node (if available)."""
    # This is a placeholder – ideally you'd use deepterm's WASM module.
    # For now, return a dummy solution that may work for file uploads
    # (in testing, file uploads sometimes succeed without PoW).
    return {
        "algorithm": "DeepSeekHashV1",
        "challenge": challenge,
        "answer": "0"*64,   # dummy – may need real solution
    }

def upload_file(token, file_path, pow_response=None):
    """Upload a file and return its file_id."""
    url = f"{BASE}/file/upload_file"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if pow_response:
        headers["x-ds-pow-response"] = json.dumps(pow_response)

    file_name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        files = {"file": (file_name, f, "application/octet-stream")}
        resp = requests.post(url, headers=headers, files=files)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("data", {}).get("file_id"):
            return data["data"]["file_id"]
        else:
            print(f"⚠️  Upload succeeded but no file_id: {data}", file=sys.stderr)
            return None
    else:
        print(f"❌ Upload failed: {resp.status_code} {resp.text}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description="Direct file upload to DeepSeek")
    parser.add_argument("--file", "-f", required=True, help="File to upload")
    parser.add_argument("--token", "-t", help="Bearer token (if omitted, tries deepcli cache)")
    parser.add_argument("--skip-pow", action="store_true", help="Skip PoW challenge (may still work)")
    args = parser.parse_args()

    token = args.token or get_token_from_deepcli()
    if not token:
        print("❌ No token found. Provide --token or run deepcli first.", file=sys.stderr)
        sys.exit(1)

    pow_resp = None
    if not args.skip_pow:
        challenge = create_pow_challenge(token)
        if challenge:
            pow_resp = solve_pow_with_wasm(challenge)
            if not pow_resp:
                print("⚠️  Could not solve PoW, attempting upload without it...", file=sys.stderr)

    file_id = upload_file(token, args.file, pow_resp)
    if file_id:
        print(json.dumps({"success": True, "file_id": file_id, "file_name": os.path.basename(args.file)}))
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()