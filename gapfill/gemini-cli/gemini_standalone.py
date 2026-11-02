#!/usr/bin/env python3
"""
gemini-standalone – Minimal Gemini client with Gem (system prompt) support.
"""

import json
import urllib.request
import urllib.parse
import time
import ssl
import sys
import uuid
import re
import os
import hashlib
from typing import Optional, Tuple

__version__ = "0.2.0"

CONFIG = {
    "cookie_file": os.environ.get("GEMINI_COOKIE_FILE", ""),
    "auth_user": os.environ.get("GEMINI_AUTH_USER", ""),
    "xsrf_token": os.environ.get("GEMINI_XSRF_TOKEN", ""),
    "gemini_bl": "boq_assistant-bard-web-server_20260525.09_p0",
    "default_model": "gemini-3.5-flash",
    "retry_attempts": 3,
    "retry_delay_sec": 2,
    "proxy": os.environ.get("GEMINI_PROXY", ""),
}

MODELS = {
    "gemini-3.5-flash":          {"mode": 1, "think": 4},
    "gemini-3.5-flash-thinking": {"mode": 2, "think": 0},
    "gemini-3.1-pro":            {"mode": 3, "think": 4},
    "gemini-auto":               {"mode": 4, "think": 4},
    "gemini-3.5-flash-thinking-lite": {"mode": 5, "think": 0},
    "gemini-flash-lite":         {"mode": 6, "think": 4},
}

# ─── Helpers (same as before) ──────────────────────────────────────────────

def load_cookie() -> Tuple[str, Optional[str]]:
    cookie_file = CONFIG.get("cookie_file")
    if not cookie_file or not os.path.exists(cookie_file):
        return "", None
    try:
        with open(cookie_file, "r") as f:
            content = f.read().strip()
        if content.startswith("{"):
            data = json.loads(content)
            cookie_str = data.get("cookie", "")
            sapisid = data.get("sapisid", "")
        else:
            cookie_str = content
            pairs = dict(p.split("=", 1) for p in cookie_str.split("; ") if "=" in p)
            sapisid = pairs.get("SAPISID", "")
        return cookie_str, sapisid if sapisid else None
    except Exception as e:
        sys.stderr.write(f"[!] Cookie load error: {e}\n")
        return "", None

