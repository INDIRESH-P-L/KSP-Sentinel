import pandas as pd
import random
from datetime import datetime

try:
    from statsmodels.tsa.arima.model import ARIMA as StatsARIMA
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

try:
    from sklearn.linear_model import LinearRegression
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

class CrimeForecaster:
    def __init__(self):
        pass

    def forecast_district_crimes(self, historical_data, forecast_months=3):
        """
        historical_data: List of dicts with {"year": Y, "month": M, "count": C}
        Returns: List of dicts with {"year": Y, "month": M, "predicted_count": C, "confidence": Conf}
        """
        if len(historical_data) < 6 or (not HAS_STATSMODELS and not HAS_SKLEARN):
            return self._heuristic_forecast(historical_data, forecast_months)
            
        df = pd.DataFrame(historical_data)
        df = df.sort_values(by=["year", "month"])
        
        df["date"] = df.apply(lambda r: datetime(int(r["year"]), int(r["month"]), 1), axis=1)
        df.set_index("date", inplace=True)
        
        counts = df["count"].values.astype(float)
        predictions = []
        last_date = df.index[-1]
        
        if HAS_STATSMODELS:
            try:
                model = StatsARIMA(counts, order=(1, 1, 1))
                model_fit = model.fit()
                forecast = model_fit.forecast(steps=forecast_months)
                
                for idx, val in enumerate(forecast):
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
                        "confidence": round(float(0.85 - (idx * 0.05)), 2)
                    })
                return predictions
            except Exception as e:
                print(f"Statsmodels ARIMA failed: {e}")
                
        if HAS_SKLEARN:
            try:
                import numpy as np
                X = np.arange(len(counts)).reshape(-1, 1)
                y = counts
                months = df.index.month.values
                month_dummies = pd.get_dummies(months).values
                
                reg = LinearRegression()
                X_features = np.hstack([X, month_dummies]) if month_dummies.shape[1] > 0 else X
                reg.fit(X_features, y)
                
                for idx in range(1, forecast_months + 1):
                    next_date = last_date + pd.DateOffset(months=idx)
                    next_x = len(counts) + idx - 1
                    future_month = next_date.month
                    if month_dummies.shape[1] > 0:
                        future_dummies = np.zeros(month_dummies.shape[1])
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
        if not historical_data:
            counts = [10]
            last_date = datetime.now()
        else:
            sorted_data = sorted(historical_data, key=lambda x: (x.get("year", 2024), x.get("month", 1)))
            counts = [item.get("count", 0) for item in sorted_data]
            last_item = sorted_data[-1]
            last_date = datetime(int(last_item.get("year", 2024)), int(last_item.get("month", 1)), 1)

        recent = counts[-3:] if len(counts) >= 3 else counts
        last_val = sum(recent) / len(recent) if recent else 10.0
        
        predictions = []
        for idx in range(1, forecast_months + 1):
            next_month = last_date.month + idx
            next_year = last_date.year
            while next_month > 12:
                next_month -= 12
                next_year += 1

            val = last_val * (1.0 + random.uniform(-0.05, 0.05))
            predictions.append({
                "year": next_year,
                "month": next_month,
                "predicted_count": max(0, int(round(val))),
                "confidence": round(0.70 - (idx * 0.05), 2)
            })
        return predictions
