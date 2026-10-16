"""
anomaly_detection.py
Z-score based anomaly detection for climate variables
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ══════════════════════════════════════════════════════════════
# CES THRESHOLDS — WMO SPI METHODOLOGY (WMO-No. 1090, 2012)
# Computed from actual Bangalore data 1951–2024 (882 months)
# Moderate = 84th percentile of CES distribution = 1.051
# Extreme  = 95th percentile of CES distribution = 1.300
# ══════════════════════════════════════════════════════════════
CES_MODERATE = 1.051
CES_EXTREME  = 1.300


def compute_climatology(monthly: pd.DataFrame) -> pd.DataFrame:
    """
    Compute monthly climatology baseline:
    mean and std for Rainfall, Temp_mean, Humidity per calendar month.
    """
    baseline = monthly.groupby('Month').agg(
        Rain_mean=('Rainfall', 'mean'),
        Rain_std=('Rainfall', 'std'),
        Temp_mean_mean=('Temp_mean', 'mean'),
        Temp_mean_std=('Temp_mean', 'std'),
        Hum_mean=('Humidity', 'mean'),
        Hum_std=('Humidity', 'std'),
    ).reset_index()
    return baseline


def compute_anomalies(monthly: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """
    Merge climatology with monthly data and compute:
    - Raw anomalies
    - Z-scores
    - Anomaly labels
    - CES
    """
    df = monthly.merge(baseline, on='Month', how='left')

    # Raw anomalies
    df['Rain_anomaly'] = df['Rainfall'] - df['Rain_mean']
    df['Temp_anomaly'] = df['Temp_mean'] - df['Temp_mean_mean']
    df['Hum_anomaly'] = df['Humidity'] - df['Hum_mean']

    # Z-scores
    df['Z_rain'] = df['Rain_anomaly'] / df['Rain_std'].replace(0, np.nan)
    df['Z_temp'] = df['Temp_anomaly'] / df['Temp_mean_std'].replace(0, np.nan)
    df['Z_hum'] = df['Hum_anomaly'] / df['Hum_std'].replace(0, np.nan)

    # Fill NaN Z-scores with 0
    for col in ['Z_rain', 'Z_temp', 'Z_hum']:
        df[col] = df[col].fillna(0)

    # Anomaly labels per variable
    def label_anomaly(z):
        az = abs(z)
        if az >= CES_EXTREME:
            return 'Strong'
        elif az >= CES_MODERATE:
            return 'Moderate'
        else:
            return 'Normal'

    df['Rain_label'] = df['Z_rain'].apply(label_anomaly)
    df['Temp_label'] = df['Z_temp'].apply(label_anomaly)
    df['Hum_label'] = df['Z_hum'].apply(label_anomaly)

    # Climate Extreme Score (humidity kept in pipeline but not in CES)
    df['CES'] = (0.6 * df['Z_rain']) + (0.4 * df['Z_temp'])

    # CES classification
    def label_ces(ces):
        a = abs(ces)
        if a >= CES_EXTREME:
            return 'Extreme'
        elif a >= CES_MODERATE:
            return 'Moderate'
        else:
            return 'Normal'

    df['CES_label'] = df['CES'].apply(label_ces)

    return df


def anomaly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return count of each anomaly label per variable."""
    rain_counts = df['Rain_label'].value_counts().rename('Rainfall')
    temp_counts = df['Temp_label'].value_counts().rename('Temperature')
    hum_counts = df['Hum_label'].value_counts().rename('Humidity')
    summary = pd.DataFrame([rain_counts, temp_counts, hum_counts]).T.fillna(0).astype(int)
    return summary


def compute_climatology_baseline(monthly: pd.DataFrame) -> dict:
    """
    Compute baseline statistics as dictionary (for Flask app compatibility)
    """
    baseline = {
        'rain_mean': monthly['Rainfall'].mean(),
        'rain_std': monthly['Rainfall'].std(),
        'temp_mean': monthly['Temp_mean'].mean(),
        'temp_std': monthly['Temp_mean'].std(),
        'hum_mean': monthly['Humidity'].mean(),
        'hum_std': monthly['Humidity'].std(),
    }
    return baseline


