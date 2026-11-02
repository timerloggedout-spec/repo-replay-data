import pathlib, json

p = pathlib.Path.home() / 'deepcli-tui/tui.py'
src = p.read_text()

# 1a. Add /sessions command for filtered session list
sessions_cmd = r"""
        if user_input.lower().startswith('/sessions'):
            args = user_input[9:].strip()
            filter_test = '--test' in args
            filter_agent = '--agent' in args
            sort_by = 'recent'
            if '--relevance' in args: sort_by = 'relevance'
            all_sessions = []
            cache_dir = os.path.expanduser('~/.deepcli/session_store')
            if os.path.isdir(cache_dir):
                for f in Path(cache_dir).glob('*.json'):
                    try:
                        data = json.loads(f.read_text())
                        msgs = data if isinstance(data, list) else data.get('messages', [])
                        if msgs:
                            first_content = msgs[0].get('content','')[:100] if isinstance(msgs[0], dict) else str(msgs[0])[:100]
                            is_agent = 'agent' in first_content.lower()
                            if filter_agent and not is_agent: continue
                            if filter_test and 'test' not in f.stem and 'echo' not in first_content: continue
                            all_sessions.append((f.stem, len(msgs), first_content, f.stat().st_mtime))
                    except: pass
            if sort_by == 'relevance':
                all_sessions.sort(key=lambda x: -x[1])  # by message count
            else:
                all_sessions.sort(key=lambda x: -x[3])  # by mtime
            
            page = 0; per_page = 15
            total = len(all_sessions)
            while True:
                console.clear()
                console.print(f"[bold]📂 Sessions ({total} total, {'agent' if filter_agent else 'all'})[/]")
                start = page * per_page
                for i, (sid, count, snippet, mtime) in enumerate(all_sessions[start:start+per_page], start=start):
                    timestamp = datetime.fromtimestamp(mtime).strftime('%m-%d %H:%M')
                    console.print(f"  [yellow]{i:3d}[/] {sid[:16]}... [dim]({count} msgs, {timestamp})[/] {snippet[:60]}")
                console.print(f"\n[dim]Page {page+1}/{(total+per_page-1)//per_page}. n=next, p=prev, q=quit[/]")
                cmd = input("> ").strip().lower()
                if cmd == 'n' and (start+per_page) < total: page += 1
                elif cmd == 'p' and page > 0: page -= 1
                elif cmd == 'q': break
                else: pass
            continue
"""
src = src.replace("        if user_input.lower() == '/back':", sessions_cmd + "\n        if user_input.lower() == '/back':")

# 1b. Add /diff command to compare two child branches
diff_cmd = r"""
        if user_input.lower().startswith('/diff '):
            ids = user_input[6:].strip().split()
            if len(ids) != 2:
                console.print("[red]Usage: /diff <child_id1> <child_id2>[/]")
            else:
                m1 = next((m for m in messages if m.get('message_id','') == ids[0]), None)
                m2 = next((m for m in messages if m.get('message_id','') == ids[1]), None)
                if m1 and m2:
                    c1 = m1.get('content','')
                    c2 = m2.get('content','')
                    import difflib
                    diff = difflib.unified_diff(c1.splitlines(), c2.splitlines(), fromfile=ids[0][:8], tofile=ids[1][:8], lineterm='')
                    console.print('\n'.join(diff)[:2000])
                else:
                    console.print("[red]One or both message IDs not found.[/]")
            input("\nPress Enter to continue...")
            continue
"""
src = src.replace("        if user_input.lower() == '/back':", diff_cmd + "\n        if user_input.lower() == '/back':")

p.write_text(src)
print("TUI upgraded: /sessions (filterable), /diff for branch comparison.")