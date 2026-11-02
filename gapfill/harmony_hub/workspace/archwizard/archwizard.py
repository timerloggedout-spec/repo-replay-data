#!/usr/bin/env python3
"""🪄 ArchWizard – Mana-based multi-agent volley controller."""
import sqlite3, json, subprocess, sys, os, random
from pathlib import Path
from datetime import datetime

DB = Path.home() / 'termux-multi-agent' / 'local_repo.db'
ELO_FILE = Path.home() / 'harmony_hub' / 'workspace' / 'elo' / 'elo_ratings.json'

def load_mana():
    if ELO_FILE.exists():
        with open(ELO_FILE) as f:
            return json.load(f).get('ratings', {})
    return {}

def get_gr Imoire():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM run_history WHERE verdict IS NOT NULL ORDER BY timestamp DESC LIMIT 50").fetchall()
    conn.close()
    return rows

def select_caster(task_type: str) -> str:
    """Select best agent for task based on Mana (ELO)."""
    mana = load_mana()
    if not mana:
        return 'primary'
    # Sort by ELO descending, pick top
    sorted_agents = sorted(mana.items(), key=lambda x: x[1], reverse=True)
    return sorted_agents[0][0] if sorted_agents else 'primary'

def cast_spell(caster: str, goal: str, target: str):
    """Dispatch a task to a caster agent."""
    agent_script = Path.home() / 'harmony_hub' / 'workspace' / 'agent' / 'direct_task.py'
    cmd = [sys.executable, str(agent_script), caster, goal, target]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr

def volley(goal: str, target: str, rounds: int = 3):
    """Auto-volley: alternate casters, improve on each round."""
    for r in range(rounds):
        caster = select_caster('transmute')
        print(f"🪄 Round {r+1}: {caster} casts Transmute on {target}")
        success, output = cast_spell(caster, goal, target)
        if success:
            print(f"✅ Round {r+1} succeeded.")
            # Next round: review the result
            goal = f"Scry (review) the previous changes to {target} and improve them."
        else:
            print(f"❌ Round {r+1} failed. Restoring from Phylactery.")
            break
    return success

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("🪄 ArchWizard Usage: archwizard.py <goal> <target> [rounds]")
        print("   Volleys tasks between highest-Mana casters.")
        sys.exit(1)
    goal = sys.argv[1]
    target = sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    volley(goal, target, rounds)