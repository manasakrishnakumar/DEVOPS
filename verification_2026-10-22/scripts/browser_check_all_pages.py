"""Visits EVERY page of both web apps, the inference API, Grafana and Prometheus in a real browser (Edge via playwright), saves a screenshot
of each, and records HTTP status, page title, visible error text, JavaScript console errors and failed sub-requests.
Local development apps only; test accounts. Needs: monolith app on :5000, frontend on :5100 (port-forward), inference API on :5001,
Grafana on :3000, Prometheus on :9090.
    python browser_check_all_pages.py <out_dir>
"""
import json
import os
import sys
import time

import requests
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
SHOTS = os.path.join(OUT, 'screenshots')
os.makedirs(SHOTS, exist_ok=True)
U, P = 'qa_final', 'QaTest#2026x'
API = 'http://127.0.0.1:5001'
BAD = ('Internal Server Error', 'Traceback', 'Not Found', 'Bad Gateway', 'Service Unavailable', 'jinja2', 'TemplateNotFound', 'Application error')
rows = []


def visit(page, label, url, shot=None, wait=3000, post=None, expect_json=False, full=True, expect=None):
    errs, failed = [], []
    on_c = lambda m: errs.append(m.text[:160]) if m.type == 'error' else None          # noqa: E731
    on_f = lambda r: failed.append(f'{r.url[:90]} {r.failure}')                         # noqa: E731
    page.on('console', on_c)
    page.on('requestfailed', on_f)
    status, title, text = None, '', ''
    try:
        resp = page.goto(url, wait_until='load', timeout=90000)
        status = resp.status if resp else None
        page.wait_for_timeout(wait)
        title = page.title()
        text = page.inner_text('body')[:20000]
        if shot:
            page.screenshot(path=os.path.join(SHOTS, shot + '.png'), full_page=full)
    except Exception as e:
        text = 'EXCEPTION ' + str(e)[:200]
    page.remove_listener('console', on_c)
    page.remove_listener('requestfailed', on_f)
    bad = [b for b in BAD if b in text]
    ok = status is not None and (status == expect if expect else status < 400) and not bad and not text.startswith('EXCEPTION')   # expect: a status that is the CORRECT answer (503 = unhealthy)
    rows.append({'page': label, 'url': url, 'status': status, 'ok': ok, 'title': title[:80], 'error_text': bad, 'console_errors': errs[:5],
                 'failed_requests': failed[:5], 'chars': len(text), 'screenshot': (shot + '.png') if shot else None})
    print(('OK   ' if ok else 'FAIL ') + label, status, flush=True)
    return text


def login(page, base, user, pw, register=False):
    if register:
        page.goto(base + '/register')
        page.fill('input[name=username]', user)
        page.fill('input[name=email]', user + '@example.test')
        page.fill('input[name=password]', pw)
        page.fill('input[name=confirm_password]', pw)
        page.click('button[type=submit]')
        page.wait_for_timeout(1500)
    page.goto(base + '/login')
    page.fill('input[name=username]', user)
    page.fill('input[name=password]', pw)
    page.click('button[type=submit]')
    page.wait_for_timeout(1500)


def predict(page, base, r, t, h):
    page.goto(base + '/predict')
    page.fill('input[name=rainfall]', str(r))
    page.fill('input[name=temperature]', str(t))
    page.fill('input[name=humidity]', str(h))
    page.click('button[type=submit]')
    page.wait_for_url('**/result', timeout=90000)


