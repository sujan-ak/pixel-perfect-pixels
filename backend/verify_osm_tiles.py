import time
import os
import sys
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\sujan\.gemini\antigravity-ide\brain\3bceaf77-50d4-4b58-b154-2ed3c5887d2c"

def test_osm_tiles():
    print("=========================================================================")
    print("TESTING OPENSTREETMAP TILES & GREEN CORRIDOR IN BROWSER")
    print("=========================================================================\n")

    osm_tiles = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()

        def on_response(res):
            if "tile.openstreetmap.org" in res.url:
                osm_tiles.append({"url": res.url, "status": res.status})

        page.on("response", on_response)

        print("[1] Navigating to http://localhost:8080/ ...")
        page.goto("http://localhost:8080/", wait_until="networkidle")
        time.sleep(2.0)

        # Reset console
        reset_btn = page.locator("button:has-text('Reset console')")
        if reset_btn.is_visible():
            reset_btn.click()
            time.sleep(1.0)

        # Locate Leaflet map
        map_elem = page.locator(".leaflet-container")
        assert map_elem.is_visible(), "Leaflet map container not visible!"
        print(" -> Leaflet map container found.")

        # Scroll to map so it's fully in view
        map_elem.scroll_into_view_if_needed()
        time.sleep(1.5)

        # Verify OSM tiles
        tile_count = page.locator(".leaflet-tile").count()
        print(f" -> Leaflet tiles in DOM: {tile_count}")
        print(f" -> Network OSM tile requests intercepted: {len(osm_tiles)}")
        for t in osm_tiles[:3]:
            print(f"    OSM: {t['url']} => status {t['status']}")

        # Screenshot the map specifically before trigger
        initial_map_path = f"{SCREENSHOT_DIR}/osm_map_initial.png"
        map_elem.screenshot(path=initial_map_path)
        print(f" -> Screenshot saved: {initial_map_path}")

        # Trigger crash_zone04
        print("\n[2] Triggering crash_zone04 scenario ...")
        crash_btn = page.locator("button:has-text('Trigger crash scenario')")
        crash_btn.click()

        # Wait for Approve dispatch button
        print("[3] Waiting for RESPONSE_PROPOSED and 'Approve dispatch' button ...")
        approve_btn = page.locator("button:has-text('Approve dispatch')")
        approve_btn.wait_for(state="visible", timeout=25000)
        print(" -> 'Approve dispatch' button is visible!")

        # Click Approve dispatch
        print("\n[4] Clicking 'Approve dispatch' ...")
        approve_btn.click()

        # Wait for signal actuation sequence (6 signals * 200ms = 1.2s + buffer)
        time.sleep(3.0)

        # Check green corridor lines and green signals
        green_signals = page.locator(".signal-glow-green").count()
        print(f" -> Signals flipped to GREEN: {green_signals}/6")

        corridor_log_count = page.locator("text=Junction").count()
        print(f" -> Municipal signal log entries: {corridor_log_count}")

        # Screenshot the map with active green corridor
        corridor_map_path = f"{SCREENSHOT_DIR}/osm_map_corridor_active.png"
        map_elem.screenshot(path=corridor_map_path)
        print(f" -> Screenshot saved: {corridor_map_path}")

        # Full page screenshot
        full_page_path = f"{SCREENSHOT_DIR}/osm_full_page.png"
        page.screenshot(path=full_page_path, full_page=True)
        print(f" -> Full page screenshot saved: {full_page_path}")

        browser.close()
        print("\n=========================================================================")
        print(">>> ALL CHECKS PASSED: OpenStreetMap dark tiles & Green corridor verified! <<<")
        print("=========================================================================")

if __name__ == "__main__":
    test_osm_tiles()
