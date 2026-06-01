#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it from https://www.python.org/downloads/."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

python backend/server.py &
SERVER_PID=$!

for _ in $(seq 1 30); do
  if python - <<'PY' >/dev/null 2>&1
import json
from urllib.request import urlopen
data = json.load(urlopen("http://127.0.0.1:8080/health", timeout=1))
raise SystemExit(0 if data.get("status") == "ok" and data.get("db") == "connected" else 1)
PY
  then
    break
  fi
  sleep 1
done

if command -v open >/dev/null 2>&1; then
  open "http://localhost:8080"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:8080"
else
  python -m webbrowser "http://localhost:8080"
fi

wait $SERVER_PID
