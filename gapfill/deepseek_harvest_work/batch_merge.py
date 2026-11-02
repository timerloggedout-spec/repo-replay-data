#!/usr/bin/env python3
"""
batch_merge.py – Multi‑provider fallback code merge engine.
Tries DeepSeek → Gemini → OpenRouter → Groq → Mistral Codestral.
Records provider, model, and endpoint used in evolution_trace.md and merge_log.json.
"""
import os, sys, json, time, difflib
from pathlib import Path
from collections import defaultdict

# Ensure requests is available
try:
    import requests
except ImportError:
    os.system("pip install requests -q")
    import requests

# ----------------------------------------------------------------------
#  API key loading (supports multiple providers)
# ----------------------------------------------------------------------
def load_key(env_var, file_name=None):
    key = os.environ.get(env_var)
    if key:
        return key
    if file_name:
        kf = Path.home() / file_name
        if kf.exists():
            return kf.read_text().strip()
    return None

# Provider configurations – ordered by preference
PROVIDERS = [
    {
        "name": "DeepSeek",
        "api_key": load_key("DEEPSEEK_API_KEY", ".deepseek_api_key"),
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "payload": lambda model, messages, temp, max_tok: {
            "model": model, "messages": messages,
            "temperature": temp, "max_tokens": max_tok, "stream": False
        },
        "response_parser": lambda data: data["choices"][0]["message"]["content"],
        "rate_limit_delay": 1.5
    },
    {
        "name": "Google Gemini",
        "api_key": load_key("GEMINI_API_KEY", ".gemini_api_key"),
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "model": "gemini-2.5-flash",
        "headers": lambda key: {"Content-Type": "application/json"},
        "payload": lambda model, messages, temp, max_tok: {
            "contents": [{"parts": [{"text": messages[-1]["content"]}]}],
            "generationConfig": {"temperature": temp, "maxOutputTokens": max_tok}
        },
        "extra_params": lambda key: {"key": key},
        "response_parser": lambda data: data["candidates"][0]["content"]["parts"][0]["text"],
        "rate_limit_delay": 6.0   # 10 RPM
    },
    {
        "name": "OpenRouter",
        "api_key": load_key("OPENROUTER_API_KEY", ".openrouter_api_key"),
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model": "qwen/qwen3-coder:free",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "payload": lambda model, messages, temp, max_tok: {
            "model": model, "messages": messages,
            "temperature": temp, "max_tokens": max_tok, "stream": False
        },
        "response_parser": lambda data: data["choices"][0]["message"]["content"],
        "rate_limit_delay": 3.0
    },
    {
        "name": "Groq",
        "api_key": load_key("GROQ_API_KEY", ".groq_api_key"),
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-versatile",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "payload": lambda model, messages, temp, max_tok: {
            "model": model, "messages": messages,
            "temperature": temp, "max_tokens": max_tok, "stream": False
        },
        "response_parser": lambda data: data["choices"][0]["message"]["content"],
        "rate_limit_delay": 2.0
    },
    {
        "name": "Mistral Codestral",
        "api_key": load_key("MISTRAL_API_KEY", ".mistral_api_key"),
        "endpoint": "https://codestral.mistral.ai/v1/chat/completions",
        "model": "codestral-latest",
        "headers": lambda key: {"Authorization": f"Bearer {key}"},
        "payload": lambda model, messages, temp, max_tok: {
            "model": model, "messages": messages,
            "temperature": temp, "max_tokens": max_tok, "stream": False
        },
        "response_parser": lambda data: data["choices"][0]["message"]["content"],
        "rate_limit_delay": 2.0
    },
]

# Remove providers with no API key
PROVIDERS = [p for p in PROVIDERS if p["api_key"]]

if not PROVIDERS:
    print("❌ No API keys found. Set at least one of:")
    print("   DEEPSEEK_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY")
    print("   Or create files: ~/.deepseek_api_key, ~/.gemini_api_key, ~/.openrouter_api_key, ~/.groq_api_key, ~/.mistral_api_key")
    sys.exit(1)

