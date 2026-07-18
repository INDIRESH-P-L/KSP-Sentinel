import numpy as np
import pandas as pd
import random
from datetime import datetime

try:
    from statsmodels.tsa.arima.model import ARIMA as StatsARIMA
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    from sklearn.linear_model import LinearRegression

class CrimeForecaster:
    def __init__(self):
        pass

    def forecast_district_crimes(self, historical_data, forecast_months=3):
        """
        historical_data: List of dicts with {"year": Y, "month": M, "count": C}
        Returns: List of dicts with {"year": Y, "month": M, "predicted_count": C, "confidence": Conf}
        """
        if len(historical_data) < 6:
            # Not enough data for statistical time series, use a simple heuristic trend + seasonality
            return self._heuristic_forecast(historical_data, forecast_months)
            
        df = pd.DataFrame(historical_data)
        df = df.sort_values(by=["year", "month"])
        
        # Prepare date index
        df["date"] = df.apply(lambda r: datetime(int(r["year"]), int(r["month"]), 1), axis=1)
        df.set_index("date", inplace=True)
        
        counts = df["count"].values.astype(float)
        
        predictions = []
        last_date = df.index[-1]
        
        if HAS_STATSMODELS:
            try:
                # Run ARIMA (1, 1, 1) or AutoReg
                model = StatsARIMA(counts, order=(1, 1, 1))
                model_fit = model.fit()
                forecast = model_fit.forecast(steps=forecast_months)
                
                for idx, val in enumerate(forecast):
                    # Calculate next dates
                    m_offset = idx + 1
                    next_month = last_date.month + m_offset
                    next_year = last_date.year
                    while next_month > 12:
                        next_month -= 12
                        next_year += 1
                        
                    predicted_count = max(0, int(round(val)))
                    predictions.append({
                        "year": next_year,
                        "month": next_month,
                        "predicted_count": predicted_count,
                        "confidence": round(float(0.85 - (idx * 0.05)), 2) # Decaying confidence
                    })
                return predictions
            except Exception as e:
                print(f"Statsmodels ARIMA failed, using regression fallback: {e}")
                
        # Scikit-Learn Regression fallback (trend + seasonality)
        try:
            X = np.arange(len(counts)).reshape(-1, 1)
            y = counts
            
            # Simple seasonality feature (month of year)
            months = df.index.month.values
            month_dummies = pd.get_dummies(months).values
            
            # Fit linear model on trend + monthly seasonality
            reg = LinearRegression()
            X_features = np.hstack([X, month_dummies]) if month_dummies.shape[1] > 0 else X
            reg.fit(X_features, y)
            
            # Predict future
            for idx in range(1, forecast_months + 1):
                next_date = last_date + pd.DateOffset(months=idx)
                next_x = len(counts) + idx - 1
                
                # Setup monthly seasonal dummies for future prediction
                future_month = next_date.month
                if month_dummies.shape[1] > 0:
                    future_dummies = np.zeros(month_dummies.shape[1])
                    # map future_month back to dummy index (0 to 11 if all months present)
                    unique_months = sorted(list(set(months)))
                    if future_month in unique_months:
                        future_dummies[unique_months.index(future_month)] = 1
                    future_features = np.hstack([[next_x], future_dummies]).reshape(1, -1)
                else:
                    future_features = np.array([[next_x]])
                    
                val = reg.predict(future_features)[0]
                predicted_count = max(0, int(round(val)))
                
                predictions.append({
                    "year": next_date.year,
                    "month": next_date.month,
                    "predicted_count": predicted_count,
                    "confidence": round(0.80 - (idx * 0.04), 2)
                })
            return predictions
        except Exception as e:
            print(f"Regression fallback failed: {e}")
            return self._heuristic_forecast(historical_data, forecast_months)

    def _heuristic_forecast(self, historical_data, forecast_months):
        df = pd.DataFrame(historical_data)
        df = df.sort_values(by=["year", "month"])
        counts = df["count"].values if not df.empty else [10]
        
        # Heuristic: average of last 3 months + random trend
        last_val = np.mean(counts[-3:]) if len(counts) >= 3 else np.mean(counts)
        last_date = datetime(int(df.iloc[-1]["year"]), int(df.iloc[-1]["month"]), 1) if not df.empty else datetime.now()
        
        predictions = []
        for idx in range(1, forecast_months + 1):
            next_date = last_date + pd.DateOffset(months=idx)
            val = last_val * (1.0 + random.uniform(-0.05, 0.05))
            predictions.append({
                "year": next_date.year,
                "month": next_date.month,
                "predicted_count": max(0, int(round(val))),
                "confidence": round(0.70 - (idx * 0.05), 2)
            })
        return predictions
