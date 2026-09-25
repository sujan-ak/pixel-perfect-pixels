import time
import os
import sys
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\sujan\.gemini\antigravity-ide\brain\3bceaf77-50d4-4b58-b154-2ed3c5887d2c"

def run_visual_verification():
    print("=========================================================================")
    print("STARTING LIVEMAP VISUAL VERIFICATION & GREEN CORRIDOR ACTUATION TEST")
    print("=========================================================================\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()

        print("[1] Navigating to http://localhost:8080/ ...")
        page.goto("http://localhost:8080/", wait_until="networkidle")
        time.sleep(2.0)

        # Reset console to start from pristine baseline
        reset_btn = page.locator("button:has-text('Reset console')")
        if reset_btn.is_visible():
            reset_btn.click()
            time.sleep(1.0)

        # 1. Verify Leaflet map container & tiles
        map_elem = page.locator(".leaflet-container")
        assert map_elem.is_visible(), "Leaflet container not visible!"
        print(" -> Leaflet map container detected and visible.")

        # Check for loaded tile images
        tile_count = page.locator(".leaflet-tile").count()
        print(f" -> CartoDB dark tiles rendered: {tile_count} tiles in DOM.")
        assert tile_count > 0, "No map tiles rendered (blank map)!"

        # Check for 4 camera zone markers
        zone_markers = page.locator(".custom-zone-marker").count()
        print(f" -> Camera Zone markers detected: {zone_markers}")
        assert zone_markers >= 4, f"Expected 4 camera zone markers, found {zone_markers}"

        # Check for hospital & fire markers
        hosp = page.locator(".custom-hospital-marker").count()
        fire = page.locator(".custom-fire-marker").count()
        print(f" -> Hospital marker: {hosp} | Fire station marker: {fire}")

        # Check for 6 initial red traffic signals
        signals = page.locator(".custom-signal-marker").count()
        red_signals = page.locator(".signal-glow-red").count()
        print(f" -> Traffic signal markers: {signals} total, {red_signals} currently RED.")
        assert signals == 6, f"Expected 6 traffic signals, found {signals}"
        assert red_signals == 6, f"Expected all 6 traffic signals to be RED initially, found {red_signals}"

        # Check for honesty label in Signal Actuation Log
        honesty_label = page.locator("text=SIMULATED MUNICIPAL SIGNAL API")
        assert honesty_label.is_visible(), "Mandatory SIMULATED MUNICIPAL SIGNAL API label not visible!"
        print(" -> Mandatory honesty badge 'SIMULATED MUNICIPAL SIGNAL API' confirmed.")

        # Capture initial map screenshot
        initial_shot = os.path.join(SCREENSHOT_DIR, "p6_map_initial_standby.png")
        page.screenshot(path=initial_shot)
        print(f" -> Saved initial map screenshot: {initial_shot}")

        # 2. Trigger crash scenario
        print("\n[2] Clicking 'Trigger crash scenario' ...")
        trigger_btn = page.locator("button:has-text('Trigger crash scenario')")
        trigger_btn.click()

        # 3. Wait for RESPONSE_PROPOSED and Approve button
        print("\n[3] Waiting for dual agents to adjudicate and reach RESPONSE_PROPOSED ...")
        approve_btn = page.locator("button:has-text('Approve dispatch')")
        approve_btn.wait_for(state="visible", timeout=25000)
        print(" -> Incident reached RESPONSE_PROPOSED! 'Approve dispatch' button is visible.")

        # 4. Scroll to map so it's fully in viewport
        map_elem.scroll_into_view_if_needed()
        time.sleep(1.0)

        # 5. Click Approve dispatch
        print("\n[4] Clicking 'Approve dispatch' ...")
        approve_btn.click()

        # 6. Observe sequential 200ms signal actuation
        print("\n[5] Observing sequential 200ms green corridor actuation...")
        # Check green signals flipping
        green_signals = 0
        for wait_step in range(35):
            green_signals = page.locator(".signal-glow-green").count()
            if green_signals > 0:
                print(f"    [t+{wait_step * 200}ms] Green signals active: {green_signals} / 6")
            if green_signals == 6:
                break
            time.sleep(0.2)

        assert green_signals == 6, f"Expected all 6 signals to turn green, found {green_signals}"
        print(" -> All 6 traffic signals flipped RED -> GREEN in sequence!")

        # 7. Check for glowing green corridor polyline
        glow_poly = page.locator(".green-corridor-glow")
        assert glow_poly.count() > 0, "Green corridor glowing polyline not rendered!"
        print(" -> Glowing green polyline successfully rendered on map.")

        # 8. Check for GREEN CORRIDOR ACTIVE banner
        active_badge = page.locator("text=GREEN CORRIDOR ACTIVE · EST. TIME SAVED: 4 MIN 20 SEC")
        assert active_badge.is_visible(), "Green corridor active banner not visible!"
        print(" -> Banner verified: 'GREEN CORRIDOR ACTIVE · EST. TIME SAVED: 4 MIN 20 SEC'")

        # 9. Verify ambulance icon is animating along the route
        ambulance = page.locator(".custom-ambulance-marker")
        assert ambulance.is_visible(), "Ambulance icon not visible on map!"
        print(" -> Ambulance icon appeared with emergency beacon effect.")

        # Sample position over time to verify actual movement (not static/teleporting)
        pos1 = ambulance.bounding_box()
        time.sleep(2.0)
        pos2 = ambulance.bounding_box()
        print(f" -> Ambulance position at t=0s: ({pos1['x']:.1f}, {pos1['y']:.1f})")
        print(f" -> Ambulance position at t=2s: ({pos2['x']:.1f}, {pos2['y']:.1f})")
        dist_moved = ((pos2['x'] - pos1['x'])**2 + (pos2['y'] - pos1['y'])**2)**0.5
        assert dist_moved > 5.0, f"Ambulance did not animate along route! Dist moved: {dist_moved}"
        print(f" -> VERIFIED: Ambulance smoothly animating along polyline! (Moved {dist_moved:.1f}px in 2s)")

        # Capture active corridor & ambulance screenshot
        active_shot = os.path.join(SCREENSHOT_DIR, "p6_green_corridor_active.png")
        page.screenshot(path=active_shot)
        print(f" -> Saved active corridor screenshot: {active_shot}")

        # 10. Check Signal Actuation Log panel
        log_entries = page.locator(".border-signal-verified\\/40").count()
        print(f" -> Signal Actuation Log entries recorded: {log_entries} / 6")
        assert log_entries >= 6, f"Expected at least 6 actuation logs, found {log_entries}"

        # Wait for ambulance to arrive at hospital
        time.sleep(3.5)

        # Full page screenshot
        full_shot = os.path.join(SCREENSHOT_DIR, "p6_full_control_room_verified.png")
        page.screenshot(path=full_shot, full_page=True)
        print(f" -> Saved full control room screenshot: {full_shot}")

        browser.close()
        print("\n=========================================================================")
        print(">>> ALL LIVEMAP & GREEN CORRIDOR VISUAL TESTS PASSED 100%! <<<")
        print("=========================================================================")

if __name__ == "__main__":
    run_visual_verification()
