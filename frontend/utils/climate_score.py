"""
climate_score.py
Climate Extreme Score (CES) analysis utilities
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# ══════════════════════════════════════════════════════════════
# CES THRESHOLDS — WMO SPI METHODOLOGY (WMO-No. 1090, 2012)
# Computed from actual Bangalore data 1951–2024 (882 months)
# Moderate = 84th percentile of CES distribution = 1.051
# Extreme  = 95th percentile of CES distribution = 1.300
# ══════════════════════════════════════════════════════════════
CES_MODERATE = 1.051
CES_EXTREME  = 1.300


def ces_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Yearly average CES."""
    return df.groupby('Year')['CES'].mean().reset_index()


def ces_by_decade(df: pd.DataFrame) -> pd.DataFrame:
    """Decade average CES."""
    return df.groupby('Decade')['CES'].mean().reset_index()


def ces_by_season(df: pd.DataFrame) -> pd.DataFrame:
    """Seasonal average CES."""
    return df.groupby('Season')['CES'].mean().reset_index()


def ces_extreme_events(df: pd.DataFrame) -> pd.DataFrame:
    """Filter only Extreme CES events."""
    return df[df['CES_label'] == 'Extreme'].copy()


def period_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare mean Rainfall, Temp_mean, Humidity, CES
    across three historical periods.
    """
    bins = [1950, 1980, 2000, 2025]
    labels = ['1951-1980', '1981-2000', '2001-2024']
    df = df.copy()
    df['Period'] = pd.cut(df['Year'], bins=bins, labels=labels, right=True)
    summary = df.groupby('Period', observed=True).agg(
        Rainfall=('Rainfall', 'mean'),
        Temp_mean=('Temp_mean', 'mean'),
        Humidity=('Humidity', 'mean'),
        CES=('CES', 'mean'),
        Anomaly_count=('Rain_label', lambda x: (x != 'Normal').sum())
    ).reset_index()
    return summary


def compute_ces_trend_simple(ces_series):
    """
    Compute CES trend analysis (simplified for Flask)
    """
    x = np.arange(len(ces_series))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, ces_series.values)
    
    return {
        'slope': slope,
        'trend': 'Increasing' if slope > 0 else 'Decreasing',
        'total_change': slope * len(ces_series),
        'r_squared': r_value ** 2,
        'significant': p_value < 0.05
    }


def get_ces_summary_stats(ces_df):
    """
    Get summary statistics for CES values
    """
    return {
        'mean_ces': ces_df['CES'].mean(),
        'std_ces': ces_df['CES'].std(),
        'max_ces': ces_df['CES'].max(),
        'min_ces': ces_df['CES'].min(),
        'extreme_count': (ces_df['CES_label'] == 'Extreme').sum(),
        'moderate_count': (ces_df['CES_label'] == 'Moderate').sum(),
        'normal_count': (ces_df['CES_label'] == 'Normal').sum()
    }


def plot_ces_timeline(ces_df, save_path=None):
    """
    Plot CES timeline
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    ax.plot(ces_df['Date'], ces_df['CES'], 'b-', linewidth=2)
    ax.fill_between(ces_df['Date'], 0, ces_df['CES'], alpha=0.3)
    ax.axhline(y=CES_MODERATE, color='orange', linestyle='--',
               label=f'Moderate ≥{CES_MODERATE} (WMO SPI, 84th percentile)', linewidth=2)
    ax.axhline(y=CES_EXTREME,  color='red',    linestyle='--',
               label=f'Extreme ≥{CES_EXTREME} (WMO SPI, 95th percentile)',  linewidth=2)
    
    ax.set_title('Climate Extreme Score (CES) Over Time', fontsize=14, fontweight='bold')
    ax.set_xlabel('Year')
    ax.set_ylabel('CES Value')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    
    plt.close()
    return fig


if __name__ == '__main__':
    from preprocessing import load_data, preprocess, aggregate_monthly, add_season, add_decade
    from anomaly_detection import compute_climatology, compute_anomalies
    raw = load_data('data.csv')
    daily = preprocess(raw)
    monthly = aggregate_monthly(daily)
    monthly = add_season(monthly)
    monthly = add_decade(monthly)
    baseline = compute_climatology(monthly)
    df = compute_anomalies(monthly, baseline)
    print(period_comparison(df))