def make_sapisidhash(sapisid: str) -> str:
    ts = int(time.time())
    h = hashlib.sha1(f"{ts} {sapisid} https://gemini.google.com".encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{h}"

def account_prefix() -> str:
    auth_user = CONFIG.get("auth_user")
    return f"/u/{auth_user}" if auth_user else ""

def build_payload(prompt: str, model_id: int, think_mode: int, gem: str = None) -> bytes:
    # inner[0] is the main prompt; we can prepend gem as a system instruction.
    # Alternatively, we can put it in inner[2] which is metadata.
    # Based on Gemini-API, the gem is passed in the request's model header and also in the RPC.
    # For StreamGenerate, we can inject the gem as a prefix to the prompt, or in the "context" field.
    # Let's try putting it in inner[2][0] (the first element of that list).
    inner = [None] * 80
    inner[0] = [prompt, 0, None, None, None, None, 0]
    inner[1] = ["en"]
    # inner[2] is the metadata array: [?, ?, ?, ...] – we can put gem in first slot.
    # In Gemini-API, the gem name is put into the model header and also in the RPC; but here we'll just pass it as a system message.
    # A simpler method: if gem is given, we can prepend it to the prompt with a separator.
    if gem:
        # Use a clear delimiter: "System: <gem instructions>\n\nUser: <prompt>"
        # This is a hack but works for many system prompts.
        full_prompt = f"System: {gem}\n\n{prompt}"
        inner[0][0] = full_prompt
    # ... rest of payload (same as before)
    inner[2] = ["", "", "", None, None, None, None, None, None, ""]
    inner[6] = [0]
    inner[7] = 1
    inner[10] = 1
    inner[11] = 0
    inner[17] = [[think_mode]]
    inner[18] = 0
    inner[27] = 1
    inner[30] = [4]
    inner[41] = [2]
    inner[53] = 0
    inner[59] = str(uuid.uuid4())
    inner[61] = []
    inner[68] = 1
    inner[79] = model_id
    outer = [None, json.dumps(inner)]
    params = {"f.req": json.dumps(outer)}
    if CONFIG.get("xsrf_token"):
        params["at"] = CONFIG["xsrf_token"]
    return urllib.parse.urlencode(params).encode()

def build_headers() -> dict:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://gemini.google.com",
        "Referer": f"https://gemini.google.com{account_prefix()}/app",
        "X-Same-Domain": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if account_prefix():
        headers["X-Goog-AuthUser"] = str(CONFIG["auth_user"])
    cookie_str, sapisid = load_cookie()
    if cookie_str:
        headers["Cookie"] = cookie_str
    if sapisid:
        headers["Authorization"] = make_sapisidhash(sapisid)
    return headers

def get_url(reqid: int) -> str:
    prefix = account_prefix()
    return (f"https://gemini.google.com{prefix}/_/BardChatUi/data/"
            f"assistant.lamda.BardFrontendService/StreamGenerate"
            f"?bl={CONFIG['gemini_bl']}&hl=en&_reqid={reqid}&rt=c")

def generate(prompt: str, model_name: str = None, gem: str = None) -> str:
    if model_name is None:
        model_name = CONFIG["default_model"]
    model_cfg = MODELS.get(model_name)
    if not model_cfg:
        raise ValueError(f"Unknown model: {model_name}")
    model_id = model_cfg["mode"]
    think_mode = model_cfg["think"]

    body = build_payload(prompt, model_id, think_mode, gem)
    reqid = int(time.time()) % 1000000
    url = get_url(reqid)
    headers = build_headers()

    proxy = CONFIG.get("proxy")
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy}) if proxy else {},
        urllib.request.HTTPSHandler(context=ctx)
    )

    last_err = None
    for attempt in range(CONFIG["retry_attempts"]):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with opener.open(req, timeout=60) as resp:
                raw = resp.read().decode()
            # Check error
            bard_err = re.search(r'BardErrorInfo\s*\[(\d+)\]', raw)
            if bard_err:
                raise RuntimeError(f"Gemini error [{bard_err.group(1)}]")
            # Extract text (same as before)
            texts = []
            for line in raw.split("\n"):
                if '"wrb.fr"' not in line or len(line) < 200:
                    continue
                try:
                    arr = json.loads(line)
                    def walk(obj):
                        if isinstance(obj, str) and len(obj) > 20:
                            texts.append(obj)
                        elif isinstance(obj, list):
                            for item in obj:
                                walk(item)
                        elif isinstance(obj, dict):
                            for v in obj.values():
                                walk(v)
                    walk(arr)
                except:
                    pass
            if texts:
                # combine and clean
                return "\n".join(texts)
            raise RuntimeError("No text extracted")
        except Exception as e:
            last_err = e
            time.sleep(CONFIG["retry_delay_sec"])
    raise RuntimeError(f"Failed after retries: {last_err}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gemini standalone with Gem support.")
    parser.add_argument("prompt", nargs="*", help="Prompt.")
    parser.add_argument("-m", "--model", default=CONFIG["default_model"], choices=list(MODELS.keys()))
    parser.add_argument("-g", "--gem", help="Gem system prompt or instructions.")
    parser.add_argument("-c", "--cookie", help="Cookie file.")
    parser.add_argument("--proxy", help="Proxy.")
    parser.add_argument("--xsrf", help="XSRF token.")
    parser.add_argument("--auth-user", help="Account number.")
    args = parser.parse_args()

    if args.cookie:
        CONFIG["cookie_file"] = args.cookie
    if args.proxy:
        CONFIG["proxy"] = args.proxy
    if args.xsrf:
        CONFIG["xsrf_token"] = args.xsrf
    if args.auth_user:
        CONFIG["auth_user"] = args.auth_user

    prompt = " ".join(args.prompt) if args.prompt else (sys.stdin.read().strip() if not sys.stdin.isatty() else input("Prompt: "))
    if not prompt:
        print("No prompt.", file=sys.stderr)
        sys.exit(1)

    try:
        response = generate(prompt, model_name=args.model, gem=args.gem)
        print(response)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()