import os, json, subprocess, glob
from pathlib import Path

base = os.getcwd()
results = {}

for d in sorted(glob.glob("*/")):
    repo = d.rstrip("/")
    if not os.path.isdir(os.path.join(repo, ".git")):
        continue
    print(f"🔎 Scanning {repo}...")
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

    # Detect prepare command (lock files)
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

    # -------- Smart test detection --------
    test_cmd = None

    # 1. package.json
    pkg_path = os.path.join(repo, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path) as f:
                pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                # prefer "test", then "test:ci", then any key with "test"
                candidates = [k for k in scripts.keys() if "test" in k.lower()]
                if candidates:
                    # pick the shortest (often "test") or first
                    candidates.sort(key=len)
                    test_cmd = f"npm run {candidates[0]}"
                elif "lint" in scripts:
                    test_cmd = f"npm run lint"   # fallback to lint
                elif "check" in scripts:
                    test_cmd = f"npm run check"
        except:
            pass

    # 2. Gradle (Haven, etc.)
    if not test_cmd and os.path.exists(os.path.join(repo, "gradlew")):
        test_cmd = "./gradlew test --no-daemon"
        # if no prepare, set a default
        if not prep_cmd:
            prep_cmd = "./gradlew assemble --no-daemon"

    # 3. Rust
    if not test_cmd and os.path.exists(os.path.join(repo, "Cargo.toml")):
        test_cmd = "cargo test"

    # 4. Python
    if not test_cmd and (os.path.exists(os.path.join(repo, "pyproject.toml")) or 
                         os.path.exists(os.path.join(repo, "setup.py"))):
        # check for pytest.ini or tox.ini
        if os.path.exists(os.path.join(repo, "pytest.ini")) or os.path.exists(os.path.join(repo, "tox.ini")):
            test_cmd = "pytest"
        else:
            # fallback to unittest discovery if there is a tests/ dir
            if os.path.exists(os.path.join(repo, "tests")):
                test_cmd = "python -m unittest discover -s tests"
            elif os.path.exists(os.path.join(repo, "test")):
                test_cmd = "python -m unittest discover -s test"

    # 5. Makefile with test target
    if not test_cmd and os.path.exists(os.path.join(repo, "Makefile")):
        with open(os.path.join(repo, "Makefile")) as f:
            if "test:" in f.read():
                test_cmd = "make test"

    # 6. Fallback: if there is a test/ or tests/ directory, suggest a generic command
    if not test_cmd:
        if os.path.exists(os.path.join(repo, "tests")):
            test_cmd = "echo 'No test runner detected, but tests/ exists'"
        elif os.path.exists(os.path.join(repo, "test")):
            test_cmd = "echo 'No test runner detected, but test/ exists'"

    # if still nothing, mark as "true" (we'll skip)
    if not test_cmd:
        test_cmd = "true"

    info["test_cmd"] = test_cmd

    results[repo] = info

with open("repo_inventory_deep.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"✅ Deep inventory saved to repo_inventory_deep.json ({len(results)} repos)")