"""Pluggable model backends: SARIMA (statsmodels .pkl) and LSTM (Keras .h5). Same interface."""
import os
import time

import joblib
import numpy as np

import metrics

VARS = ['Rainfall', 'Temp_mean', 'Humidity']
MODEL_DIR = os.environ.get('MODEL_DIR', 'saved_models')


class Backend:
    name = 'base'

    def __init__(self):
        self.models = {}
        self.load_seconds = {}
        self.ready = False

    def load(self):
        for v in VARS:
            t = time.time()
            self.models[v] = self._load_var(v)
            self.load_seconds[v] = time.time() - t
            metrics.gauge('model_load_seconds', round(self.load_seconds[v], 4), model=self.name, variable=v)
        self.ready = all(m is not None for m in self.models.values())
        metrics.gauge('model_ready', int(self.ready), model=self.name)
        return self.ready

    def partial_ready(self):
        return {v: self.models.get(v) is not None for v in VARS}


class SarimaBackend(Backend):
    name = 'sarima'

    def _load_var(self, v):
        p = os.path.join(MODEL_DIR, f'sarima_{v.lower()}.pkl')
        return joblib.load(p) if os.path.exists(p) else None

    # Same physical monthly rainfall caps the app applies (utils/forecasting.py); step 1 = January 2024
    RAIN_CAPS = {1: 5.0, 2: 8.0, 3: 9.0, 4: 43.0, 5: 162.0, 6: 140.9, 7: 203.5, 8: 225.1, 9: 292.1, 10: 298.6,
                 11: 145.3, 12: 38.1}
    start_month = 1

    def forecast(self, series, steps):
        out = {v: np.maximum(np.asarray(m.get_forecast(steps=steps).predicted_mean, dtype=float), 0)
               for v, m in self.models.items()}
        caps = np.array([self.RAIN_CAPS[((k - 1) % 12) + 1] for k in range(1, steps + 1)])
        out['Rainfall'] = np.minimum(out['Rainfall'], caps)
        return out


class LstmBackend(Backend):
    name = 'lstm'

    def _load_var(self, v):
        from utils.lstm_model import load_lstm_model
        m, s = load_lstm_model(v)
        return (m, s) if m is not None else None

    def forecast(self, series, steps):
        from utils.lstm_model import forecast_lstm
        return {v: forecast_lstm(m, s, series[v], steps) for v, (m, s) in self.models.items()}
