"""
Model Training Script
=====================
Train SARIMA models for all climate variables
Run this script before starting the Flask app
"""

import os
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from utils import (
    load_data, preprocess, aggregate_monthly, 
    add_season, add_decade, train_all_models
)

def main():
    print("="*60)
    print("BANGALORE CLIMATE ANALYTICS SYSTEM")
    print("Model Training Pipeline")
    print("="*60)
    
    # Load your data
    # Update this path to your actual data file
    DATA_PATH = 'data.csv'  # Change this to your data file path
    
    if not os.path.exists(DATA_PATH):
        print(f"\nError: Data file not found at {DATA_PATH}")
        print("\nPlease ensure your data file is in the correct location.")
        print("Expected columns: Date, Rainfall, Temp_Max, Temp_Min, Humidity")
        return
    
    print("\n1. Loading data...")
    raw = load_data(DATA_PATH)
    print(f"   Loaded {len(raw)} rows")
    
    print("\n2. Preprocessing data...")
    daily = preprocess(raw)
    print(f"   Daily data shape: {daily.shape}")
    
    print("\n3. Aggregating to monthly...")
    monthly = aggregate_monthly(daily)
    monthly = add_season(monthly)
    monthly = add_decade(monthly)
    print(f"   Monthly data shape: {monthly.shape}")
    print(f"   Date range: {monthly['Date'].min()} to {monthly['Date'].max()}")
    
    print("\n4. Training SARIMA models...")
    print("   This may take a few minutes...")
    
    try:
        results, metrics = train_all_models(monthly, train_cutoff_year=2018)
        
        print("\n5. Model Evaluation Results:")
        print("="*50)
        for var, metric in metrics.items():
            print(f"\n{var}:")
            print(f"   MAE:  {metric['MAE']:.3f}")
            print(f"   RMSE: {metric['RMSE']:.3f}")
            print(f"   MAPE: {metric['MAPE']:.2f}%")
            print(f"   R²:   {metric['R2']:.3f}")
        
        print("\n6. Generating sample forecast...")
        from utils import forecast_future
        future = forecast_future(results, steps=24)
        print("\n   Next 6 months forecast:")
        print(future.head(6).to_string())
        
        print("\n" + "="*60)
        print("MODEL TRAINING COMPLETE!")
        print("Models saved in 'saved_models/' directory")
        print("="*60)
        
        # Save metrics to file
        metrics_df = pd.DataFrame(metrics).T
        metrics_df.to_csv('outputs/model_metrics.csv')
        print("\nMetrics saved to outputs/model_metrics.csv")
        
    except Exception as e:
        print(f"\nError during training: {e}")
        print("\nTips:")
        print("1. Ensure your data has at least 24 months of history")
        print("2. Check for any missing values in the data")
        print("3. Verify the data contains the required columns")

if __name__ == '__main__':
    main()