with sync_playwright() as pw:
    b = pw.chromium.launch(channel='msedge')
    ctx = b.new_context(viewport={'width': 1280, 'height': 860})
    page = ctx.new_page()

    for tag, base, new in (('A', 'http://127.0.0.1:5000', True), ('B', 'http://127.0.0.1:5100', True)):
        name = 'monolith app (:5000)' if tag == 'A' else 'Kubernetes app (:5100)'
        visit(page, f'{tag} home', base + '/', f'{tag}01_home')
        visit(page, f'{tag} register form', base + '/register', f'{tag}02_register')
        visit(page, f'{tag} login form', base + '/login', f'{tag}03_login')
        login(page, base, U + tag.lower(), P, register=True)
        visit(page, f'{tag} dashboard', base + '/dashboard', f'{tag}04_dashboard', wait=6000)
        visit(page, f'{tag} predict form', base + '/predict', f'{tag}05_predict_form')
        predict(page, base, 300, 27, 85)
        visit(page, f'{tag} result (extreme rain)', page.url, f'{tag}06_result_extreme', wait=4000)
        predict(page, base, 0, 18, 45)
        visit(page, f'{tag} result (drought)', page.url, f'{tag}07_result_drought', wait=4000)
        visit(page, f'{tag} analysis', base + '/analysis', f'{tag}08_analysis', wait=5000)
        visit(page, f'{tag} xai', base + '/xai', f'{tag}09_xai', wait=5000)
        visit(page, f'{tag} history', base + '/history', f'{tag}10_history')
        visit(page, f'{tag} /api/forecast', base + '/api/forecast', None)
        visit(page, f'{tag} /api/baseline', base + '/api/baseline', None)
        if tag == 'B':
            visit(page, 'B healthz', base + '/healthz', None)
            visit(page, 'B metrics', base + '/metrics', None)
            page.goto(base + '/lstm_predict')
            visit(page, 'B lstm_predict form', base + '/lstm_predict', 'B11_lstm_predict_form')
            page.click('button[type=submit]')
            page.wait_for_url('**/lstm_result', timeout=120000)
            visit(page, 'B lstm_result', page.url, 'B12_lstm_result', wait=4000)
            visit(page, 'B drift', base + '/drift', 'B13_drift') if False else None
        page.goto(base + '/logout')
        page.wait_for_timeout(800)
        ctx.clear_cookies()

    # ---- inference API
    for ep, shot in (('/health/live', None), ('/health/ready', 'C01_ready'), ('/health/semantic', 'C02_semantic'), ('/golden/info', 'C03_golden_info'),
                     ('/predict?model=auto&steps=6', 'C04_predict'), ('/slo', 'C05_slo'), ('/drift', 'C06_drift'), ('/aging', 'C07_aging'),
                     ('/energy', 'C08_energy'), ('/baseline', None), ('/shadow/status', None), ('/metrics', None)):
        visit(page, 'API ' + ep, API + ep, shot, wait=500)

    # ---- fault injection through the UI of the Kubernetes app, then recovery
    requests.get(API + '/fault?mode=corrupt', timeout=10)
    time.sleep(8)
    visit(page, 'API semantic health while corrupted (503 = correct)', API + '/health/semantic', 'C09_semantic_corrupted', wait=500, expect=503)
    login(page, 'http://127.0.0.1:5100', U + 'b', P)
    visit(page, 'B dashboard while degraded', 'http://127.0.0.1:5100/dashboard', 'B14_dashboard_degraded', wait=6000)
    requests.get(API + '/fault?mode=heal', timeout=10)
    time.sleep(8)
    visit(page, 'API semantic health after heal', API + '/health/semantic', 'C10_semantic_healed', wait=500)

    # ---- Grafana
    G = 'http://127.0.0.1:3000'
    page.goto(G + '/login')
    page.fill('input[name=user]', 'admin')
    page.fill('input[name=password]', 'admin')
    page.click('button[type=submit]')
    page.wait_for_timeout(2500)
    try:
        page.get_by_text('Skip').click(timeout=3000)
    except Exception:
        pass
    for _ in range(8):
        requests.get(API + '/predict?model=auto&steps=6', timeout=20)
        time.sleep(1)
    time.sleep(8)
    page.set_viewport_size({'width': 1600, 'height': 1000})
    gtext = visit(page, 'Grafana climate dashboard', G + '/d/climate-live/climate-ml-service-live?orgId=1&from=now-15m&to=now', 'D01_grafana', wait=15000, full=False)
    if 'Inference p95 latency' not in gtext:                          # a 200 with empty panels is not a pass
        rows[-1]['ok'] = False
        rows[-1]['error_text'] = ['dashboard panels did not render']
    page.set_viewport_size({'width': 1280, 'height': 860})
    for i, q in enumerate(('up', 'golden_violation_total', 'sum by (tier) (predict_tier_total)', 'golden_signature_valid'), 1):
        visit(page, 'Prometheus ' + q, 'http://127.0.0.1:9090/query?g0.expr=' + requests.utils.quote(q) + '&g0.tab=0&g0.range_input=15m', f'E0{i}_prometheus', wait=3500)
    b.close()

n_ok = sum(1 for r in rows if r['ok'])
json.dump({'generated': time.strftime('%Y-%m-%d %H:%M:%S'), 'pages': len(rows), 'ok': n_ok, 'rows': rows}, open(os.path.join(OUT, 'browser_check.json'), 'w'), indent=1)
lines = ['# Live browser check of every page', '', f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')}  |  {n_ok}/{len(rows)} pages OK", '',
         '| Page | HTTP | Result | Title | Console errors | Failed requests | Screenshot |', '|---|---|---|---|---|---|---|']
for r in rows:
    lines.append(f"| {r['page']} | {r['status']} | {'OK' if r['ok'] else '**FAIL**'} | {r['title']} | {len(r['console_errors'])} | {len(r['failed_requests'])} | {r['screenshot'] or ''} |")
open(os.path.join(OUT, 'browser_check.md'), 'w', encoding='utf8').write('\n'.join(lines))
print(f'{n_ok}/{len(rows)} pages OK')
