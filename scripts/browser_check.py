"""Browser checks for what Django's test client can't see: layout, Leaflet, live HTMX swaps.

Run with the webapp-testing helper so the dev server is managed for you:

    python .claude/skills/webapp-testing/scripts/with_server.py \
        --server ".venv/bin/python manage.py runserver 8765 --noreload" --port 8765 \
        -- .venv/bin/python scripts/browser_check.py profile

Screenshots land in docs/screens/<screen>-{mobile,desktop}.png.
"""

import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screens"
WIDTHS = {"mobile": (375, 812), "desktop": (1280, 900)}


def login(page, username="demo", password="demo12345"):
    page.goto(f"{BASE}/accounts/login/")
    page.fill("input[name=login]", username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def wait_for_map(page, min_pins=1):
    page.wait_for_function(
        f"() => Number(document.querySelector('[data-diary-map]')?.dataset.pinCount || 0) >= {min_pins}",
        timeout=15000,
    )
    return int(page.eval_on_selector("[data-diary-map]", "el => el.dataset.pinCount"))


def check_profile(page, mode):
    page.goto(f"{BASE}/u/demo/")
    page.wait_for_load_state("networkidle")
    pins = wait_for_map(page, 5)
    markers = page.locator(".leaflet-marker-icon").count()
    # fitBounds: every marker should be inside the visible map box.
    inside = page.evaluate("""() => {
        const box = document.querySelector('#profile-map').getBoundingClientRect();
        return [...document.querySelectorAll('.leaflet-marker-icon')].every(m => {
            const r = m.getBoundingClientRect(); const x = r.left + r.width/2, y = r.top + r.height/2;
            return x >= box.left && x <= box.right && y >= box.top && y <= box.bottom; });
    }""")
    # Pins in the same metro area overlap at world zoom, so open one that stands alone.
    page.locator(".leaflet-marker-icon[title^='Hollywood Bowl']").click()
    page.wait_for_selector(".leaflet-popup-content")
    page.wait_for_timeout(500)  # let the popup fade in
    popup = page.inner_text(".leaflet-popup-content")
    return {"pins": pins, "markers": markers, "all_pins_in_view": inside, "popup": popup.replace("\n", " | ")}


def reseed():
    root = Path(__file__).resolve().parent.parent
    subprocess.run([str(root / ".venv/bin/python"), str(root / "manage.py"), "seed_demo", "-v0"], check=True)


def check_search(page, mode):
    page.goto(f"{BASE}/search/")
    page.wait_for_load_state("networkidle")
    wait_for_map(page, 5)
    page.locator("#id_artist").press_sequentially("japanese", delay=40)  # exercises the 300ms debounce
    page.wait_for_selector("#results li button")
    before = page.locator(".leaflet-marker-icon[title^='Union Transfer']").get_attribute("title")
    button = page.locator("#results li button[aria-label*='Union Transfer']")
    button.click()
    page.wait_for_selector("#results [role=status]:has-text('In your diary')")
    page.wait_for_function("() => document.getElementById('minimap-status').textContent.includes('Added')")
    page.wait_for_timeout(500)
    after = page.locator(".leaflet-marker-icon[title^='Union Transfer']").get_attribute("title")
    status = page.inner_text("#minimap-status")
    reloaded = page.evaluate("() => performance.getEntriesByType('navigation').length")  # still 1 page load
    return {"pin_before": before, "pin_after": after, "status": status,
            "live_update": before != after and reloaded == 1}


def check_diary(page, mode):
    page.goto(f"{BASE}/u/demo/diary/")
    page.wait_for_load_state("networkidle")
    rows_before = page.locator("#diary-list li time").count()
    page.select_option("#diary-sort", "rating")
    page.wait_for_url("**sort=rating**")
    page.wait_for_load_state("networkidle")
    first = page.locator("#diary-list li [role=img]").first.get_attribute("aria-label")
    page.select_option("#diary-year", "2023")
    page.wait_for_url("**year=2023**")
    page.wait_for_load_state("networkidle")
    rows_2023 = page.locator("#diary-list li time").count()
    page.select_option("#diary-year", "")
    page.select_option("#diary-sort", "newest")
    page.wait_for_load_state("networkidle")
    return {"rows": rows_before, "top_rated": first, "rows_2023": rows_2023,
            "live_update": rows_before == 15 and first == "5 out of 5 stars" and 0 < rows_2023 < 15}


def check_detail(page, mode):
    # Big Thief at O2 Academy Brixton starts unrated in the seed.
    page.goto(f"{BASE}/u/demo/diary/")
    page.click("text=Rate and review")
    page.wait_for_load_state("networkidle")
    page.locator(".stars label[title='4.5 stars']").click()
    page.wait_for_selector("[role=status]:has-text('Saved: 4.5 stars.')")
    # Keyboard: arrow right from 4.5 should go up to 5, the same direction the stars read.
    page.focus(".stars input:checked")
    page.keyboard.press("ArrowRight")
    page.wait_for_selector("[role=status]:has-text('Saved: 5 stars.')")
    page.mouse.move(0, 0)  # drop the hover preview before measuring
    page.wait_for_timeout(200)
    filled = page.evaluate("""() => [...document.querySelectorAll('.stars label.star')]
        .filter(l => getComputedStyle(l).backgroundColor === 'rgb(255, 201, 77)').length""")
    page.click("text=Write a review")
    page.fill("textarea[name=review]", "Brixton floor was bouncing. Front row the whole night.")
    page.click("button:has-text('Save review')")
    page.wait_for_selector("text=Review saved.")
    page.mouse.move(0, 0)
    page.wait_for_timeout(300)
    return {"filled_halves": filled, "live_update": filled == 10}


SCREENS = {
    "detail": (True, check_detail),
    "diary": (True, check_diary),
    "profile": (False, check_profile),
    "search": (True, check_search),
}


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name in names:
            needs_login, check = SCREENS[name]
            for mode, (w, h) in WIDTHS.items():
                ctx = browser.new_context(viewport={"width": w, "height": h})
                page = ctx.new_page()
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                if needs_login:
                    reseed()  # each width starts from the same diary (resets the session too)
                    login(page)
                result = check(page, mode) or {}
                overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                page.screenshot(path=str(OUT / f"{name}-{mode}.png"), full_page=True)
                ok = overflow <= 0 and not errors and all(result.get(k, True) is not False for k in ("all_pins_in_view", "live_update"))
                failures += not ok
                print(f"[{'PASS' if ok else 'FAIL'}] {name} @ {w}px  overflow={overflow}px  console_errors={errors}  {result}")
                ctx.close()
        browser.close()
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main(sys.argv[1:] or list(SCREENS))
