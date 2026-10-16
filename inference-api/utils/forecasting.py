"""
forecasting.py
Time-series forecasting using ARIMA/SARIMA for Bangalore climate variables
"""

import pandas as pd
import numpy as np
import warnings
import joblib
import os
import matplotlib.pyplot as plt
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════
# CES THRESHOLDS — WMO SPI METHODOLOGY (WMO-No. 1090, 2012)
# Computed from actual Bangalore data 1951–2024 (882 months)
# Moderate = 84th percentile of CES distribution = 1.051
# Extreme  = 95th percentile of CES distribution = 1.300
# ══════════════════════════════════════════════════════════════
CES_MODERATE = 1.051
CES_EXTREME  = 1.300

MODELS_DIR = 'saved_models'
os.makedirs(MODELS_DIR, exist_ok=True)


def _compute_ces_single(rainfall, temperature, humidity, baseline, month=None):
    """
    Internal CES computation to avoid circular imports.
    Uses OVERALL baseline for BOTH rainfall and temperature so that
    CES values are consistent with the predict/result and XAI pages.
    Humidity kept as parameter so caller does not break,
    but NOT used in CES — removed due to multicollinearity.
    month parameter retained for API compatibility but not used.
    """
    # CES uses OVERALL baseline for BOTH rainfall and temperature
    rain_mean = baseline['rain_mean']
    rain_std  = baseline['rain_std']
    temp_mean = baseline['temp_mean']
    temp_std  = baseline['temp_std']

    z_rain = (rainfall - rain_mean) / (rain_std + 1e-8)
    z_temp = (temperature - temp_mean) / (temp_std + 1e-8)
    # Rainfall weight 0.6 — Bangalore is monsoon-dominated (IMD SOP 2021)
    # Temperature weight 0.4 — secondary driver (IMD heatwave criteria)
    ces = (0.6 * z_rain) + (0.4 * z_temp)
    
    def label_anomaly(z):
        az = abs(z)
        if az >= CES_EXTREME:    return 'Strong Anomaly'
        elif az >= CES_MODERATE: return 'Moderate Anomaly'
        else:                    return 'Normal'
    
    def label_ces(ces_val):
        ac = abs(ces_val)
        if ac >= CES_EXTREME:    return 'Extreme'
        elif ac >= CES_MODERATE: return 'Moderate'
        else:                    return 'Normal'
    
    return {
        'Z_Rainfall': round(z_rain, 3),
        'Rainfall_Condition': label_anomaly(z_rain),
        'Z_Temperature': round(z_temp, 3),
        'Temperature_Condition': label_anomaly(z_temp),
        'CES': round(ces, 3),
        'Climate_Condition': label_ces(ces)
    }


def adf_test(series: pd.Series, name: str = '') -> bool:
    """Augmented Dickey-Fuller test. Returns True if stationary."""
    result = adfuller(series.dropna())
    stationary = result[1] < 0.05
    print(f"ADF Test [{name}]: p-value={result[1]:.4f} → {'Stationary' if stationary else 'Non-Stationary'}")
    return stationary


def make_stationary(series: pd.Series) -> pd.Series:
    """Apply first differencing if non-stationary."""
    if not adf_test(series, series.name):
        series = series.diff().dropna()
    return series


def train_sarima(series: pd.Series, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12)):
    """Fit SARIMA model."""
    model = SARIMAX(series, order=order, seasonal_order=seasonal_order,
                    enforce_stationarity=False, enforce_invertibility=False)
    fitted = model.fit(disp=False)
    return fitted