print(f"🔑 Providers loaded: {', '.join(p['name'] for p in PROVIDERS)}")

# ----------------------------------------------------------------------
#  Constants
# ----------------------------------------------------------------------
TEMPERATURE = 0.1
MAX_TOKENS = 4000
SIMILARITY_THRESHOLD = 0.65

# ----------------------------------------------------------------------
#  Load manifest
# ----------------------------------------------------------------------
MANIFEST_PATH = Path("~/deepseek_harvest_work/code_harvest/manifest.json").expanduser()
if not MANIFEST_PATH.exists():
    print("❌ manifest.json not found.")
    sys.exit(1)
with open(MANIFEST_PATH) as f:
    blocks = json.load(f)
print(f"📦 Loaded {len(blocks)} code blocks.")

# ----------------------------------------------------------------------
#  Group & cluster
# ----------------------------------------------------------------------
groups = defaultdict(list)
for b in blocks:
    t = b.get("conversation_title", "Untitled")
    t = t.replace('\n', ' ').replace('\r', ' ')
    t = ''.join(c if c.isalnum() or c in ' ._-' else '_' for c in t)
    proj = ' '.join(t.split())[:80] or "untitled"
    lang = b.get("language", "text")
    groups[(proj, lang)].append(b)

def similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def cluster_blocks(blk_list):
    codes = [b["code"] for b in blk_list]
    used = [False] * len(codes)
    clusters = []
    for i in range(len(codes)):
        if used[i]: continue
        cluster = [blk_list[i]]
        used[i] = True
        for j in range(i+1, len(codes)):
            if not used[j] and similarity(codes[i], codes[j]) >= SIMILARITY_THRESHOLD:
                cluster.append(blk_list[j])
                used[j] = True
        clusters.append(cluster)
    return clusters

def pick_three(cluster):
    sorted_c = sorted(cluster, key=lambda x: x.get("message_timestamp", "0"))
    if len(sorted_c) >= 3:
        return sorted_c[0], sorted_c[len(sorted_c)//2], sorted_c[-1]
    elif len(sorted_c) == 2:
        return sorted_c[0], sorted_c[0], sorted_c[1]
    return None, None, None

# ----------------------------------------------------------------------
#  Multi‑provider API call with fallback
# ----------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are an elite software engineer. Merge three code versions using 3‑way merge, then refactor to remove all comments, "
    "placeholders, and dead code. Apply modern best practices, optimise for readability and performance. "
    "Output only the final code, no explanations, no markdown fences."
)

