#!/usr/bin/env python3
"""Run the backend server from the repo root.

This wrapper lets you run `python server.py` at the repository root and
will pick the first available backend/server.py in sensible locations.
"""
import os
import runpy
import sys

ROOT = os.path.abspath(os.path.dirname(__file__))
CANDIDATES = [
    os.path.join(ROOT, "backend", "server.py"),
    os.path.join(ROOT, "3d-ambigram", "backend", "server.py")
]

for path in CANDIDATES:
    if os.path.exists(path):
        print(f"Running server: {os.path.relpath(path, ROOT)}")
        runpy.run_path(path, run_name="__main__")
        sys.exit(0)

print("No backend server file found. Checked:")
for p in CANDIDATES:
    print(" -", p)
sys.exit(2)
