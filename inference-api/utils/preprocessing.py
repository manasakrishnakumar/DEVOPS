"""
preprocessing.py
Data loading and preprocessing for Bangalore Climate Analytics
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')


def load_data(filepath: str) -> pd.DataFrame:
    """Load raw CSV dataset."""
    df = pd.read_csv(filepath)
    return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full preprocessing pipeline:
    - Parse dates
    - Rename columns
    - Handle missing values
    - Compute Temp_mean
    - Extract Year, Month
    """
    df = df.copy()

    # Rename columns to standard names
    df.columns = ['Date', 'Rainfall', 'Temp_Max', 'Temp_Min', 'Humidity']

    # Convert Date
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])

    # Replace trace rainfall values ('Tr', 'Trace') with 0 BEFORE numeric conversion
    df['Rainfall'] = df['Rainfall'].replace({'Tr': 0, 'Trace': 0, 'tr': 0, 'trace': 0})

    # Convert all climate columns to numeric (coerce any remaining non-numeric to NaN)
    for col in ['Rainfall', 'Temp_Max', 'Temp_Min', 'Humidity']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop duplicates
    df = df.drop_duplicates(subset='Date').reset_index(drop=True)

    # Handle missing values via interpolation then forward fill
    for col in ['Rainfall', 'Temp_Max', 'Temp_Min', 'Humidity']:
        df[col] = df[col].interpolate(method='linear').ffill().bfill()

    # Derived feature
    df['Temp_mean'] = (df['Temp_Max'] + df['Temp_Min']) / 2

    # Time features
    df['Year'] = df['Date'].dt.year
    df['Month'] = df['Date'].dt.month

    return df


def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily data to monthly."""
    monthly = df.groupby(['Year', 'Month']).agg(
        Rainfall=('Rainfall', 'sum'),
        Temp_Max=('Temp_Max', 'mean'),
        Temp_Min=('Temp_Min', 'mean'),
        Temp_mean=('Temp_mean', 'mean'),
        Humidity=('Humidity', 'mean')
    ).reset_index()

    # Create a proper date column (first of each month)
    monthly['Date'] = pd.to_datetime(
        monthly['Year'].astype(str) + '-' + monthly['Month'].astype(str).str.zfill(2) + '-01'
    )
    monthly = monthly.sort_values('Date').reset_index(drop=True)
    return monthly


def get_season(month: int) -> str:
    """Map month number to season."""
    if month in [12, 1, 2]:
        return 'Winter'
    elif month in [3, 4, 5]:
        return 'Summer'
    elif month in [6, 7, 8, 9]:
        return 'Monsoon'
    else:
        return 'Post-Monsoon'


def add_season(df: pd.DataFrame) -> pd.DataFrame:
    """Add Season column."""
    df = df.copy()
    df['Season'] = df['Month'].apply(get_season)
    return df


def add_decade(df: pd.DataFrame) -> pd.DataFrame:
    """Add Decade column."""
    df = df.copy()
    df['Decade'] = (df['Year'] // 10) * 10
    return df


if __name__ == '__main__':
    raw = load_data('data.csv')
    daily = preprocess(raw)
    monthly = aggregate_monthly(daily)
    monthly = add_season(monthly)
    monthly = add_decade(monthly)
    print("Daily shape:", daily.shape)
    print("Monthly shape:", monthly.shape)
    print(monthly.head())