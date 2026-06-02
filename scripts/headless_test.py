#!/usr/bin/env python3
"""Headless UI check using Playwright.

This script runs a headless Chromium, opens the homepage, captures console errors, and saves a screenshot.

Requires: playwright (`pip install playwright`) and `playwright install chromium`.
"""
import asyncio
import sys
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except Exception as e:
    print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    sys.exit(2)

OUTPUT = Path(__file__).parent / "headless-output"
OUTPUT.mkdir(exist_ok=True)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        errors = []

        page.on("console", lambda msg: errors.append((msg.type, msg.text)))
        page.on("pageerror", lambda exc: errors.append(("pageerror", str(exc))))

        url = "http://127.0.0.1:8080/test"
        print("Opening", url)
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(2500)
        screenshot_path = OUTPUT / "homepage.png"
        await page.screenshot(path=str(screenshot_path))
        print("Screenshot saved to", screenshot_path)

        if errors:
            print("Console / page errors:")
            for t, text in errors:
                print(f"[{t}] {text}")
        else:
            print("No console errors detected.")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
