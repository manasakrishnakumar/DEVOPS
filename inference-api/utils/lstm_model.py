"""
LSTM Model for Climate Forecasting
==================================
Complete LSTM implementation with proper data cleaning
"""

import numpy as np
import pandas as pd
import warnings
import joblib
import os
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib.pyplot as plt

# Set TensorFlow to use CPU only (avoid GPU issues)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.optimizers import Adam

# Suppress warnings
tf.get_logger().setLevel('ERROR')
warnings.filterwarnings('ignore')

MODELS_DIR = 'saved_models/lstm'
os.makedirs(MODELS_DIR, exist_ok=True)

# Set random seeds for reproducibility
np.random.seed(42)
tf.random.set_seed(42)


def clean_series(series):
    """
    Clean and validate time series data
    
    Parameters:
    -----------
    series : pd.Series
        Input time series
        
    Returns:
    --------
    pd.Series
        Cleaned series
    """
    # Remove any non-numeric values
    series = pd.to_numeric(series, errors='coerce')
    
    # Remove outliers (values beyond 3 standard deviations)
    mean = series.mean()
    std = series.std()
    series = series[(series - mean).abs() <= 3 * std]
    
    # Interpolate missing values
    series = series.interpolate(method='linear')
    
    # Forward fill any remaining NaN
    series = series.fillna(method='ffill').fillna(method='bfill')
    
    # Ensure all values are positive where applicable (rainfall)
    if series.name == 'Rainfall':
        series = series.clip(lower=0)
    
    return series


def create_sequences(data, seq_length=12):
    """
    Create sequences for LSTM training
    
    Parameters:
    -----------
    data : array-like
        Input time series data
    seq_length : int
        Number of previous time steps to use for prediction
        
    Returns:
    --------
    X, y : arrays
        Sequences and corresponding target values
    """
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data[i:i + seq_length])
        y.append(data[i + seq_length])
    return np.array(X), np.array(y)


def prepare_lstm_data(series, seq_length=12, train_split=0.8):
    """
    Prepare data for LSTM training with proper cleaning
    
    Parameters:
    -----------
    series : pd.Series
        Time series data
    seq_length : int
        Sequence length for LSTM
    train_split : float
        Proportion of data to use for training
        
    Returns:
    --------
    tuple
        (X_train, X_test, y_train, y_test, scaler)
    """
    # Clean the series first
    series = clean_series(series)
    
    # Convert to numpy array and ensure proper shape
    series_values = series.values.reshape(-1, 1)
    
    # Remove any remaining NaN or infinite values
    series_values = series_values[~np.isnan(series_values)]
    series_values = series_values[~np.isinf(series_values)]
    
    if len(series_values) < seq_length + 10:
        raise ValueError(f"Not enough data after cleaning. Got {len(series_values)} values, need at least {seq_length + 10}")
    
    # Scale the data
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(series_values)
    
    # Create sequences
    X, y = create_sequences(scaled_data.flatten(), seq_length)
    
    if len(X) == 0:
        raise ValueError("No sequences created. Data length insufficient.")
    
    # Split into train and test
    split_idx = int(len(X) * train_split)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    # Reshape for LSTM [samples, time steps, features]
    X_train = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
    X_test = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))
    
    return X_train, X_test, y_train, y_test, scaler


def build_lstm_model(seq_length, units=64, dropout=0.2):
    """
    Build LSTM model architecture
    
    Parameters:
    -----------
    seq_length : int
        Input sequence length
    units : int
        Number of LSTM units
    dropout : float
        Dropout rate for regularization
        
    Returns:
    --------
    model : tf.keras.Model
        Compiled LSTM model
    """
    model = Sequential([
        Input(shape=(seq_length, 1)),
        LSTM(units, return_sequences=True),
        Dropout(dropout),
        LSTM(units // 2, return_sequences=False),
        Dropout(dropout),
        Dense(32, activation='relu'),
        Dense(16, activation='relu'),
        Dense(1)
    ])
    
    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae', 'mape']
    )
    
    return model


