#!/usr/bin/env python3
"""Bootstrap a new two-week sprint file from the TWO-WEEK-IMPROVEMENT.md template.

Usage:
  python scripts/new_sprint.py --title "Sprint Name"
  python scripts/new_sprint.py --start 2026-06-02 --title "Release sprint"
"""
import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TEMPLATE = os.path.join(ROOT, "TWO-WEEK-IMPROVEMENT.md")
OUT_DIR = os.path.join(ROOT, "sprints")


def sanitize_title(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s.strip().lower())
    return s


def main():
    p = argparse.ArgumentParser(description="Bootstrap a two-week sprint file from template")
    p.add_argument("--title", "-t", help="Sprint title (optional)")
    p.add_argument("--start", "-s", help="Start date YYYY-MM-DD (default: today)")
    p.add_argument("--out", "-o", default=OUT_DIR, help="Output directory for sprint files")
    args = p.parse_args()

    if args.start:
        try:
            start = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
        except Exception:
            print("Invalid date format, use YYYY-MM-DD", file=sys.stderr)
            sys.exit(2)
    else:
        start = datetime.date.today()
    end = start + datetime.timedelta(days=13)

    title = args.title or f"Sprint {start.isoformat()}"
    safe = sanitize_title(title)
    filename = f"{start.isoformat()}-{safe}.md"

    os.makedirs(args.out, exist_ok=True)

    if not os.path.exists(TEMPLATE):
        print(f"Template not found: {TEMPLATE}", file=sys.stderr)
        sys.exit(1)

    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        tpl = fh.read()

    # Replace any line that starts with 'Sprint dates:' with the concrete dates
    tpl = re.sub(r"^Sprint dates:.*$", f"Sprint dates: {start.isoformat()} → {end.isoformat()}", tpl, flags=re.M)

    header = f"# {title}\n\nStart: {start.isoformat()}\nEnd:   {end.isoformat()}\n\n"
    out_path = os.path.join(args.out, filename)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(header + tpl)

    print(out_path)


if __name__ == "__main__":
    main()
