"""Convenience runner — picks the first available backend server to run.

Usage:
  python run_server.py
  python run_server.py --path 3d-ambigram/backend/server.py
"""
import os
import runpy
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--path", "-p", help="Path to server file (relative to repo root)")
args = parser.parse_args()

candidates = [
    args.path if args.path else None,
    os.path.join("backend", "server.py"),
    os.path.join("3d-ambigram", "backend", "server.py")
]

for cand in candidates:
    if not cand:
        continue
    if os.path.exists(cand):
        print(f"Running server: {cand}")
        sys.path.insert(0, os.path.dirname(cand))
        runpy.run_path(cand, run_name="__main__")
        sys.exit(0)

print("No backend server file found. Checked:")
for c in candidates:
    if c:
        print(" - ", c)
sys.exit(2)
