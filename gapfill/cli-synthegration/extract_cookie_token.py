#!/usr/bin/env python3
"""Extract an API-ready token from a cookies JSON file (Puppeteer or Firefox export).
Usage: python extract_cookie_token.py [cookies_file] [--format bearer|cookie]
Output: prints token to stdout."""
import sys, json
from pathlib import Path

COOKIE_FILE = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "deepseek-cli" / "cookies_2.json")
FORMAT = sys.argv[sys.argv.index('--format')+1] if '--format' in sys.argv else 'bearer'

with open(COOKIE_FILE) as f:
    data = json.load(f)

# handle both Puppeteer array and Firefox {cookies: [...]}
cookies = data if isinstance(data, list) else data.get("cookies", [])

aws_token = None
session_id = None
for c in cookies:
    if c.get("name") == "aws-waf-token":
        aws_token = c["value"]
    elif c.get("name") == "ds_session_id":
        session_id = c["value"]

if FORMAT == "bearer":
    if aws_token:
        print(aws_token)
    else:
        sys.exit(1)
elif FORMAT == "cookie":
    if aws_token and session_id:
        print(f"aws-waf-token={aws_token}; ds_session_id={session_id}")
    else:
        sys.exit(1)