def try_merge(base_code, ours_code, theirs_code):
    """Try each provider in order. Return (merged_code, provider_name, model, endpoint)."""
    fence = "```"
    user_content = (
        f"Merge the following three code versions and refactor as instructed.\n\n"
        f"BASE:\n{fence}\n{base_code}\n{fence}\n"
        f"OURS:\n{fence}\n{ours_code}\n{fence}\n"
        f"THEIRS:\n{fence}\n{theirs_code}\n{fence}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]

    last_error = None
    for provider in PROVIDERS:
        name = provider["name"]
        try:
            payload = provider["payload"](provider["model"], messages, TEMPERATURE, MAX_TOKENS)
            extra = provider.get("extra_params", lambda key: {})
            params = extra(provider["api_key"])
            resp = requests.post(
                provider["endpoint"],
                headers=provider["headers"](provider["api_key"]),
                json=payload,
                params=params if params else None,
                timeout=120
            )
            if resp.status_code == 200:
                merged = provider["response_parser"](resp.json())
                return merged, name, provider["model"], provider["endpoint"]
            else:
                last_error = f"{name} HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            last_error = f"{name} exception: {str(e)[:200]}"
        # Fall through to next provider
    raise RuntimeError(f"All providers failed. Last error: {last_error}")

# ----------------------------------------------------------------------
#  Output directories & trace file
# ----------------------------------------------------------------------
OUTPUT_DIR = Path("~/deepseek_harvest_work/merged").expanduser()
OUTPUT_DIR.mkdir(exist_ok=True)
TRACE_FILE = OUTPUT_DIR / "evolution_trace.md"

with open(TRACE_FILE, "w") as f:
    f.write("# Code Evolution Trace\n\n")
    f.write(f"Session started: {time.ctime()}\n")
    f.write(f"Fallback chain: {' → '.join(p['name'] for p in PROVIDERS)}\n\n")

def append_trace(project, lang, base_blk, ours_blk, theirs_blk, merged_code, out_path,
                 provider_name, model, endpoint):
    fence = "```"
    diff = difflib.unified_diff(
        base_blk["code"].splitlines(keepends=True),
        merged_code.splitlines(keepends=True),
        fromfile='BASE', tofile='MERGED', lineterm=''
    )
    diff_text = ''.join(diff)
    entry = f"""
## {project} · {lang} · {Path(out_path).name}

**Sources:**
- **BASE** – `{base_blk['conversation_title']}` · timestamp `{base_blk['message_timestamp']}` · hash `{base_blk['code_hash']}`
- **OURS** – `{ours_blk['conversation_title']}` · timestamp `{ours_blk['message_timestamp']}` · hash `{ours_blk['code_hash']}`
- **THEIRS** – `{theirs_blk['conversation_title']}` · timestamp `{theirs_blk['message_timestamp']}` · hash `{theirs_blk['code_hash']}`

**AI Provider Used:**
- **Provider:** {provider_name}
- **Model:** {model}
- **Endpoint:** `{endpoint}`

**Merged output:** `{out_path}`

**Changes (unified diff from BASE to MERGED):**
{fence}diff
{diff_text}
{fence}
---
"""
    with open(TRACE_FILE, "a") as f:
        f.write(entry)

# ----------------------------------------------------------------------
#  Main merge loop
# ----------------------------------------------------------------------
LOG = []
merge_count = 0
provider_stats = defaultdict(int)

for (proj, lang), blk_list in groups.items():
    if len(blk_list) < 2: continue
    clusters = cluster_blocks(blk_list)
    for ci, cluster in enumerate(clusters):
        if len(cluster) < 2: continue
        base, ours, theirs = pick_three(cluster)
        if not base: continue
        print(f"🔄 Merging {proj}/{lang} cluster {ci+1} ({len(cluster)} versions)")
        try:
            merged, pname, pmodel, pendpoint = try_merge(base["code"], ours["code"], theirs["code"])
            provider_stats[pname] += 1
            # Save output file
            safe_proj = proj.replace('/', '_').replace('\\', '_')
            fname_base = Path(base.get("unique_filename", "unknown"))
            stem = fname_base.stem
            out_name = f"{stem}_merged_{base['code_hash'][:8]}_{theirs['code_hash'][:8]}.{fname_base.suffix}"
            proj_dir = OUTPUT_DIR / safe_proj
            proj_dir.mkdir(parents=True, exist_ok=True)
            out_path = proj_dir / out_name
            out_path.write_text(merged, encoding="utf-8")
            # Trace
            append_trace(proj, lang, base, ours, theirs, merged, out_path,
                         pname, pmodel, pendpoint)
            LOG.append({
                "project": proj, "language": lang,
                "base_hash": base["code_hash"], "ours_hash": ours["code_hash"], "theirs_hash": theirs["code_hash"],
                "output": str(out_path),
                "provider": pname,
                "model": pmodel,
                "endpoint": pendpoint
            })
            merge_count += 1
            print(f"   ✅ [{pname}] Saved {out_path}")
            time.sleep(1.0)
        except Exception as e:
            print(f"   ❌ Failed: {e}")

# ----------------------------------------------------------------------
#  Save logs
# ----------------------------------------------------------------------
log_path = OUTPUT_DIR / "merge_log.json"
with open(log_path, "w") as f:
    json.dump(LOG, f, indent=2, ensure_ascii=False)
print(f"\n📋 Merge log: {log_path}")
print(f"📜 Evolution trace: {TRACE_FILE}")
print(f"🎉 Batch merge complete. {merge_count} merges performed.")
print(f"📊 Provider usage: {dict(provider_stats)}")