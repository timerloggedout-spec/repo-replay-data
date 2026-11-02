import os, json, subprocess, glob
from pathlib import Path

base = os.getcwd()
results = {}

for d in sorted(glob.glob("*/")):
    if not os.path.isdir(d): continue
    git = os.path.join(d, ".git")
    if not os.path.isdir(git): continue
    repo = d.rstrip("/")
    print(f"Scanning {repo}...")
    info = {"path": repo, "abs": os.path.abspath(repo)}
    
    # Git stats
    try:
        commits = subprocess.check_output(f"git -C {repo} rev-list --all --count", shell=True, text=True).strip()
        info["commits"] = int(commits)
    except:
        info["commits"] = 0
    try:
        remote = subprocess.check_output(f"git -C {repo} remote get-url origin", shell=True, text=True).strip()
        info["remote"] = remote
    except:
        info["remote"] = None
    
    # Detect lock files / primary language
    lock_files = {
        "package-lock.json": "npm ci",
        "pnpm-lock.yaml": "pnpm install --frozen-lockfile",
        "yarn.lock": "yarn install --frozen-lockfile",
        "Cargo.lock": "cargo fetch",
        "requirements.txt": "pip install -r requirements.txt",
        "pyproject.toml": "pip install -e .",
        "Gemfile.lock": "bundle install",
        "composer.lock": "composer install",
        "go.mod": "go mod download",
    }
    prep_cmd = None
    for f, cmd in lock_files.items():
        if os.path.exists(os.path.join(repo, f)):
            prep_cmd = cmd
            break
    info["prepare_cmd"] = prep_cmd
    
    # Guess test command
    test_cmd = None
    if os.path.exists(os.path.join(repo, "package.json")):
        try:
            import json as j
            with open(os.path.join(repo, "package.json")) as f:
                pkg = j.load(f)
                if "scripts" in pkg and "test" in pkg["scripts"]:
                    test_cmd = "npm test"
                elif "scripts" in pkg and "check" in pkg["scripts"]:
                    test_cmd = "npm run check"
        except: pass
    elif os.path.exists(os.path.join(repo, "Cargo.toml")):
        test_cmd = "cargo test"
    elif os.path.exists(os.path.join(repo, "pyproject.toml")) or os.path.exists(os.path.join(repo, "setup.py")):
        test_cmd = "pytest"  # common
    elif os.path.exists(os.path.join(repo, "Makefile")):
        # check for test target
        with open(os.path.join(repo, "Makefile")) as f:
            if "test:" in f.read():
                test_cmd = "make test"
    # fallback
    if not test_cmd and prep_cmd:
        # maybe the test is part of prep? but we keep generic
        test_cmd = "true"  # no test found
    info["test_cmd"] = test_cmd
    
    results[repo] = info

with open("repo_inventory.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"✅ Inventory saved to repo_inventory.json ({len(results)} repos)")