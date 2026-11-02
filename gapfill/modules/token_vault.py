import json, os, sys
from pathlib import Path

VAULT_PATHS = [
    Path.home()/"deepseek-cli/upload-api.json",
    Path.home()/"termux-multi-agent/config/tokens.json",
    Path.home()/".deepseek_api_key"
]

def load_vault(path):
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("authorization") or data.get("api_key") or data.get("token")
        return data.strip()
    except:
        return None

def get_token():
    for p in VAULT_PATHS:
        tok = load_vault(p)
        if tok:
            return tok
    return os.environ.get("DEEPSEEK_API_KEY", "")