def train_lstm_model(series, variable_name, seq_length=12, epochs=100, batch_size=32):
    """
    Train LSTM model for a climate variable
    
    Parameters:
    -----------
    series : pd.Series
        Time series data
    variable_name : str
        Name of the variable
    seq_length : int
        Sequence length
    epochs : int
        Number of training epochs
    batch_size : int
        Batch size for training
        
    Returns:
    --------
    tuple
        (model, scaler, history, metrics)
    """
    print(f"\n{'='*60}")
    print(f"Training LSTM Model for {variable_name}")
    print(f"{'='*60}")
    
    # Clean and prepare data
    series_clean = clean_series(series)
    print(f"Original data points: {len(series)}")
    print(f"Clean data points: {len(series_clean)}")
    
    try:
        X_train, X_test, y_train, y_test, scaler = prepare_lstm_data(series_clean, seq_length)
    except Exception as e:
        print(f"Error preparing data: {e}")
        # Fallback: use simpler approach
        print("Using fallback data preparation...")
        series_values = series_clean.values
        scaler = MinMaxScaler()
        scaled_data = scaler.fit_transform(series_values.reshape(-1, 1))
        
        # Simple sequence creation
        X, y = [], []
        for i in range(len(scaled_data) - seq_length):
            X.append(scaled_data[i:i+seq_length].flatten())
            y.append(scaled_data[i+seq_length])
        
        X = np.array(X)
        y = np.array(y)
        
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        X_train = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
        X_test = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))
    
    print(f"Training samples: {X_train.shape[0]}")
    print(f"Test samples: {X_test.shape[0]}")
    print(f"Sequence length: {seq_length}")
    
    # Build model
    model = build_lstm_model(seq_length)
    model.summary()
    
    # Callbacks
    callbacks = [
        EarlyStopping(
            monitor='val_loss',
            patience=20,
            restore_best_weights=True,
            verbose=1
        ),
        ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=10,
            min_lr=0.00001,
            verbose=1
        )
    ]
    
    # Train model
    print("\nTraining LSTM model...")
    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.2,
        callbacks=callbacks,
        verbose=1
    )
    
    # Evaluate on test set
    print("\nEvaluating model on test set...")
    y_pred = model.predict(X_test, verbose=0)
    
    # Inverse transform predictions
    y_test_actual = scaler.inverse_transform(y_test.reshape(-1, 1))
    y_pred_actual = scaler.inverse_transform(y_pred)
    
    # Calculate metrics
    mae = mean_absolute_error(y_test_actual, y_pred_actual)
    rmse = np.sqrt(mean_squared_error(y_test_actual, y_pred_actual))
    mape = np.mean(np.abs((y_test_actual - y_pred_actual) / (y_test_actual + 1e-8))) * 100
    r2 = r2_score(y_test_actual, y_pred_actual)
    
    metrics = {
        'MAE': round(mae, 3),
        'RMSE': round(rmse, 3),
        'MAPE': round(mape, 2),
        'R2': round(r2, 3)
    }
    
    print(f"\n📊 {variable_name} Model Performance:")
    print(f"   MAE:  {metrics['MAE']}")
    print(f"   RMSE: {metrics['RMSE']}")
    print(f"   MAPE: {metrics['MAPE']}%")
    print(f"   R²:   {metrics['R2']}")
    
    # Save model and scaler
    model_path = os.path.join(MODELS_DIR, f'lstm_{variable_name.lower()}.h5')
    scaler_path = os.path.join(MODELS_DIR, f'scaler_{variable_name.lower()}.pkl')
    
    model.save(model_path)
    joblib.dump(scaler, scaler_path)
    print(f"\n✅ Model saved to: {model_path}")
    print(f"✅ Scaler saved to: {scaler_path}")
    
    return model, scaler, history, metrics


def load_lstm_model(variable_name):
    """
    Load trained LSTM model and scaler
    
    Parameters:
    -----------
    variable_name : str
        Name of the variable
        
    Returns:
    --------
    tuple
        (model, scaler)
    """
    model_path = os.path.join(MODELS_DIR, f'lstm_{variable_name.lower()}.h5')
    scaler_path = os.path.join(MODELS_DIR, f'scaler_{variable_name.lower()}.pkl')
    
    if os.path.exists(model_path) and os.path.exists(scaler_path):
        try:
            model = load_model(model_path)
            scaler = joblib.load(scaler_path)
            return model, scaler
        except Exception as e:
            print(f"Error loading model for {variable_name}: {e}")
            return None, None
    
    return None, None


_STEP_FNS = {}


def _step_fn(model):
    """Compiled single-step inference (graph mode, avoids Keras predict() overhead; identical numbers)."""
    f = _STEP_FNS.get(id(model))
    if f is None:
        f = tf.function(lambda x: model(x, training=False), reduce_retracing=True)
        _STEP_FNS[id(model)] = f
    return f


