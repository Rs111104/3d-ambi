@echo off
setlocal

cd /d %~dp0

py -3 --version >nul 2>nul
if errorlevel 1 (
  python --version >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is required. Install it from https://www.python.org/downloads/.
    pause
    exit /b 1
  )
)

if not exist .venv (
  py -3 -m venv .venv || python -m venv .venv
)

if not exist .env (
  copy .env.example .env >nul
)

call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r backend\requirements.txt

start "3D Ambi Server" .venv\Scripts\python.exe backend\server.py

for /l %%i in (1,1,30) do (
  .venv\Scripts\python.exe -c "import json; from urllib.request import urlopen; data=json.load(urlopen('http://127.0.0.1:8080/health', timeout=1)); raise SystemExit(0 if data.get('status') == 'ok' and data.get('db') == 'connected' else 1)" >nul 2>nul && goto open_app
  timeout /t 1 >nul
)

:open_app
start "" http://localhost:8080
