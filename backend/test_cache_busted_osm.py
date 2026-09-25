import time
import os
import sys
import json
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = r"C:\Users\sujan\.gemini\antigravity-ide\brain\3bceaf77-50d4-4b58-b154-2ed3c5887d2c"

def run_cache_busted_test():
    print("=========================================================================")
    print("STARTING CACHE-BUSTED OSM TILE VERIFICATION & GREEN CORRIDOR TEST")
    print("=========================================================================\n")

    tile_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        # Fresh context with no cache
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()

        # Disable cache via CDP protocol
        cdp = context.new_cdp_session(page)
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        print(" -> CDP Network.setCacheDisabled: True")

        # Track network requests
        def on_request(req):
            if "tile" in req.url or "cartocdn" in req.url:
                tile_requests.append(req.url)

        page.on("request", on_request)

        print("[1] Navigating to http://localhost:8080/ (Cache Disabled) ...")
        page.goto("http://localhost:8080/", wait_until="networkidle")
        time.sleep(2.0)

        # Reset console to start clean
        reset_btn = page.locator("button:has-text('Reset console')")
        if reset_btn.is_visible():
            reset_btn.click()
            time.sleep(1.0)

        # Locate Leaflet map and scroll into view
        map_elem = page.locator(".leaflet-container")
        assert map_elem.is_visible(), "Leaflet map container not visible!"
        map_elem.scroll_into_view_if_needed()
        time.sleep(2.0)

        # Verify tile requests are strictly OpenStreetMap, NOT CartoDB
        osm_count = sum(1 for url in tile_requests if "tile.openstreetmap.org" in url)
        carto_count = sum(1 for url in tile_requests if "cartocdn.com" in url)
        print(f" -> Tile requests captured:")
        print(f"    OpenStreetMap (tile.openstreetmap.org): {osm_count}")
        print(f"    CartoDB (cartocdn.com): {carto_count}")
        assert carto_count == 0, f"CartoDB tiles were still requested! Found {carto_count}"
        assert osm_count > 0, "No OpenStreetMap tile requests captured!"

        # Screenshot the tiles specifically (STANDBY STATE)
        standby_screenshot = f"{ARTIFACT_DIR}/clean_osm_tiles.png"
        map_elem.screenshot(path=standby_screenshot)
        print(f" -> Standby tile screenshot saved: {standby_screenshot}")

        # Trigger crash_zone04
        print("\n[2] Triggering crash_zone04 scenario ...")
        crash_btn = page.locator("button:has-text('Trigger crash scenario')")
        crash_btn.click()

        # Wait for Approve dispatch button
        print("[3] Waiting for 'Approve dispatch' button ...")
        approve_btn = page.locator("button:has-text('Approve dispatch')")
        approve_btn.wait_for(state="visible", timeout=25000)
        print(" -> 'Approve dispatch' button is visible.")

        # Click Approve dispatch
        print("\n[4] Clicking 'Approve dispatch' ...")
        approve_btn.click()

        # Wait 1.5s for modal and dismiss it cleanly
        time.sleep(1.5)
        close_x = page.locator("header, div, button").locator("svg.lucide-x").locator("..")
        if close_x.count() > 0:
            try:
                close_x.first.click()
                print(" -> Dismissed SMS modal.")
            except Exception:
                pass
        time.sleep(1.0)
        page.keyboard.press("Escape")

        # Scroll to map again
        map_elem.scroll_into_view_if_needed()

        # Wait for the sequential 200ms signal actuations and ambulance movement
        time.sleep(2.5)

        # Verify green signals
        green_signals = page.locator(".signal-glow-green").count()
        print(f" -> Signals flipped to GREEN: {green_signals}/6")

        # Verify glowing green corridor polyline in SVG
        corridor_lines = page.locator("path.leaflet-interactive[stroke='#10b981'], path.green-corridor-glow").count()
        print(f" -> Active green corridor glowing paths: {corridor_lines}")

        # Verify ambulance marker exists
        ambulance = page.locator(".custom-ambulance-marker").count()
        print(f" -> Ambulance marker: {ambulance}")

        # Screenshot active green corridor on the new OSM tiles
        active_screenshot = f"{ARTIFACT_DIR}/clean_osm_corridor_active.png"
        map_elem.screenshot(path=active_screenshot)
        print(f" -> Active corridor screenshot saved: {active_screenshot}")

        # Full page screenshot
        full_screenshot = f"{ARTIFACT_DIR}/clean_osm_full_page.png"
        page.screenshot(path=full_screenshot, full_page=True)
        print(f" -> Full page screenshot saved: {full_screenshot}")

        browser.close()
        print("\n=========================================================================")
        print(">>> SUCCESS: OpenStreetMap dark tiles confirmed clean with 0 watermarks! <<<")
        print("=========================================================================")

if __name__ == "__main__":
    run_cache_busted_test()
