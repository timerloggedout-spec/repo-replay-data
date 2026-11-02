#!/usr/bin/env python3
import os, sys, json, re, time, subprocess, tempfile, shutil, argparse
from datetime import datetime, timezone
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import requests
from dateutil.parser import parse as parse_date

CHECKPOINT_FILE = ".perfect_sync.state"
CACHE_FILE = ".issue_cache.json"

@dataclass
class Issue:
    id: str
    title: str
    state: str
    created_at: datetime
    closed_at: Optional[datetime]
    url: str
    body: str = ""

@dataclass
class LagEntry:
    type: str
    ref: str
    summary: str
    detail: str = ""

class TrunkBuilder:
    def __init__(self, src, tgt, validate_cmd, prepare_cmd, issues_source, token, since_date):
        self.src = os.path.abspath(src)
        self.tgt = os.path.abspath(tgt)
        self.validate_cmd = validate_cmd
        self.prepare_cmd = prepare_cmd
        self.issues_source = issues_source
        self.token = token
        self.since = parse_date(since_date) if since_date else None
        self.issues: List[Issue] = []
        self.commit_list = []
        self.checkpoint = self._load_checkpoint()
        self.cached_issues = self._load_cache()
        self.default_branch = self._get_default_branch()

    def _get_default_branch(self):
        try:
            out = subprocess.check_output(["git", "-C", self.src, "symbolic-ref", "HEAD"], text=True).strip()
            return out.replace("refs/heads/", "")
        except:
            for branch in ["main", "master"]:
                try:
                    subprocess.check_output(["git", "-C", self.src, "rev-parse", "--verify", branch], stderr=subprocess.DEVNULL)
                    return branch
                except:
                    continue
            return "main"

    def _run_git(self, *args, cwd=None, capture=True):
        cwd = cwd or self.src
        cmd = ["git", "-C", cwd] + list(args)
        res = subprocess.run(cmd, capture_output=capture, text=True)
        if res.returncode != 0 and capture:
            raise RuntimeError(f"Git error: {res.stderr}")
        return res.stdout.strip() if capture else res

    def _load_checkpoint(self):
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE) as f:
                return json.load(f)
        return {"last_sha": None, "last_issue_time": None}

    def _save_checkpoint(self, sha, issue_time=None):
        self.checkpoint["last_sha"] = sha
        if issue_time:
            self.checkpoint["last_issue_time"] = issue_time.isoformat()
        with open(CHECKPOINT_FILE, "w") as f:
            json.dump(self.checkpoint, f)

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cached_issues, f)

    def fetch_issues(self):
        if not self.issues_source:
            return
        print("📥 Fetching issues from:", self.issues_source)
        if self.issues_source.startswith("github:"):
            repo = self.issues_source.split(":", 1)[1]
            url = f"https://api.github.com/repos/{repo}/issues"
            headers = {"Accept": "application/vnd.github+json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            params = {"state": "all", "per_page": 100, "sort": "updated"}
            if self.since:
                params["since"] = self.since.isoformat()
            page = 1
            while True:
                params["page"] = page
                resp = requests.get(url, headers=headers, params=params, timeout=30)
                if resp.status_code == 403 and "X-RateLimit-Remaining" in resp.headers and int(resp.headers["X-RateLimit-Remaining"]) == 0:
                    reset = int(resp.headers["X-RateLimit-Reset"])
                    sleep = max(1, reset - time.time())
                    print(f"⏳ Rate limit, sleeping {sleep:.0f}s...")
                    time.sleep(sleep)
                    continue
                if resp.status_code != 200:
                    print(f"⚠️  Failed to fetch issues: {resp.status_code} - {resp.text}")
                    break
                data = resp.json()
                if not data:
                    break
                for item in data:
                    if "pull_request" in item:
                        continue
                    issue = Issue(
                        id=str(item["number"]),
                        title=item["title"],
                        state=item["state"],
                        created_at=parse_date(item["created_at"]),
                        closed_at=parse_date(item["closed_at"]) if item["closed_at"] else None,
                        url=item["html_url"],
                        body=item.get("body", "")
                    )
                    self.issues.append(issue)
                page += 1
                if len(data) < params["per_page"]:
                    break
            print(f"✅ Fetched {len(self.issues)} issues")
            self._save_cache()
        else:
            print("⚠️  Only 'github:owner/repo' is supported. Skipping issues.")

    def get_commits(self):
        # Get all commits in chronological order (oldest first)
        out = self._run_git("log", "--all", "--reverse", "--format=%H %ct %an %ae %at %s")
        if not out:
            print("⚠️  No commits found. Is the repo empty?")
            return
        for line in out.splitlines():
            # 6 fields: hash, committer time, author name, author email, author time, subject
            parts = line.split(" ", 5)
            if len(parts) < 6:
                continue
            sha, ct, name, email, uts, subject = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
            dt = datetime.fromtimestamp(int(uts), tz=timezone.utc)
            # resume from checkpoint
            if self.checkpoint["last_sha"] and sha == self.checkpoint["last_sha"]:
                self.commit_list = []
                continue
            self.commit_list.append((sha, dt, name, email, subject))
        print(f"📜 Found {len(self.commit_list)} commits to process")

    def snapshot_tree(self, sha) -> Tuple[str, str]:
        tree = self._run_git("show", "-s", "--format=%T", sha)
        author = self._run_git("show", "-s", "--format=%an <%ae> %ad", sha)
        return tree, author

    def validate_commit(self, sha):
        with tempfile.TemporaryDirectory(prefix="trunk_val_") as tmp:
            self._run_git("checkout-index", "-a", f"--prefix={tmp}/", capture=False)
            if self.prepare_cmd:
                subprocess.run(self.prepare_cmd, shell=True, cwd=tmp, capture_output=True, text=True)
            res = subprocess.run(self.validate_cmd, shell=True, cwd=tmp, capture_output=True, text=True)
            return res.returncode == 0, res.stdout[:200] + "..." if len(res.stdout) > 200 else res.stdout, res.stderr[:200] + "..." if len(res.stderr) > 200 else res.stderr

    def build_perfect_trunk(self):
        os.makedirs(self.tgt, exist_ok=True)
        if not os.listdir(self.tgt):
            subprocess.run(["git", "init", "--bare", self.tgt], check=True, capture_output=True)
        else:
            if not os.path.exists(os.path.join(self.tgt, "HEAD")):
                raise RuntimeError(f"Target {self.tgt} exists but is not a Git repository.")

        work_tgt = self.tgt + "_work"
        if os.path.exists(work_tgt):
            shutil.rmtree(work_tgt)
        subprocess.run(["git", "clone", self.tgt, work_tgt], check=True, capture_output=True)
        os.chdir(work_tgt)

        # ensure initial commit exists
        if subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True).returncode != 0:
            with open("README.md", "w") as f:
                f.write("# Perfect Trunk\n")
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "root"], check=True)
            subprocess.run(["git", "push", "origin", self.default_branch], check=True, capture_output=True)
        else:
            subprocess.run(["git", "checkout", self.default_branch], check=True)

        parent = None
        lag_pool = []
        valid_count = 0
        manifest = []

        for sha, dt, name, email, subject in self.commit_list:
            print(f"⏳ Processing {sha[:8]} - {subject[:40]}...")
            ok, stdout, stderr = self.validate_commit(sha)
            if ok:
                lag_str = ""
                if lag_pool:
                    lag_str = "[LAG BLOCK]\n"
                    for entry in lag_pool:
                        if entry.type == "broken":
                            lag_str += f"  - BROKEN {entry.ref}: {entry.summary}\n"
                        elif entry.type == "issue":
                            lag_str += f"  - ISSUE {entry.ref}: {entry.summary}\n"
                    lag_str += "\n"
                lag_pool = []

                tree, author = self.snapshot_tree(sha)
                if parent:
                    cmd = ["git", "commit-tree", tree, "-p", parent, "-m", f"[VALID] {subject}\n\n{lag_str}[ORIGINAL] {sha}\n[AUTHOR] {author}\n[VALIDATION] ok\n{stderr}"]
                else:
                    cmd = ["git", "commit-tree", tree, "-m", f"[VALID] {subject}\n\n{lag_str}[ORIGINAL] {sha}\n[AUTHOR] {author}\n[VALIDATION] ok\n{stderr}"]
                new_sha = subprocess.check_output(cmd, text=True).strip()
                subprocess.run(["git", "update-ref", f"refs/heads/{self.default_branch}", new_sha], check=True)
                parent = new_sha
                valid_count += 1
                manifest.append({
                    "new_hash": new_sha,
                    "source_hash": sha,
                    "skipped_commits": [e.ref for e in lag_pool if e.type == "broken"],
                    "linked_issues": [e.ref for e in lag_pool if e.type == "issue"]
                })
                subprocess.run(["git", "push", "origin", self.default_branch], check=True, capture_output=True)
                self._save_checkpoint(sha, dt)
                print(f"✅ Valid commit {new_sha[:8]} (source {sha[:8]})")
            else:
                lag_pool.append(LagEntry("broken", sha[:8], subject, stderr))
                # look for issue references in subject
                found = re.findall(r'#(\d+)', subject)
                for num in found:
                    issue = next((i for i in self.issues if i.id == num), None)
                    if issue:
                        lag_pool.append(LagEntry("issue", f"#{issue.id}", issue.title, issue.url))
                print(f"❌ Broken commit {sha[:8]} added to lag pool")

        with open(os.path.join(self.tgt, "lag_manifest.ndjson"), "w") as f:
            for entry in manifest:
                f.write(json.dumps(entry) + "\n")
        print(f"🎉 Done! Created {valid_count} valid commits. Manifest at {self.tgt}/lag_manifest.ndjson")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--validate-cmd", required=True)
    parser.add_argument("--prepare-cmd", default="")
    parser.add_argument("--issues-source", default="")
    parser.add_argument("--issues-token", default="")
    parser.add_argument("--since-date", default="")
    args = parser.parse_args()
    builder = TrunkBuilder(args.source, args.target, args.validate_cmd, args.prepare_cmd,
                           args.issues_source, args.issues_token, args.since_date)
    builder.fetch_issues()
    builder.get_commits()
    if builder.commit_list:
        builder.build_perfect_trunk()
    else:
        print("⚠️  No commits to process. Exiting.")

if __name__ == "__main__":
    main()