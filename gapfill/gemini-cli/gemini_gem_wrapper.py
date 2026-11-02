#!/usr/bin/env python3
"""
Gemini CLI with full Gem support – using the reverse‑engineered Gemini-API client.
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# Add the Gemini-API source to Python path
REPO_ROOT = Path(os.environ.get("GEMINI_API_REPO", "~/refTemplates/gemini_recon/Gemini-API")).expanduser()
sys.path.insert(0, str(REPO_ROOT / "src"))

from gemini_webapi import GeminiClient, set_log_level, logger
from gemini_webapi.constants import Model

# Optional: load cookies from a file if you don't want to use browser cookies.
# We'll rely on the client's ability to auto‑detect browser cookies.

def list_gems(client):
    """Print all available gems (from the client's gem list)."""
    # The client may not have a direct list_gems; we can fetch via the web UI.
    # For now, we can note that gems are identified by their names/IDs.
    # If you have a known gem name, you can pass it as a string.
    print("To use a gem, provide its name as you see it on gemini.google.com.")
    print("Examples: 'Gemini Advanced', 'Image Generator', or a custom gem name.")
    print("You can also pass the gem ID (the long string from the URL).")

async def main_async(args):
    # Initialize the client
    # If you have cookies in a file, you can pass them via `cookies` parameter.
    # Or let it auto‑detect from your browser.
    client = GeminiClient()
    try:
        await client.init()
    except Exception as e:
        print(f"Failed to init client: {e}", file=sys.stderr)
        print("Make sure you have cookies from a logged‑in Gemini session.", file=sys.stderr)
        sys.exit(1)

    if args.list_gems:
        list_gems(client)
        await client.close()
        return

    # Determine prompt
    if args.prompt:
        prompt = " ".join(args.prompt)
    else:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        else:
            prompt = input("Prompt: ")
    if not prompt:
        print("No prompt provided.", file=sys.stderr)
        await client.close()
        sys.exit(1)

    # Choose model (optional)
    model = args.model or Model.UNSPECIFIED  # auto
    # Choose gem
    gem = args.gem or None

    try:
        if args.stream:
            async for chunk in client.generate_content_stream(
                prompt=prompt,
                model=model,
                gem=gem,
            ):
                print(chunk.text, end="", flush=True)
            print()
        else:
            response = await client.generate_content(
                prompt=prompt,
                model=model,
                gem=gem,
            )
            print(response.text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    finally:
        await client.close()

def main():
    parser = argparse.ArgumentParser(description="Gemini CLI with Gem support.")
    parser.add_argument("prompt", nargs="*", help="Your prompt.")
    parser.add_argument("-m", "--model", help="Model name (e.g., 'gemini-1.5-pro').")
    parser.add_argument("-g", "--gem", help="Gem name or ID (system prompt).")
    parser.add_argument("--stream", action="store_true", help="Stream output.")
    parser.add_argument("--list-gems", action="store_true", help="Show how to use gems.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logs.")
    args = parser.parse_args()

    if args.verbose:
        set_log_level("DEBUG")

    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()