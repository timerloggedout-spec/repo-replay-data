#!/usr/bin/env python3
"""
CPR – CEDARscript Pointer Registry
Replaces long CEDARscript commands with short, hash-like pointers.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Optional, Any

try:
    from cedarscript_editor import CEDARScriptEditor, CEDARScriptASTParser
    HAS_CEDAR = True
except ImportError:
    HAS_CEDAR = False
    import sys
    print("Warning: cedarscript_editor not found", file=sys.stderr)

class CEDARPointerRegistry:
    POINTER_PREFIX = "→"
    HASH_LEN = 4
    REGISTRY_PATH = Path.home() / ".cedar" / "command_registry.json"

    def __init__(self, registry_file: Path = None):
        self.registry_file = registry_file or self.REGISTRY_PATH
        self._ptr_to_cmd = {}
        self._cmd_to_ptr = {}
        self._load()

    def _load(self):
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                data = json.load(f)
                self._ptr_to_cmd = data.get("ptr_to_cmd", {})
                self._cmd_to_ptr = data.get("cmd_to_ptr", {})
        else:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            self._save()

    def _save(self):
        with open(self.registry_file, 'w') as f:
            json.dump({"ptr_to_cmd": self._ptr_to_cmd, "cmd_to_ptr": self._cmd_to_ptr}, f, indent=2)

    def _normalize(self, cmd: str) -> str:
        return ' '.join(cmd.split())

    def _generate_pointer(self, cmd: str) -> str:
        norm = self._normalize(cmd)
        h = hashlib.sha256(norm.encode()).digest()
        num = int.from_bytes(h[:8], 'big')
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
        base36 = ""
        while num > 0:
            num, rem = divmod(num, 36)
            base36 = alphabet[rem] + base36
        ptr = (base36[:self.HASH_LEN]).ljust(self.HASH_LEN, '0')
        return f"{self.POINTER_PREFIX}{ptr}"

    def register(self, cmd: str) -> str:
        norm = self._normalize(cmd)
        if norm in self._cmd_to_ptr:
            return self._cmd_to_ptr[norm]
        ptr = self._generate_pointer(cmd)
        collision = 0
        while ptr in self._ptr_to_cmd and self._ptr_to_cmd[ptr] != norm:
            collision += 1
            ptr = self._generate_pointer(f"{cmd}{collision}")
        self._ptr_to_cmd[ptr] = norm
        self._cmd_to_ptr[norm] = ptr
        self._save()
        return ptr

    def compress(self, cmd: str) -> str:
        return self.register(cmd)

    def expand(self, pointer: str) -> Optional[str]:
        if not pointer.startswith(self.POINTER_PREFIX):
            return None
        return self._ptr_to_cmd.get(pointer)

    def resolve_in_text(self, text: str) -> str:
        pattern = re.escape(self.POINTER_PREFIX) + r'([a-z0-9]{' + str(self.HASH_LEN) + r'})'
        def repl(m):
            ptr = self.POINTER_PREFIX + m.group(1)
            return self.expand(ptr) or ptr
        return re.sub(pattern, repl, text)

    def execute(self, pointer_or_cmd: str, root_path: str = ".", dry_run: bool = False) -> Dict[str, Any]:
        if not HAS_CEDAR:
            return {"error": "cedarscript_editor not installed"}
        cmd = self.expand(pointer_or_cmd)
        if cmd is None:
            cmd = pointer_or_cmd
        parser = CEDARScriptASTParser()
        commands, errors = parser.parse_script(cmd)
        if errors:
            return {"error": errors, "raw": cmd}
        if dry_run:
            return {"dry_run": True, "commands": [str(c) for c in commands], "raw": cmd}
        editor = CEDARScriptEditor(root_path=root_path)
        editor.apply_commands(commands)
        return {"success": True, "raw": cmd}

if __name__ == "__main__":
    import sys
    cpr = CEDARPointerRegistry()
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith(CEDARPointerRegistry.POINTER_PREFIX):
            cmd = cpr.expand(arg)
            print(f"Expanded: {cmd}")
            if len(sys.argv) > 2 and sys.argv[2] == "--exec":
                res = cpr.execute(arg)
                print(f"Result: {res}")
        else:
            ptr = cpr.compress(arg)
            print(f"Pointer: {ptr}")
    else:
        print("CPR - CEDARscript Pointer Registry")
        while True:
            inp = input("> ").strip()
            if inp in ("exit","quit"): break
            if inp.startswith("→"):
                print(cpr.expand(inp))
            else:
                print(cpr.compress(inp))