def forecast_lstm(model, scaler, last_values, steps, seq_length=12):
    """
    Generate future forecasts using LSTM
    
    Parameters:
    -----------
    model : tf.keras.Model
        Trained LSTM model
    scaler : MinMaxScaler
        Fitted scaler for inverse transformation
    last_values : array
        Last known values (will use most recent seq_length values)
    steps : int
        Number of steps to forecast
    seq_length : int
        Sequence length used in training
        
    Returns:
    --------
    array
        Forecasted values
    """
    # Get the last seq_length values
    if len(last_values) > seq_length:
        last_sequence = last_values[-seq_length:]
    else:
        # Pad if necessary
        last_sequence = np.pad(last_values, (seq_length - len(last_values), 0), 'edge')
    
    # Scale the sequence
    scaled_sequence = scaler.transform(last_sequence.reshape(-1, 1)).flatten()
    
    forecasts = []
    current_sequence = scaled_sequence.copy()
    
    for _ in range(steps):
        # Reshape for prediction
        input_seq = current_sequence.reshape((1, seq_length, 1))
        
        # Predict next value (scaled)
        pred_scaled = float(np.asarray(_step_fn(model)(tf.constant(input_seq, dtype=tf.float32)))[0, 0])
        
        # Inverse transform to get actual value
        pred_value = scaler.inverse_transform([[pred_scaled]])[0, 0]
        forecasts.append(pred_value)
        
        # Update sequence for next prediction
        current_sequence = np.append(current_sequence[1:], pred_scaled)
    
    # Ensure non-negative values
    forecasts = np.maximum(forecasts, 0)
    
    return np.array(forecasts)


def train_all_lstm_models(monthly, train_cutoff_year=2018):
    """
    Train LSTM models for all climate variables
    
    Parameters:
    -----------
    monthly : pd.DataFrame
        Monthly climate data
    train_cutoff_year : int
        Year to split training and testing
        
    Returns:
    --------
    dict
        Trained models, scalers, and metrics
    """
    variables = ['Rainfall', 'Temp_mean', 'Humidity']
    results = {}
    metrics_summary = {}
    
    for var in variables:
        series = monthly.set_index('Date')[var]
        train_series = series[series.index.year <= train_cutoff_year]
        
        try:
            model, scaler, history, metrics = train_lstm_model(train_series, var)
            
            results[var] = {
                'model': model,
                'scaler': scaler,
                'history': history,
                'train_series': train_series
            }
            metrics_summary[var] = metrics
        except Exception as e:
            print(f"Error training {var}: {e}")
            results[var] = None
            metrics_summary[var] = {'MAE': 0, 'RMSE': 0, 'MAPE': 0, 'R2': 0}
    
    # Print summary
    print("\n" + "="*60)
    print("LSTM Model Training Summary")
    print("="*60)
    for var, metrics in metrics_summary.items():
        if metrics['MAE'] > 0:
            print(f"\n{var}:")
            print(f"   MAE:  {metrics['MAE']}")
            print(f"   RMSE: {metrics['RMSE']}")
            print(f"   MAPE: {metrics['MAPE']}%")
            print(f"   R²:   {metrics['R2']}")
    
    return results, metrics_summary


def forecast_with_lstm_models(models, scalers, last_sequences, steps=12, seq_length=12):
    """
    Generate forecasts using all LSTM models
    
    Parameters:
    -----------
    models : dict
        Dictionary of trained LSTM models
    scalers : dict
        Dictionary of fitted scalers
    last_sequences : dict
        Last known values for each variable
    steps : int
        Number of steps to forecast
    seq_length : int
        Sequence length
        
    Returns:
    --------
    pd.DataFrame
        Forecasted values
    """
    forecasts = {}
    
    for var, model in models.items():
        if model is not None and scalers.get(var) is not None:
            last_seq = last_sequences.get(var, np.zeros(seq_length))
            try:
                forecast = forecast_lstm(model, scalers[var], last_seq, steps, seq_length)
                forecasts[var] = forecast
            except Exception as e:
                print(f"Error forecasting {var}: {e}")
                forecasts[var] = np.zeros(steps)
        else:
            # Fallback forecast
            forecasts[var] = np.zeros(steps)
    
    forecast_df = pd.DataFrame({
        'Month': range(1, steps + 1),
        'Rainfall': forecasts.get('Rainfall', np.zeros(steps)),
        'Temp_mean': forecasts.get('Temp_mean', np.zeros(steps)),
        'Humidity': forecasts.get('Humidity', np.zeros(steps))
    })
    
    return forecast_df


if __name__ == '__main__':
    print("LSTM Model Module Loaded Successfully")
    print(f"TensorFlow version: {tf.__version__}")