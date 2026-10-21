"""Takes the live screenshots for the report with Edge (playwright). Local dev apps only; test accounts."""
import os, sys, time, requests
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
U, P = "qa_shots", "QaTest#2026x"
API = "http://127.0.0.1:5001"
def shot(page, name, full=False, wait=2500, clip_h=None):
    page.wait_for_timeout(wait)
    kw = {"path": os.path.join(OUT, name + ".png")}
    if full:
        kw["full_page"] = True
        if clip_h: kw["clip"] = {"x": 0, "y": 0, "width": 1280, "height": clip_h}; kw["full_page"] = True
    page.screenshot(**kw); print("saved", name)
def login(page, base, user, pw, register=False):
    if register:
        page.goto(base + "/register"); page.fill("input[name=username]", user); page.fill("input[name=email]", user + "@example.test")
        page.fill("input[name=password]", pw); page.fill("input[name=confirm_password]", pw); page.click("button[type=submit]"); page.wait_for_timeout(1500)
    page.goto(base + "/login"); page.fill("input[name=username]", user); page.fill("input[name=password]", pw); page.click("button[type=submit]"); page.wait_for_timeout(1500)
def predict(page, base, r, t, h, months="12"):
    page.goto(base + "/predict"); page.fill("input[name=rainfall]", str(r)); page.fill("input[name=temperature]", str(t)); page.fill("input[name=humidity]", str(h))
    try: page.select_option("select[name=forecast_months]", months)
    except Exception: pass
    page.click("button[type=submit]"); page.wait_for_url("**/result", timeout=60000)
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="msedge"); ctx = b.new_context(viewport={"width": 1280, "height": 860}); page = ctx.new_page()
    # ---- A. standalone Climate app (SARIMA) on :5000
    A = "http://127.0.0.1:5000"
    page.goto(A + "/"); shot(page, "A01_climate_home", full=True, clip_h=1700)
    login(page, A, U, P, register=True)
    page.goto(A + "/dashboard"); shot(page, "A02_climate_dashboard", full=True, clip_h=1500, wait=6000)
    page.goto(A + "/predict"); shot(page, "A03_climate_predict")
    predict(page, A, 300, 27, 85); shot(page, "A04_climate_result_extreme", full=True, clip_h=2300, wait=4000)
    predict(page, A, 0, 18, 45); shot(page, "A05_climate_result_drought", full=True, clip_h=1500, wait=4000)
    page.goto(A + "/xai"); shot(page, "A06_climate_xai", full=True, clip_h=2400, wait=5000)
    page.goto(A + "/analysis"); shot(page, "A07_climate_analysis", full=True, clip_h=2400, wait=5000)
    page.goto(A + "/history"); shot(page, "A08_climate_history")
    ctx.clear_cookies()
    # ---- B. DevOps app on Kubernetes (:5100): SARIMA + LSTM + guard
    B = "http://127.0.0.1:5100"
    page.goto(B + "/"); shot(page, "B01_k8s_home", full=True, clip_h=1700)
    login(page, B, "qa_k8s", P)
    page.goto(B + "/dashboard"); shot(page, "B02_k8s_dashboard_healthy", full=True, clip_h=1500, wait=6000)
    page.goto(B + "/lstm_predict"); page.click("button[type=submit]"); page.wait_for_url("**/lstm_result", timeout=90000); shot(page, "B03_k8s_lstm_result", full=True, clip_h=2200, wait=4000)
    requests.get(API + "/fault?mode=corrupt", timeout=10); time.sleep(8)
    page.goto(B + "/dashboard"); shot(page, "B04_k8s_dashboard_DEGRADED_after_silent_fault", full=True, clip_h=1500, wait=6000)
    page.goto(A.replace("5000", "5001") + "/health/semantic") if False else None
    requests.get(API + "/fault?mode=heal", timeout=10); time.sleep(8)
    # ---- C. API JSON views
    page.goto(API + "/health/semantic"); shot(page, "C01_api_health_semantic", wait=800)
    page.goto(API + "/predict?model=auto&steps=6"); shot(page, "C02_api_predict_lstm_tier", wait=800)
    page.goto(API + "/slo"); shot(page, "C03_api_slo", wait=800)
    # ---- D. Grafana (lab login from k8s/README) with a bit-flip fault so the golden panels react
    G = "http://127.0.0.1:3000"
    page.goto(G + "/login"); page.fill("input[name=user]", "admin"); page.fill("input[name=password]", "admin"); page.click("button[type=submit]"); page.wait_for_timeout(2500)
    try: page.get_by_text("Skip").click(timeout=3000)
    except Exception: pass
    requests.get(API + "/fault?mode=bitflip", timeout=10)
    for _ in range(12): requests.get(API + "/predict?model=auto&steps=6", timeout=20); time.sleep(1.5)
    time.sleep(10)
    page.set_viewport_size({"width": 1600, "height": 1500})
    page.goto(G + "/d/climate-live/climate-ml-service-live?orgId=1&from=now-15m&to=now&kiosk"); shot(page, "D01_grafana_dashboard_live_bitflip", full=True, wait=12000)
    requests.get(API + "/fault?mode=heal", timeout=10)
    # ---- E. Prometheus
    page.set_viewport_size({"width": 1280, "height": 860})
    for i, q in enumerate(["golden_violation_total", "sum by (tier) (predict_tier_total)", "up"], 1):
        page.goto("http://127.0.0.1:9090/query?g0.expr=" + requests.utils.quote(q) + "&g0.tab=0&g0.range_input=15m"); shot(page, f"E0{i}_prometheus", wait=4000)
    b.close()
print("done")
