#!/usr/bin/env python3
"""List messages in a session with IDs for branch/fork selection.
Usage: list_messages.py <session_id> [--search <term>] [--after <id>] [--limit <n>]"""
import sys, json; from pathlib import Path
HOME = Path.home()
sys.path.insert(0, str(HOME/'deepcli'))
from deepcli.core import get_token, get_history

sid = sys.argv[1] if len(sys.argv) > 1 else "e102d768-8a47-4001-95cb-14fb6245c6fa"
search = None; after_id = None; limit = 20
args = sys.argv[2:]
i = 0
while i < len(args):
    if args[i] == '--search' and i+1 < len(args):
        search = args[i+1].lower(); i += 2
    elif args[i] == '--after' and i+1 < len(args):
        after_id = args[i+1]; i += 2
    elif args[i] == '--limit' and i+1 < len(args):
        limit = int(args[i+1]); i += 2
    else: i += 1

msgs = get_history(get_token(), sid)
count = 0
for m in msgs:
    mid = str(m.get('message_id','?'))
    if after_id and int(mid) <= int(after_id): continue
    content = (m.get('content','') or '')[:80].replace('\n',' ')
    if search and search not in content.lower(): continue
    print(f"{mid:>4} | {m.get('role','?'):9} | {content}")
    count += 1
    if count >= limit: break
print(f"\n--- {count} messages shown (session {sid[:8]}...) ---")