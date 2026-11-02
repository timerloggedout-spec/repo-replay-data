import os, json
from pathlib import Path

VAULT_PATH = Path.home() / ".synthegration" / "vault.json"

def _read_upload_api():
    f = Path.home() / "deepseek-cli" / "upload-api.json"
    if f.exists():
        with open(f) as fh:
            data = json.load(fh)
            return data.get("authorization")
    return None

def get_token():
    if "DEEPSEEK_TOKEN" in os.environ:
        return os.environ["DEEPSEEK_TOKEN"]
    if VAULT_PATH.exists():
        with open(VAULT_PATH) as f:
            return json.load(f).get("token")
    token = _read_upload_api()
    if token:
        VAULT_PATH.parent.mkdir(exist_ok=True)
        with open(VAULT_PATH, "w") as f:
            json.dump({"token": token}, f)
        os.chmod(VAULT_PATH, 0o600)
        return token
    return None

if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["--print"]:
        tok = get_token()
        if tok:
            print(tok)
        else:
            print("No token", file=sys.stderr)