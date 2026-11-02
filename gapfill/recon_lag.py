#!/usr/bin/env python3
import os, sys, json, subprocess, glob, time
from collections import Counter, defaultdict
from datetime import datetime, timezone

# -------- Termux / Environment Probe --------
def probe_environment():
    print("\n🔍 [RECON] ENVIRONMENT SCAN")
    print("-" * 50)
    # Check common package managers
    tools = {
        "git": "git --version",
        "python": "python3 --version",
        "pip": "pip --version",
        "node": "node --version",
        "npm": "npm --version",
        "npx": "npx --version",
        "cargo": "cargo --version",
        "rustc": "rustc --version",
        "lua": "lua5.4 -v 2>/dev/null || lua5.3 -v 2>/dev/null || lua -v",
        "luarocks": "luarocks --version",
        "pandas": "python3 -c 'import pandas; print(pandas.__version__)' 2>/dev/null || echo NOT FOUND",
    }
    results = {}
    for name, cmd in tools.items():
        try:
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT).strip().split('\n')[0]
            results[name] = out[:60]
        except:
            results[name] = "❌ MISSING"
        print(f"  {name:10} : {results[name]}")
    
    # Storage space
    st = os.statvfs(".")
    free = (st.f_bavail * st.f_frsize) // (1024*1024)
    print(f"  free_space : {free} MB available")
    return results

# -------- Git Forensics --------
def probe_git(repo_path):
    print("\n📜 [RECON] GIT FORENSICS")
    print("-" * 50)
    os.chdir(repo_path)
    
    # Basic stats
    total = subprocess.check_output("git rev-list --all --count", shell=True, text=True).strip()
    branches = subprocess.check_output("git branch -a | wc -l", shell=True, text=True).strip()
    merges = subprocess.check_output("git log --merges --oneline | wc -l", shell=True, text=True).strip()
    authors = subprocess.check_output("git log --format='%an' | sort -u | wc -l", shell=True, text=True).strip()
    
    print(f"  total_commits   : {total}")
    print(f"  total_branches  : {branches}")
    print(f"  merge_commits   : {merges} ({(int(merges)/max(1,int(total))*100):.1f}%)")
    print(f"  unique_authors  : {authors}")
    
    # File types in latest commit
    files = subprocess.check_output("git ls-tree -r HEAD --name-only", shell=True, text=True).splitlines()
    exts = Counter([os.path.splitext(f)[-1][1:] or "no_ext" for f in files])
    print("  file_extensions : " + ", ".join([f"{k}({v})" for k, v in exts.most_common(5)]))
    
    # Detect lock files -> suggest prepare cmd
    locks = {
        "package-lock.json": "npm ci",
        "yarn.lock": "yarn install --frozen-lockfile",
        "Cargo.lock": "cargo fetch",
        "requirements.txt": "pip install -r requirements.txt",
        "pyproject.toml": "pip install -e .",
        "composer.lock": "composer install",
        "Gemfile.lock": "bundle install",
    }
    found_locks = [l for l in locks if os.path.exists(l)]
    suggestions = [locks[l] for l in found_locks if l in locks]
    print(f"  detected_locks  : {found_locks if found_locks else 'None'}")
    if suggestions:
        print(f"  ⚡ suggest_prepare : {suggestions[0]}")
    else:
        print(f"  ⚡ suggest_prepare : (none - use 'true')")

    # Recent commit sample (last 5)
    print("\n  📋 LAST 5 COMMITS (Subject & Hash):")
    recent = subprocess.check_output("git log -5 --format='%h %s'", shell=True, text=True).splitlines()
    for r in recent:
        print(f"    {r}")

    # Worst offenders - large commits (top 3 by diff size)
    print("\n  📦 LARGEST COMMITS (by patch size):")
    large = subprocess.check_output("git log --all --format='%h %s' --numstat | awk '/^[0-9]/ {add+=$1; del+=$2} /^[a-f0-9]/ && add {print add+del, hash, subj; add=del=0; hash=$0; subj=substr($0, index($0, \" \")+1)}' | sort -nr | head -3", shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    if large:
        for line in large.splitlines():
            parts = line.split(" ", 1)
            if len(parts) > 1:
                print(f"    {parts[1][:12]}... ({parts[0]} lines changed)")
    else:
        print("    (install gawk or ignore)")

    return {"total": total, "authors": authors}

# -------- Validation Sample (Dry Run) --------
def dry_validate(validate_cmd, prepare_cmd, repo_path, sample_size=3):
    print("\n⚙️  [RECON] DRY-RUN VALIDATION")
    print("-" * 50)
    print(f"  Validate Cmd : {validate_cmd}")
    print(f"  Prepare Cmd  : {prepare_cmd or '(none)'}")
    print(f"  Sample Size  : {sample_size} random commits (or recent)")
    
    try:
        # Get last N commits for quick test
        shas = subprocess.check_output(f"git log -{sample_size} --format='%H'", shell=True, text=True).splitlines()
        if not shas:
            print("  ❌ No commits found.")
            return
    except:
        print("  ❌ Git log failed.")
        return
    
    import tempfile, shutil
    passed = 0
    for sha in shas:
        with tempfile.TemporaryDirectory(prefix="recon_dry_") as tmp:
            try:
                # Checkout
                env = os.environ.copy()
                env["GIT_DIR"] = os.path.join(repo_path, ".git")
                env["GIT_WORK_TREE"] = tmp
                subprocess.run(["git", "checkout-index", "-a", f"--prefix={tmp}/"], env=env, check=True, capture_output=True)
                # Prepare
                if prepare_cmd:
                    subprocess.run(prepare_cmd, shell=True, cwd=tmp, capture_output=True, check=False)
                # Validate
                res = subprocess.run(validate_cmd, shell=True, cwd=tmp, capture_output=True, text=True)
                if res.returncode == 0:
                    passed += 1
                    print(f"    ✅ {sha[:8]} -> PASS")
                else:
                    err_preview = res.stderr[:80].replace('\n', ' ')
                    print(f"    ❌ {sha[:8]} -> FAIL (err: {err_preview}...)")
            except Exception as e:
                print(f"    ⚠️ {sha[:8]} -> ERROR ({str(e)[:50]})")
    print(f"  RESULT : {passed}/{len(shas)} passed in sample.")

# -------- Main --------
def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    validate = sys.argv[2] if len(sys.argv) > 2 else "true"
    prepare = sys.argv[3] if len(sys.argv) > 3 else ""
    
    print("🛰️  ====== PERFECT TRUNK RECON REPORT ======")
    print(f"     Target Repo : {os.path.abspath(repo)}")
    print(f"     Timestamp   : {datetime.now().isoformat()}")
    print("=" * 60)
    
    probe_environment()
    probe_git(repo)
    dry_validate(validate, prepare, repo, 3)
    
    print("\n✅ RECON complete. Analysis is safe. You can now run the builder.")
    print("💡 Suggested command:")
    suggest_prep = ""
    if os.path.exists("package-lock.json"): suggest_prep = "--prepare-cmd \"npm ci\""
    elif os.path.exists("requirements.txt"): suggest_prep = "--prepare-cmd \"pip install -r requirements.txt\""
    print(f"   python3 trunk_builder.py --source . --target ./perfect_trunk --validate-cmd \"{validate}\" {suggest_prep} --issues-source github:owner/repo")
if __name__ == "__main__":
    main()