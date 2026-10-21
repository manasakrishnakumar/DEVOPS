# Bangalore Climate Analytics System — Complete Project Analysis

## 1. Project Overview

| Property | Value |
|----------|-------|
| **Type** | Flask Web Application |
| **Dataset** | Bangalore climate data 1951–2024 (882 months) |
| **Models** | 3 × SARIMA (Rainfall, Temp_mean, Humidity) |
| **Methodology** | WMO SPI (WMO-No. 1090, 2012) |
| **CES Formula** | `CES = 0.6 × Z_rainfall + 0.4 × Z_temperature` |
| **Thresholds** | Moderate ≥ 1.051 (84th pct) · Extreme ≥ 1.300 (95th pct) |
| **Port** | http://127.0.0.1:5000 |
| **Auth** | Flask-Login (SQLite database) |

---

## 2. Directory Structure

```
bangalore_climate_app/
├── app.py                  ← MAIN APP (1382 lines) — primary Flask server
├── old_app.py              ← Legacy backup (553 lines) — not served
├── data.csv                ← 882-month Bangalore dataset (1.2 MB)
├── database.db             ← SQLite user/prediction database
├── train_models.py         ← SARIMA training script
├── run_app.py              ← Alternative startup script
├── requirements.txt        ← Python dependencies
├── saved_models/           ← 3 × SARIMA .pkl files (115 MB each)
│   ├── sarima_rainfall.pkl
│   ├── sarima_temp_mean.pkl
│   └── sarima_humidity.pkl
├── utils/                  ← Core library
│   ├── __init__.py         ← Package exports
│   ├── preprocessing.py    ← Data loading & aggregation
│   ├── anomaly_detection.py← Z-scores, CES single, baseline
│   ├── climate_score.py    ← CES by year/season/decade
│   ├── forecasting.py      ← SARIMA load, forecast, evaluate
│   ├── database.py         ← SQLite CRUD operations
│   └── train_models.py     ← Duplicate of root train_models.py
├── Backend/                ← Research/testing scripts (not served)
│   ├── anomaly_detection.py
│   ├── test_model.py
│   ├── test_inp.py
│   └── ...
├── templates/              ← Jinja2 HTML templates (14 files)
│   ├── base.html           ← Navbar, CDN imports, footer
│   ├── index.html          ← Landing page
│   ├── login.html          ← Login form
│   ├── register.html       ← Registration form
│   ├── dashboard.html      ← Post-login overview
│   ├── predict.html        ← Input form (Rainfall, Temp, Humidity, Months)
│   ├── result.html         ← Full analysis results (1097 lines)
│   ├── xai.html            ← XAI explainability page (839 lines)
│   ├── analysis.html       ← Static analysis page
│   ├── history.html        ← Prediction history
│   ├── result_old.html     ← Legacy backup
│   ├── aaa.py              ← Stray file (should not be in templates/)
│   ├── 404.html / 500.html ← Error pages
└── static/
    ├── css/style.css
    ├── js/main.js
    └── images/             ← Generated plots + static images
```

---

## 3. Application Routes

| Route | Auth | Method | Purpose |
|-------|------|--------|---------|
| `/` | No | GET | Landing page |
| `/login` | No | GET/POST | User login |
| `/register` | No | GET/POST | User registration |
| `/logout` | Yes | GET | Logout |
| `/dashboard` | Yes | GET | Overview + 6-month forecast preview |
| `/predict` | Yes | GET/POST | Input form → stores in session |
| `/result` | Yes | GET | Full CES analysis + forecast |
| `/xai` | Yes | GET | Explainability + historical validation |
| `/analysis` | Yes | GET | Static analysis page |
| `/history` | Yes | GET | User's prediction history |
| `/api/forecast` | No | GET | JSON forecast API |
| `/api/baseline` | No | GET | JSON baseline stats API |

---

## 4. CES Pipeline (Current State — WMO SPI Compliant)

