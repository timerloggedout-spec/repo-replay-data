#!/usr/bin/env python3
"""
gemini-wrapper – Uses the reverse‑engineered gemini-web2api library.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the gemini-web2api directory to Python's module search path
# Adjust this path if your clone is elsewhere
REPO_ROOT = Path(os.environ.get("GEMINI_REPO_ROOT", "~/refTemplates/gemini_recon/gemini-web2api")).expanduser()
sys.path.insert(0, str(REPO_ROOT))

# Now import from the gemini_web2api package (or the standalone file)
try:
    # Try importing from the package structure (gemini_web2api/__init__.py)
    from gemini_web2api.gemini import generate, generate_stream
    from gemini_web2api.models import MODELS, resolve_model
    from gemini_web2api.config import CONFIG
except ImportError:
    # Fallback: import from the single-file version (gemini_web2api.py)
    # But that file is not a package, so we need to import it as a module
    # We'll add the parent directory and import the file as a module
    sys.path.insert(0, str(REPO_ROOT.parent))
    import gemini_web2api  # this imports the standalone script, but it runs main() on import?
    # Better to use the package if available; if not, we can just use the functions
    # Let's assume the package works; if not, we'll advise to install httpx
    print("Could not import gemini_web2api package; try installing httpx or use the standalone script.", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Gemini CLI using the web2api library.")
    parser.add_argument("prompt", nargs="*", help="Your prompt.")
    parser.add_argument("-m", "--model", default="gemini-3.5-flash", choices=list(MODELS.keys()), help="Model.")
    parser.add_argument("-c", "--cookie", help="Cookie file path (overrides env).")
    parser.add_argument("--proxy", help="HTTP proxy.")
    parser.add_argument("--stream", action="store_true", help="Stream output incrementally.")
    args = parser.parse_args()

    if args.cookie:
        CONFIG["cookie_file"] = args.cookie
    if args.proxy:
        CONFIG["proxy"] = args.proxy

    if not args.prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            prompt = input("Prompt: ")
    else:
        prompt = " ".join(args.prompt)

    if not prompt:
        print("No prompt provided.", file=sys.stderr)
        sys.exit(1)

    # Resolve model ID
    model_name, mode_id, think_mode, err, _ = resolve_model(args.model)
    if err:
        print(f"Model error: {err}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.stream:
            for chunk in generate_stream(prompt, mode_id, think_mode):
                print(chunk, end="", flush=True)
            print()  # final newline
        else:
            response = generate(prompt, mode_id, think_mode)
            print(response)
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()