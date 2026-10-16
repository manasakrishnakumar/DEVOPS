"""
Utils Package - Bangalore Climate Analytics System
==================================================
Package initialization file
"""

from .preprocessing import (
    load_data,
    preprocess,
    aggregate_monthly,
    add_season,
    add_decade,
    get_season
)

from .anomaly_detection import (
    compute_climatology,
    compute_anomalies,
    anomaly_summary,
    compute_climatology_baseline,
    get_baseline_for_flask,
    compute_ces_single,
    plot_anomaly_timeline_simple
)

from .climate_score import (
    ces_by_year,
    ces_by_decade,
    ces_by_season,
    ces_extreme_events,
    period_comparison,
    compute_ces_trend_simple,
    get_ces_summary_stats,
    plot_ces_timeline
)

from .forecasting import (
    adf_test,
    make_stationary,
    train_sarima,
    evaluate_model,
    train_all_models,
    forecast_future,
    load_all_models,
    forecast_with_loaded_models,
    plot_forecast_with_ci,
    evaluate_model_performance
)

__all__ = [
    # Preprocessing
    'load_data', 'preprocess', 'aggregate_monthly', 
    'add_season', 'add_decade', 'get_season',
    
    # Anomaly Detection
    'compute_climatology', 'compute_anomalies', 'anomaly_summary',
    'compute_climatology_baseline', 'get_baseline_for_flask',
    'compute_ces_single', 'plot_anomaly_timeline_simple',
    
    # Climate Score
    'ces_by_year', 'ces_by_decade', 'ces_by_season',
    'ces_extreme_events', 'period_comparison',
    'compute_ces_trend_simple', 'get_ces_summary_stats', 'plot_ces_timeline',
    
    # Forecasting
    'adf_test', 'make_stationary', 'train_sarima', 'evaluate_model',
    'train_all_models', 'forecast_future', 'load_all_models',
    'forecast_with_loaded_models', 'plot_forecast_with_ci',
    'evaluate_model_performance'
]