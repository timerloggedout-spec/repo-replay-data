#!/usr/bin/env python3
"""
Automated Token Extraction via deepterm-style fetch.
No Puppeteer, no cookies — uses the account's ds_session_id to fetch a page
and extract the Bearer token from the response headers or inline JS.

Usage: python3 extract_token_bookmarklet.py <cookies.json> <account_name>
"""
import sys, json, requests, re
from pathlib import Path

def extract_token(cookies_file: str, account_name: str):
    cookies_path = Path(cookies_file)
    if not cookies_path.exists():
        print(f"❌ Cookies file not found: {cookies_file}")
        return

    with open(cookies_path) as f:
        data = json.load(f)
    cookies = data if isinstance(data, list) else data.get('cookies', [])

    ds = None
    for c in cookies:
        if c.get('name') == 'ds_session_id':
            ds = c['value']
            break
    if not ds:
        print("❌ No ds_session_id found in cookies")
        return

    # Use the cookie to get an authenticated page, then extract the token
    s = requests.Session()
    s.cookies.set('ds_session_id', ds, domain='chat.deepseek.com')
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Android 15; Mobile; rv:140.0) Gecko/140.0 Firefox/140.0',
    })

    # Fetch a page that includes the token in a script tag
    r = s.get('https://chat.deepseek.com/')
    if r.status_code != 200:
        print(f"❌ Could not fetch page: {r.status_code}")
        return

    # Search for the token in the page source
    match = re.search(r'"userToken":"([^"]+)"', r.text)
    if match:
        token = match.group(1)
        print(f"✅ Token extracted: {token[:4]}...{token[-4:]}")
        # Vault it
        vault_file = Path.home() / '.synthegration' / 'vault.json'
        vault = {}
        if vault_file.exists():
            with open(vault_file) as f:
                vault = json.load(f)
        vault[account_name] = token
        vault_file.parent.mkdir(exist_ok=True)
        with open(vault_file, 'w') as f:
            json.dump(vault, f)
        print(f"✅ Token vaulted as '{account_name}'.")
    else:
        # Fallback: use the deepterm API approach
        r2 = s.post('https://chat.deepseek.com/api/v0/chat_session/create', json={'character_id': None})
        if r2.status_code == 200:
            print("⚠️ Token not found in page source, but cookie works for API calls.")
            print("   Use the bookmarklet manually for full token extraction.")
        else:
            print("❌ Cookie rejected entirely. Export fresh cookies.")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 extract_token_bookmarklet.py <cookies.json> <account_name>")
        sys.exit(1)
    extract_token(sys.argv[1], sys.argv[2])