```
User Input (Rainfall, Temp, Humidity)
         │
         ▼
compute_baseline()  ← 30-year 1951-1980 baseline stats
         │
         ▼
compute_ces(rainfall, temp, humidity, baseline)
  z_rain = (rainfall - rain_mean) / rain_std     ← SIGNED (no abs)
  z_temp = (temp - temp_mean) / temp_std         ← SIGNED (no abs)
  ces = (0.6 × z_rain) + (0.4 × z_temp)         ← humidity EXCLUDED
         │
         ▼
Label using abs(ces):
  |CES| ≥ 1.300  → Extreme  (95th percentile)
  |CES| ≥ 1.051  → Moderate (84th percentile)
  |CES| < 1.051  → Normal
         │
         ▼
Interpretation:
  CES > 0  → Above normal  (flood/heat risk)
  CES < 0  → Below normal  (drought/cold risk)
```

---

## 5. Identified Issues

### 🔴 CRITICAL
| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | **Negative CES confuses users** — no sign indicator shown on result page | `result.html` line ~542 | Users see `-0.4` and don't know if that's good or bad |
| 2 | **`score_explanation` always says "above normal"** — action text assumes flood risk even for negative CES | `app.py` result route | Wrong advice for drought conditions |
| 3 | **`aaa.py` inside templates/** | `templates/aaa.py` | Stray file polluting template directory |

### 🟡 MODERATE
| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 4 | **`get_climate_interpretation()` missing from `old_app.py`** | `old_app.py` line ~483 | old_app.py crashes if ever run |
| 5 | **`plt.matplotlib` imported twice** | `app.py` lines 9 & 14 | Minor — duplicate import |
| 6 | **Secret key hardcoded** | `app.py` line 57 | Security issue in production |
| 7 | **SARIMA models are 115 MB each (345 MB total)** | `saved_models/` | Very heavy for deployment |
| 8 | **Backend files not updated for `hum_mean`/`hum_std` baseline key** | `Backend/test_inp.py` | `hum_mean` key removed from CES but old code may still reference it |

### 🟢 MINOR
| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 9 | **`result_old.html` stray file** | `templates/` | Clutter |
| 10 | **`PYTHONIOENCODING=utf-8` required to start** | `app.py` startup prints | Must always use env var to run |
| 11 | **Humidity input shown on predict form but not used in CES** | `predict.html` | No note telling user humidity is informational only |

---

## 6. CES Sign Issue — Root Cause

The negative CES on the result page is **correct mathematically** but the UI doesn't explain it:

- **Result page** shows raw `ces_result.CES` = e.g. `-0.42`
- The `score_explanation` card uses `abs(ces)` for classification ✅
- But the **action text** always says "above historical norms" even for negative CES ❌
- The **CES dial color** uses `ces_result.CES|abs >= 1.300` correctly ✅
- No **direction arrow** or **sign label** is shown to explain ±

---

## 7. What Was Changed in This Session

| File | Changes |
|------|---------|
| `app.py` | Constants · CES formula · Labels · Plot thresholds · score_explanation · xai_validation → validation_events/summary · All 10 hardcoded threshold fixes |
| `old_app.py` | Constants · CES formula · Labels · Plot thresholds · score_explanation |
| `utils/anomaly_detection.py` | Constants · CES formula · Labels · Plot thresholds |
| `utils/climate_score.py` | Constants · Plot thresholds |
| `utils/forecasting.py` | Constants · CES formula · Labels |
| `Backend/anomaly_detection.py` | Constants · CES formula · Labels |
| `Backend/test_model.py` | Constants · CES formula · Labels · Plot thresholds |
| `Backend/test_inp.py` | Constants · CES formula · Labels · Plot thresholds |
| `templates/result.html` | CES color conditionals · Scale text · "What does your CES mean?" card |
| `templates/xai.html` | CES formula text · Section 7 validation with full dataset stats |
| `templates/predict.html` | Threshold hint text |

---

## 8. Recommended Next Fixes (Priority Order)

### Fix A — Show CES direction on result page (HIGH PRIORITY)
Add a direction indicator next to the CES value:
- `CES = +1.45 ↑ Above Normal (Flood Risk)` 
- `CES = -0.42 ↓ Below Normal (Drought Risk)`

### Fix B — Fix score_explanation action text for negative CES
Current text always says "rainfall/temperature significantly above normal."
Should say "below normal" for negative CES.

### Fix C — Add note on predict form about humidity
`"Humidity is collected for data completeness but not used in CES calculation (excluded due to multicollinearity)."`

### Fix D — Delete stray files
- `templates/aaa.py`
- `templates/result_old.html`

### Fix E — Move secret key to environment variable
```python
app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-key')
```
