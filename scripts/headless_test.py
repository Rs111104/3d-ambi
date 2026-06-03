#!/usr/bin/env python3
"""Robust headless E2E using Playwright.

This script pre-creates or discovers a session token, injects it into the
page before navigation, and polls for the frontend test helper to start the
question flow. It then answers a few questions and fetches the result.

Requires: playwright (`pip install playwright`) and `playwright install chromium`.
"""
import asyncio
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except Exception:
    print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    raise

OUTPUT = Path(__file__).parent / "headless-output"
OUTPUT.mkdir(exist_ok=True)

BACKEND_DB = Path(__file__).parent.parent / "backend" / "data.db"


def try_create_session():
    url = "http://127.0.0.1:8080/api/session/start"
    payload = json.dumps({"name": "Headless Bot", "setId": "", "inviteToken": ""}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=4) as res:
            body = res.read().decode()
            data = json.loads(body)
            return data.get("sessionToken")
    except Exception:
        return None


def try_read_db_token():
    if not BACKEND_DB.exists():
        return None
    for _ in range(6):
        try:
            conn = sqlite3.connect(str(BACKEND_DB))
            cur = conn.execute("SELECT token FROM session_meta ORDER BY started_at DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        time.sleep(0.25)
    return None


def make_init_script(token: str) -> str:
    # Sets localStorage and polls for the page helper to begin the session.
    return f"""
    (() => {{
      try {{
        const token = "{token}";
        localStorage.setItem('ambi_session', JSON.stringify({{sessionToken: token, questionNumber: 0, maxQuestions: 10, correctCount: 0, sessionStartedAt: Date.now()}}));
        window.__ambi_injected_token = token;
        (function poll() {{
          if (window.__ambi_test && typeof window.__ambi_test.beginSessionViaToken === 'function') {{
            try {{ window.__ambi_test.beginSessionViaToken(window.__ambi_injected_token); }} catch (e) {{ console.error('beginSessionViaToken failed', e); }}
          }} else {{
            setTimeout(poll, 200);
          }}
        }})();
      }} catch (e) {{ console.error(e); }}
    }})();
    """


async def run():
    # Pre-create or discover a session token
    session_token = try_create_session()
    if not session_token:
        session_token = try_read_db_token()
    print("Using session token:", session_token)

    async with async_playwright() as p:
        # Enable GPU / WebGL flags to improve headless WebGL support so the
        # frontend can initialize its GL context in CI/headless environments.
        browser = await p.chromium.launch(headless=True, args=[
            '--use-gl=egl',
            '--enable-webgl',
            '--ignore-gpu-blocklist',
            '--enable-accelerated-2d-canvas',
            '--enable-gpu-rasterization',
            '--disable-software-rasterizer'
        ])
        context = await browser.new_context()
        page = await context.new_page()

        # Logging
        page.on("request", lambda r: print("->", r.method, r.url, getattr(r, 'post_data', None)))
        page.on("response", lambda r: print("<-", r.status, r.url))
        page.on("requestfailed", lambda r: print("!! failed", r.url, r.failure))

        async def _on_console(msg):
            try:
                values = []
                for a in msg.args:
                    try:
                        values.append(await a.json_value())
                    except Exception:
                        try:
                            values.append(a.toString())
                        except Exception:
                            values.append(str(a))
                print("[console]", msg.type, msg.text, *values)
            except Exception as e:
                print("[console handler error]", e)

        page.on("console", _on_console)
        page.on("pageerror", lambda exc: print("[pageerror]", exc))

        if session_token:
            await context.add_init_script(make_init_script(session_token))

        await page.goto("http://127.0.0.1:8080/test", timeout=60000)
        # Quick diagnostic: evaluate whether the helper exists in the page.
        try:
            helper_info = await page.evaluate("() => { try { return JSON.stringify({ has: !!window.__ambi_test, keys: window.__ambi_test ? Object.keys(window.__ambi_test) : [] }); } catch(e) { return 'eval_error:'+String(e); } }")
            print('helper_info evaluate ->', helper_info)
        except Exception as e:
            print('helper_info evaluate error', e)
        try:
            scripts = await page.evaluate("() => Array.from(document.scripts).map(s => ({src: s.src || null, inline: s.src ? null : (s.textContent||'').slice(0,240)}))")
            print('page scripts ->', scripts)
        except Exception as e:
            print('scripts eval error', e)

        # Wait for either answer buttons to appear or for the helper to run
        try:
            await page.wait_for_selector('.answer-btn', timeout=20000)
            print('Answer buttons visible')
        except Exception:
            print('No answer buttons within timeout; attempting helper invocation fallback')
            # Try to call helper directly if present
            try:
                # Give the page more time to initialize and define the helper.
                await page.wait_for_function("() => window.__ambi_test && typeof window.__ambi_test.beginSessionViaToken === 'function'", timeout=20000)
                if not session_token:
                    session_token = try_create_session() or try_read_db_token()
                if session_token:
                    await page.evaluate('(t) => window.__ambi_test.beginSessionViaToken(t)', session_token)
                    try:
                        await page.wait_for_selector('.answer-btn', timeout=10000)
                        print('Answer buttons visible after helper')
                    except Exception:
                        print('Still no answer buttons after helper')
            except Exception:
                print('Helper not available')
            # As a robust fallback (headless / no-webgl), drive session via API
            if session_token:
                print('Falling back to API-driven session flow')
                try:
                    def api_post(path, payload):
                        import urllib.request
                        req = urllib.request.Request('http://127.0.0.1:8080' + path, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=10) as r:
                            return json.loads(r.read().decode())

                    for i in range(3):
                        nxt = api_post('/api/session/next', {'sessionToken': session_token})
                        print('API next:', nxt.get('questionId'))
                        api_post('/api/session/answer', {'sessionToken': session_token, 'questionId': nxt.get('questionId'), 'answerIndex': 0, 'timeMs': 1000, 'headCompliance': 1.0})
                    completed = api_post('/api/session/complete', {'sessionToken': session_token})
                    result = api_post('/api/session/result', {'token': session_token}) if False else None
                    # /api/session/result is GET; fetch directly
                    try:
                        import urllib.request as _urlreq
                        with _urlreq.urlopen(f'http://127.0.0.1:8080/api/session/result?token={session_token}', timeout=10) as r:
                            print('API result:', json.loads(r.read().decode()))
                    except Exception as e:
                        print('Could not fetch API result:', e)
                except Exception as e:
                    print('API fallback failed:', e)

        # Try answering up to 3 questions
        answered = 0
        for _ in range(3):
            try:
                await page.wait_for_selector('.answer-btn', timeout=10000)
                buttons = await page.query_selector_all('.answer-btn')
                if not buttons:
                    break
                clicked = False
                for b in buttons:
                    disabled = await b.get_attribute('disabled')
                    if not disabled:
                        await b.click()
                        clicked = True
                        break
                if not clicked:
                    await buttons[0].click()
                answered += 1
                await page.wait_for_timeout(600)
            except Exception as e:
                print('Answering error', e)
                break

        # If we have a token, complete and fetch results
        if session_token:
            try:
                res = await page.evaluate("async (t) => { await fetch('/api/session/complete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({sessionToken: t})}).catch(()=>{}); const r = await fetch('/api/session/result?token=' + encodeURIComponent(t)); return r.ok ? await r.json() : null }", session_token)
                print('Result:', res)
            except Exception as e:
                print('Result fetch error', e)

        screenshot = OUTPUT / 'e2e.png'
        await page.screenshot(path=str(screenshot), full_page=True)
        print('Saved screenshot to', screenshot)

        await browser.close()


if __name__ == '__main__':
    asyncio.run(run())
