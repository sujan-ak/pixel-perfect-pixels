import time
import json
from playwright.sync_api import sync_playwright

def run_diagnose():
    console_messages = []
    page_errors = []
    network_responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1100})
        page = context.new_page()

        page.on("console", lambda msg: console_messages.append({
            "type": msg.type,
            "text": msg.text,
            "location": msg.location
        }))
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("response", lambda res: network_responses.append({
            "url": res.url,
            "status": res.status,
            "status_text": res.status_text
        }))

        res = page.goto("http://localhost:8080/", wait_until="networkidle")
        time.sleep(3.0)

        # 1. Console Errors
        red_errors = [m for m in console_messages if m["type"] == "error"]

        # 2. Network CartoDB Tiles
        tile_resps = [r for r in network_responses if "cartocdn.com" in r["url"]]

        # 3. Computed Height and Style of Map Container
        dom_styles = page.evaluate("""() => {
            const container = document.querySelector('.leaflet-container');
            const wrapper = document.getElementById('live-map-container') || document.querySelector('[class*="live-map"]');
            
            const getComputed = (el) => {
                if (!el) return null;
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return {
                    tagName: el.tagName,
                    id: el.id,
                    className: el.className,
                    width: rect.width,
                    height: rect.height,
                    top: rect.top,
                    left: rect.left,
                    display: style.display,
                    visibility: style.visibility,
                    position: style.position,
                    computedHeight: style.height,
                    computedWidth: style.width,
                    minHeight: style.minHeight,
                    maxHeight: style.maxHeight,
                };
            };

            return {
                leafletContainer: getComputed(container),
                mapWrapper: getComputed(wrapper),
                leafletTilesCount: document.querySelectorAll('.leaflet-tile').length,
                markersCount: document.querySelectorAll('.leaflet-marker-icon').length,
                totalLeafletElements: document.querySelectorAll('[class*="leaflet"]').length
            };
        }""")

        # 4. Leaflet CSS presence
        css_resps = [r for r in network_responses if "css" in r["url"] or "leaflet" in r["url"]]
        css_applied = page.evaluate("""() => {
            const el = document.querySelector('.leaflet-container');
            if (!el) return { found: false };
            const style = window.getComputedStyle(el);
            return {
                found: true,
                background: style.background,
                position: style.position,
                overflow: style.overflow
            };
        }""")

        # 5. Dynamic import & SSR Check
        ssr_info = page.evaluate("""() => {
            return {
                windowDefined: typeof window !== 'undefined',
                leafletGlobal: typeof window.L !== 'undefined',
                bodyHtmlLength: document.body.innerHTML.length
            };
        }""")

        report = {
            "console_errors": red_errors,
            "page_errors": page_errors,
            "tile_count": len(tile_resps),
            "sample_tiles": tile_resps[:5],
            "dom_styles": dom_styles,
            "css_resources": css_resps,
            "css_applied": css_applied,
            "ssr_info": ssr_info
        }

        with open("diagnose_output.json", "w") as f:
            json.dump(report, f, indent=2)

        browser.close()
        print("DIAGNOSTIC_COMPLETED_SUCCESSFULLY")

if __name__ == "__main__":
    run_diagnose()
