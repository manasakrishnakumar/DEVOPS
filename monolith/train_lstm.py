"""
Train LSTM Models for Climate Forecasting
Run this script before using the LSTM prediction feature
"""

import os
import sys
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.preprocessing import load_data, preprocess, aggregate_monthly
from utils.lstm_model import train_all_lstm_models


def clean_data_directly(df):
    """Direct data cleaning function"""
    print("\nPerforming direct data cleaning...")
    
    # Clean rainfall column
    df['Rainfall'] = df['Rainfall'].astype(str).str.extract('(\d+\.?\d*)').astype(float)
    df['Rainfall'] = df['Rainfall'].fillna(0)
    
    # Clean temperature columns
    df['Temp_Max'] = pd.to_numeric(df['Temp_Max'], errors='coerce')
    df['Temp_Min'] = pd.to_numeric(df['Temp_Min'], errors='coerce')
    df['Humidity'] = pd.to_numeric(df['Humidity'], errors='coerce')
    
    # Remove outliers
    for col in ['Temp_Max', 'Temp_Min', 'Humidity']:
        q1 = df[col].quantile(0.01)
        q99 = df[col].quantile(0.99)
        df[col] = df[col].clip(q1, q99)
    
    # Drop rows with NaN
    df = df.dropna()
    
    return df


def main():
    print("\n" + "="*60)
    print("LSTM CLIMATE MODEL TRAINING")
    print("="*60)
    
    # Load data
    print("\n1. Loading climate data...")
    DATA_PATH = 'data.csv'
    
    if not os.path.exists(DATA_PATH):
        print(f"Error: Data file not found at {DATA_PATH}")
        return
    
    raw = pd.read_csv(DATA_PATH)
    print(f"   Loaded {len(raw)} rows")
    
    # Rename columns
    raw.columns = ['Date', 'Rainfall', 'Temp_Max', 'Temp_Min', 'Humidity']
    
    # Direct data cleaning
    raw = clean_data_directly(raw)
    print(f"   After cleaning: {len(raw)} rows")
    
    # Convert Date
    raw['Date'] = pd.to_datetime(raw['Date'], errors='coerce')
    raw = raw.dropna(subset=['Date'])
    
    # Calculate mean temperature
    raw['Temp_mean'] = (raw['Temp_Max'] + raw['Temp_Min']) / 2
    
    # Extract year and month
    raw['Year'] = raw['Date'].dt.year
    raw['Month'] = raw['Date'].dt.month
    
    # Filter years 1951-2024
    raw = raw[(raw['Year'] >= 1951) & (raw['Year'] <= 2024)]
    
    # Monthly aggregation
    print("\n2. Aggregating to monthly data...")
    monthly = raw.groupby(['Year', 'Month']).agg({
        'Rainfall': 'sum',
        'Temp_mean': 'mean',
        'Humidity': 'mean'
    }).reset_index()
    
    monthly['Date'] = pd.to_datetime(monthly['Year'].astype(str) + '-' + 
                                      monthly['Month'].astype(str) + '-01')
    
    print(f"   Monthly data shape: {monthly.shape}")
    print(f"   Date range: {monthly['Date'].min()} to {monthly['Date'].max()}")
    
    # Check for any remaining issues
    print("\n3. Validating data quality...")
    for var in ['Rainfall', 'Temp_mean', 'Humidity']:
        invalid = monthly[var].isna().sum()
        print(f"   {var}: {invalid} missing values")
        if invalid > 0:
            monthly[var] = monthly[var].interpolate()
    
    # Train LSTM models
    print("\n4. Training LSTM models...")
    print("   This may take 5-10 minutes...")
    
    try:
        results, metrics = train_all_lstm_models(monthly, train_cutoff_year=2018)
        
        print("\n" + "="*60)
        print("✅ TRAINING COMPLETE!")
        print("="*60)
        print("\n📊 Model Performance Summary:")
        print("-"*40)
        
        for var, metric in metrics.items():
            if metric['MAE'] > 0:
                print(f"\n{var}:")
                print(f"   MAE:  {metric['MAE']}")
                print(f"   RMSE: {metric['RMSE']}")
                print(f"   MAPE: {metric['MAPE']}%")
                print(f"   R²:   {metric['R2']}")
        
        print("\n✅ LSTM models saved to: saved_models/lstm/")
        print("\n🎯 You can now use the LSTM prediction feature at: /lstm_analysis")
        
    except Exception as e:
        print(f"\n❌ Error during training: {e}")
        print("\nTroubleshooting:")
        print("1. Check that you have enough data (at least 2 years)")
        print("2. Verify all values are numeric")
        print("3. Try restarting Python kernel")


if __name__ == '__main__':
    main()