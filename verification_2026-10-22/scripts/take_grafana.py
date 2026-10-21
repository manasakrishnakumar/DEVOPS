import os, sys, time, requests
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]; API = "http://127.0.0.1:5001"; G = "http://127.0.0.1:3000"
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge"); ctx = b.new_context(viewport={"width": 1600, "height": 2300}); page = ctx.new_page()
    page.goto(G + "/login"); page.fill("input[name=user]", "admin"); page.fill("input[name=password]", "admin"); page.click("button[type=submit]"); page.wait_for_timeout(2500)
    try: page.get_by_text("Skip").click(timeout=3000)
    except Exception: pass
    requests.get(API + "/fault?mode=bitflip", timeout=10)
    for _ in range(14): requests.get(API + "/predict?model=auto&steps=6", timeout=20); time.sleep(1.2)
    time.sleep(12)
    page.goto(G + "/d/climate-live/climate-ml-service-live?orgId=1&from=now-15m&to=now&refresh=5s")
    page.wait_for_timeout(15000)
    page.screenshot(path=os.path.join(OUT, "D01_grafana_dashboard_live_bitflip.png"))
    requests.get(API + "/fault?mode=heal", timeout=10); b.close()
print("saved")