def get_baseline_for_flask():
    """
    Compute per-month climatological baseline from actual data.
    Uses calendar-month mean and std so January is compared to
    all January values, July to all July values etc.
    This is the correct climatological anomaly approach.
    Source: WMO SPI methodology (WMO-No. 1090, 2012)
    """
    import os
    import pandas as pd
    import numpy as np

    # Load data
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data.csv')
    df = pd.read_csv(data_path)
    df.columns = ['Date', 'Rainfall', 'Temp_Max', 'Temp_Min', 'Humidity']
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Rainfall'] = pd.to_numeric(df['Rainfall'].replace({'Tr': 0, 'Trace': 0}), errors='coerce').fillna(0)
    df['Temp_Max'] = pd.to_numeric(df['Temp_Max'], errors='coerce')
    df['Temp_Min'] = pd.to_numeric(df['Temp_Min'], errors='coerce')
    df['Temp_mean'] = (df['Temp_Max'] + df['Temp_Min']) / 2
    df['Humidity'] = pd.to_numeric(df['Humidity'], errors='coerce')
    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month
    df = df.dropna(subset=['Year', 'Month'])

    monthly = df.groupby(['Year', 'Month']).agg(
        Rainfall=('Rainfall', 'sum'),
        Temp_mean=('Temp_mean', 'mean'),
        Humidity=('Humidity', 'mean')
    ).reset_index()

    # Per-month baseline — correct climatological approach
    baseline_monthly = monthly.groupby('Month').agg(
        rain_mean=('Rainfall', 'mean'),
        rain_std=('Rainfall', 'std'),
        temp_mean=('Temp_mean', 'mean'),
        temp_std=('Temp_mean', 'std'),
        hum_mean=('Humidity', 'mean'),
        hum_std=('Humidity', 'std')
    ).reset_index()

    # Also keep overall baseline for backward compatibility
    overall = {
        'rain_mean': monthly['Rainfall'].mean(),
        'rain_std':  monthly['Rainfall'].std(),
        'temp_mean': monthly['Temp_mean'].mean(),
        'temp_std':  monthly['Temp_mean'].std(),
        'hum_mean':  monthly['Humidity'].mean(),
        'hum_std':   monthly['Humidity'].std(),
        'monthly':   baseline_monthly  # per-month lookup
    }
    return overall


def compute_ces_single(rainfall, temperature, humidity, baseline, month=None):
    """
    Compute CES using OVERALL baseline for both rainfall and temperature.
    This ensures thresholds 1.051 (Moderate) and 1.300 (Extreme) are
    correctly calibrated against the full 1951-2024 distribution.
    Overall baseline: rain_mean≈66.17mm, rain_std≈77.93mm.
    Humidity kept as parameter so form does not break,
    but NOT used in CES — removed due to multicollinearity.
    month parameter retained for API compatibility but not used.
    """
    # CES uses OVERALL baseline for BOTH rainfall and temperature
    rain_mean = baseline['rain_mean']
    rain_std  = baseline['rain_std']
    temp_mean = baseline['temp_mean']
    temp_std  = baseline['temp_std']

    # Z-scores — signed, no abs()
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
        'Z_Rainfall':            round(z_rain, 3),
        'Rainfall_Condition':    label_anomaly(z_rain),
        'Z_Temperature':         round(z_temp, 3),
        'Temperature_Condition': label_anomaly(z_temp),
        'CES':                   round(ces, 3),
        'Climate_Condition':     label_ces(ces)
    }


def plot_anomaly_timeline_simple(df_anom, variable='Rainfall', save_path=None):
    """
    Create anomaly timeline plot (simplified version)
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot original values
    ax.plot(df_anom['Date'], df_anom[variable], 'b-', alpha=0.7, label='Original')
    
    # Highlight anomalies
    var_lower = variable.lower()
    if var_lower == 'rainfall':
        z_col = 'Z_rain'
    elif var_lower == 'temp_mean':
        z_col = 'Z_temp'
    else:
        z_col = 'Z_hum'
    
    if z_col in df_anom.columns:
        anomalies = df_anom[df_anom[z_col].abs() >= CES_MODERATE]
        if len(anomalies) > 0:
            ax.scatter(anomalies['Date'], anomalies[variable],
                       color='red', s=50, label='Strong Anomalies', zorder=5)
    ax.axhline(y=CES_MODERATE, color='orange', linestyle='--', label='Moderate Threshold', alpha=0.7)
    ax.axhline(y=CES_EXTREME,  color='red',    linestyle='--', label='Extreme Threshold',  alpha=0.7)
    
    ax.set_title(f'{variable} - Anomaly Detection', fontsize=14, fontweight='bold')
    ax.set_xlabel('Year')
    ax.set_ylabel(variable)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    
    plt.close()
    return fig


if __name__ == '__main__':
    from preprocessing import load_data, preprocess, aggregate_monthly, add_season, add_decade
    raw = load_data('data.csv')
    daily = preprocess(raw)
    monthly = aggregate_monthly(daily)
    monthly = add_season(monthly)
    monthly = add_decade(monthly)
    baseline = compute_climatology(monthly)
    df_anom = compute_anomalies(monthly, baseline)
    print(df_anom[['Date', 'Z_rain', 'Z_temp', 'Z_hum', 'CES', 'CES_label']].head(10))
    print("\nAnomaly Summary:")
    print(anomaly_summary(df_anom))