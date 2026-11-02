#!/usr/bin/env python3
"""Extract Mistral Bearer token from browser cookies using the session endpoint."""
import json
from pathlib import Path
from curl_cffi import requests

COOKIE_FILE = Path.home() / ".multi-ai-tokens" / "mistral_cookies.json"
TOKEN_OUT = Path.home() / ".multi-ai-tokens" / "mistral_token.txt"

with open(COOKIE_FILE) as f:
    data = json.load(f)
cookies = data.get("cookies", data if isinstance(data, list) else [])

s = requests.Session()
for c in cookies:
    s.cookies.set(c["name"], c["value"],
                  domain=c.get("domain", ".mistral.ai"),
                  path=c.get("path", "/"))

s.headers.update({
    "User-Agent": data.get("userAgent", "Mozilla/5.0 (Android 14; Mobile; rv:151.0) Gecko/151.0 Firefox/151.0"),
    "Accept": "application/json",
    "Origin": "https://chat.mistral.ai",
    "Referer": "https://chat.mistral.ai/",
})

# Hit the session endpoint to get the Bearer token
r = s.get("https://chat.mistral.ai/api/auth/session")
print(f"Status: {r.status_code}")
if r.ok:
    data = r.json()
    print(f"Keys: {list(data.keys())}")
    # The Bearer token might be in a nested field
    token = data.get("token") or data.get("accessToken") or data.get("jwt")
    if token:
        TOKEN_OUT.write_text(token)
        print(f"Token saved: {token[:40]}...")
    else:
        print("Full response:", json.dumps(data, indent=2)[:500])
        print("Token not found in response — checking cookies for session token...")
        # Fallback: use the ory_session cookie directly as token
        for c in cookies:
            if "ory_session" in c["name"]:
                TOKEN_OUT.write_text(c["value"])
                print(f"Saved ory_session cookie value as token")
                break
else:
    print(f"Response: {r.text[:300]}")