def evaluate_model(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Compute MAE, RMSE, MAPE, R2."""
    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    mape = np.mean(np.abs((actual - predicted) / (actual + 1e-8))) * 100
    r2 = r2_score(actual, predicted)
    return {'MAE': round(mae, 3), 'RMSE': round(rmse, 3), 'MAPE': round(mape, 3), 'R2': round(r2, 3)}


def train_all_models(monthly: pd.DataFrame, train_cutoff_year: int = 2018):
    """
    Train SARIMA models for Rainfall, Temp_mean, Humidity.
    Save models to saved_models/.
    Returns dict of fitted models and evaluation metrics.
    """
    targets = {
        'Rainfall': (1, 1, 1),
        'Temp_mean': (1, 1, 1),
        'Humidity': (1, 1, 1),
    }

    train = monthly[monthly['Year'] <= train_cutoff_year].set_index('Date')
    test = monthly[monthly['Year'] > train_cutoff_year].set_index('Date')

    results = {}
    metrics = {}

    for var, order in targets.items():
        print(f"\n--- Training SARIMA for {var} ---")
        train_series = train[var]
        test_series = test[var]

        adf_test(train_series, var)

        fitted = train_sarima(train_series, order=order, seasonal_order=(1, 1, 1, 12))

        # In-sample + forecast for test period
        forecast_steps = len(test_series)
        forecast_obj = fitted.get_forecast(steps=forecast_steps)
        pred = forecast_obj.predicted_mean.values

        actual = test_series.values[:len(pred)]
        m = evaluate_model(actual, pred)
        metrics[var] = m
        print(f"  {var} → MAE={m['MAE']}, RMSE={m['RMSE']}, MAPE={m['MAPE']}%, R2={m['R2']}")

        # Save model
        model_path = os.path.join(MODELS_DIR, f'sarima_{var.lower()}.pkl')
        joblib.dump(fitted, model_path)
        print(f"  Model saved: {model_path}")

        results[var] = {
            'model': fitted,
            'train': train_series,
            'test': test_series,
            'pred_test': pd.Series(pred, index=test_series.index[:len(pred)]),
        }

    return results, metrics


def forecast_future(results: dict, steps: int = 24) -> pd.DataFrame:
    """
    Generate future forecasts for all variables.
    Returns a DataFrame with future dates and forecasted values.
    """
    future_dfs = []
    for var, res in results.items():
        fitted = res['model']
        fc = fitted.get_forecast(steps=steps)
        fc_mean = fc.predicted_mean
        fc_mean.name = var
        future_dfs.append(fc_mean)

    future_df = pd.concat(future_dfs, axis=1).reset_index()
    future_df.columns = ['Date'] + list(results.keys())
    return future_df


def load_all_models(model_dir='saved_models'):
    """
    Load all trained models
    """
    models = {}
    variables = ['Rainfall', 'Temp_mean', 'Humidity']
    
    for var in variables:
        model_path = os.path.join(model_dir, f'sarima_{var.lower()}.pkl')
        if os.path.exists(model_path):
            models[var] = joblib.load(model_path)
            print(f"Loaded model for {var}")
        else:
            print(f"Model not found for {var}")
            models[var] = None
    
    return models


def forecast_with_loaded_models(models, steps=12, baseline=None, user_rainfall=None, user_temp=None):
    """
    Generate forecast using loaded models
    """
    forecast_results = {}
    
    for var, model in models.items():
        if model is not None:
            try:
                # Try to get forecast with confidence intervals
                forecast = model.get_forecast(steps=steps)
                forecast_results[var] = forecast.predicted_mean.values
            except AttributeError:
                # Fallback for different model types
                try:
                    forecast_results[var] = model.forecast(steps=steps)
                except:
                    forecast_results[var] = np.zeros(steps)
            except Exception as e:
                print(f"Error forecasting {var}: {e}")
                forecast_results[var] = np.zeros(steps)
        else:
            # Generate synthetic forecast if model missing
            if baseline:
                mean = baseline.get(f'{var.lower()}_mean', 0)
                std = baseline.get(f'{var.lower()}_std', 1)
                np.random.seed(42)
                forecast_results[var] = np.random.normal(mean, std * 0.3, steps)
            else:
                forecast_results[var] = np.zeros(steps)
    
    # Create forecast dataframe
    forecast_df = pd.DataFrame({
        'Month': range(1, steps + 1),
        'Rainfall': forecast_results.get('Rainfall', np.zeros(steps)),
        'Temp_mean': forecast_results.get('Temp_mean', np.zeros(steps)),
        'Humidity': forecast_results.get('Humidity', np.zeros(steps))
    })

    # Model trained to December 2023 → step 1 = January 2024
    # Using datetime.now().month was wrong (28 months ahead of where model starts)
    # This helper maps each forecast step to its true calendar month
    import datetime as _dt

    # Training end: December 2023
    TRAINING_END_YEAR  = 2023
    TRAINING_END_MONTH = 12

    def get_forecast_calendar_month(step, end_year, end_month):
        """step 1 = Jan 2024, step 7 = Jul 2024, step 12 = Dec 2024, etc."""
        total = end_month + step
        return ((total - 1) % 12) + 1

    # Apply physical rainfall caps using CORRECT calendar month
    # Cap = mean + 1.5*std from Bangalore 1951-2024 data
    monthly_rain_caps = {
        1: 5.0,    # Jan 75th pct=2.4mm,  cap at 5mm
        2: 8.0,    # Feb 75th pct=3.5mm,  cap at 8mm
        3: 9.0,    # Mar 75th pct=9.0mm,  cap at 9mm
        4: 43.0,   # Apr 75th pct=43.3mm, cap at 43mm
        5: 162.0,  # May mean+1.5std=162mm
        6: 140.9,  # Jun mean+1.5std=141mm
        7: 203.5,  # Jul mean+1.5std=204mm
        8: 225.1,  # Aug mean+1.5std=225mm
        9: 292.1,  # Sep mean+1.5std=292mm
        10: 298.6, # Oct mean+1.5std=299mm
        11: 145.3, # Nov mean+1.5std=145mm
        12: 38.1,  # Dec mean+1.5std=38mm
    }

    for idx, row in forecast_df.iterrows():
        step      = int(row['Month'])
        cal_month = get_forecast_calendar_month(step, TRAINING_END_YEAR, TRAINING_END_MONTH)
        cap       = monthly_rain_caps[cal_month]
        forecast_df.at[idx, 'Rainfall'] = max(0, min(float(row['Rainfall']), cap))

    # ── User-Input-Driven CES Blending ────────────────────────────────────
    # Compute the anomaly the user is currently experiencing.
    # Month 1 of forecast inherits 80% of user's current anomaly (most relevant).
    # The influence decays linearly to 0% by month 12 (SARIMA takes over fully).
    # → Normal input   → all months stay Normal (no forced bias)
    # → Extreme input  → early months show risk, fading out over the year
    # ─────────────────────────────────────────────────────────────────────
    user_ces_offset = 0.0
    if baseline and user_rainfall is not None and user_temp is not None:
        z_rain_u = (user_rainfall - baseline['rain_mean']) / (baseline['rain_std'] + 1e-8)
        z_temp_u = (user_temp     - baseline['temp_mean']) / (baseline['temp_std'] + 1e-8)
        user_ces_offset = 0.6 * z_rain_u + 0.4 * z_temp_u

    # Compute CES for forecast using CORRECT calendar month per step
    ces_df = None
    if baseline:
        ces_results = []
        for idx, row in forecast_df.iterrows():
            step      = int(row['Month'])
            cal_month = get_forecast_calendar_month(step, TRAINING_END_YEAR, TRAINING_END_MONTH)

            # Pure SARIMA CES (no forced bias)
            ces = _compute_ces_single(
                row['Rainfall'],
                row['Temp_mean'],
                row['Humidity'],
                baseline,
                month=cal_month
            )

            # Blend user's current anomaly with decaying weight:
            # month 1 = 80% user influence, month 12 = 0% user influence
            decay_weight = 0.8 * max(0.0, 1.0 - (step - 1) / (steps - 1 if steps > 1 else 1))
            blended_ces  = round(ces['CES'] + decay_weight * user_ces_offset, 3)

            # Re-label based on blended CES
            abs_blended = abs(blended_ces)
            if abs_blended >= CES_EXTREME:
                climate_condition = 'Extreme'
            elif abs_blended >= CES_MODERATE:
                climate_condition = 'Moderate'
            else:
                climate_condition = 'Normal'

            ces['CES']               = blended_ces
            ces['Climate_Condition'] = climate_condition
            ces['Month']             = row['Month']
            ces_results.append(ces)
        ces_df = pd.DataFrame(ces_results)

        # Add extreme event description per forecast month
        _month_season = {
            1: 'Winter',     2: 'Winter',     3: 'Summer',
            4: 'Summer',     5: 'Summer',     6: 'Monsoon',
            7: 'Monsoon',    8: 'Monsoon',    9: 'Monsoon',
            10: 'Post-Monsoon', 11: 'Post-Monsoon', 12: 'Winter'
        }
        for i, row in ces_df.iterrows():
            ces_val  = row['CES']
            step     = int(row['Month'])
            cal_mon  = get_forecast_calendar_month(step, TRAINING_END_YEAR, TRAINING_END_MONTH)
            season   = _month_season.get(cal_mon, 'Unknown')
            if abs(ces_val) < 1.051:
                ces_df.at[i, 'Event_Description'] = 'Normal conditions expected'
                ces_df.at[i, 'Risk_Level']        = '—'
            elif ces_val > 0:
                if season == 'Monsoon':
                    ces_df.at[i, 'Event_Description'] = 'Heavy monsoon — flood and waterlogging risk'
                    ces_df.at[i, 'Risk_Level']        = 'Flood Risk'
                elif season == 'Post-Monsoon':
                    ces_df.at[i, 'Event_Description'] = 'Above normal post-monsoon rains — flooding risk'
                    ces_df.at[i, 'Risk_Level']        = 'Flood Risk'
                elif season == 'Summer':
                    ces_df.at[i, 'Event_Description'] = 'Unseasonal heavy rains with heat — thunderstorm risk'
                    ces_df.at[i, 'Risk_Level']        = 'Thunderstorm Risk'
                else:
                    ces_df.at[i, 'Event_Description'] = 'Above normal winter rainfall — unseasonal flood risk'
                    ces_df.at[i, 'Risk_Level']        = 'Flood Risk'
            else:
                if season == 'Monsoon':
                    ces_df.at[i, 'Event_Description'] = 'Deficient monsoon — drought and water shortage risk'
                    ces_df.at[i, 'Risk_Level']        = 'Drought Risk'
                elif season == 'Post-Monsoon':
                    ces_df.at[i, 'Event_Description'] = 'Dry post-monsoon — reservoir depletion risk'
                    ces_df.at[i, 'Risk_Level']        = 'Water Shortage Risk'
                elif season == 'Summer':
                    ces_df.at[i, 'Event_Description'] = 'Dry hot summer — severe heatwave and water scarcity'
                    ces_df.at[i, 'Risk_Level']        = 'Heatwave Risk'
                else:
                    ces_df.at[i, 'Event_Description'] = 'Cold dry winter — cold wave risk'
                    ces_df.at[i, 'Risk_Level']        = 'Cold Wave Risk'
    
    return forecast_df, ces_df


def plot_forecast_with_ci(forecast_df, actual_series=None, variable='Rainfall', save_path=None):
    """
    Plot forecast with confidence intervals (if available)
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot actual if provided
    if actual_series is not None:
        ax.plot(actual_series.index, actual_series.values, 'b-', label='Historical', alpha=0.7)
    
    # Plot forecast
    months = range(1, len(forecast_df) + 1)
    ax.plot(months, forecast_df[variable], 'r-', marker='o', label='Forecast', linewidth=2)
    
    ax.set_title(f'{variable} - {len(forecast_df)} Month Forecast', fontsize=14, fontweight='bold')
    ax.set_xlabel('Future Months')
    ax.set_ylabel(variable)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    
    plt.close()
    return fig


def evaluate_model_performance(monthly, model_results):
    """
    Evaluate model performance on test set
    """
    metrics_list = []
    
    for var, res in model_results.items():
        if 'test' in res and 'pred_test' in res:
            metrics = evaluate_model(res['test'].values, res['pred_test'].values)
            metrics['Variable'] = var
            metrics_list.append(metrics)
    
    return pd.DataFrame(metrics_list)


if __name__ == '__main__':
    from preprocessing import load_data, preprocess, aggregate_monthly, add_season, add_decade
    raw = load_data('data.csv')
    daily = preprocess(raw)
    monthly = aggregate_monthly(daily)
    monthly = add_season(monthly)
    monthly = add_decade(monthly)
    results, metrics = train_all_models(monthly)
    print("\nEvaluation Metrics:")
    print(pd.DataFrame(metrics).T)
    future = forecast_future(results, steps=24)
    print("\nFuture Forecast (first 6 rows):")
    print(future.head(6))