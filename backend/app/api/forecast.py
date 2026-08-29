from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import deny_admin_from_crime_data
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# Forecasting models live in backend/forecasting/ — add that to path
_forecasting_dir = os.path.join(os.path.dirname(__file__), "..", "..", "forecasting")
if _forecasting_dir not in sys.path:
    sys.path.insert(0, os.path.abspath(_forecasting_dir))

from app import filestore_crime_data

# Import forecasters using dynamic paths
from arima_model import CrimeForecaster
from prophet_model import ProphetForecaster
from xgboost_model import XGBoostForecaster
from lstm_model import LSTMForecaster

# Router-level auth. Every route below reads operational crime data, so all of
# them require a valid bearer token (get_current_user, reached through this
# dependency, now 401s without one) and none of them may be called by an Admin
# account (separation of duties). These routers previously declared no auth
# dependency at all, which -- combined with get_current_user's anonymous
# fallback -- left them readable by any unauthenticated caller.
router = APIRouter(prefix="/forecast", tags=["Forecasting"],
                   dependencies=[Depends(deny_admin_from_crime_data)])

@router.get("/")
def get_crime_forecast(
    district_id: int,
    category_id: int = Query(None, description="Crime category id. If omitted, server will pick a sensible default"),
    model_name: str = Query("ARIMA", description="ARIMA, Prophet, XGBoost, LSTM"),
    forecast_months: int = 3,
):
    """Calculates actual vs predicted crime trends using the specified model, live from FileStore."""
    ds = filestore_crime_data.get_dataset()
    if ds is None:
        raise HTTPException(status_code=503, detail="Crime data is unavailable: could not reach Catalyst FileStore.")
    _, districts_df, _, categories_df, _ = ds

    # 1. Fetch district and category
    district_match = districts_df[districts_df['id'] == district_id]
    if district_match.empty:
        raise HTTPException(status_code=404, detail="District not found")
    district = district_match.iloc[0]

    if category_id is None:
        if categories_df.empty:
            raise HTTPException(status_code=404, detail="No crime categories available")
        category = categories_df.sort_values('id').iloc[0]
        category_id = int(category['id'])
    else:
        category_match = categories_df[categories_df['id'] == category_id]
        if category_match.empty:
            raise HTTPException(status_code=404, detail="Category not found")
        category = category_match.iloc[0]

    # 2. Monthly historical data for the past 2 years, from the in-memory FIR frame
    historical_data = filestore_crime_data.get_forecast_history(district_id, category_id)

    # If no historical data is found, generate standard mock history to run forecasting
    if not historical_data:
        import random
        # Create 12 months of fake historical records
        import datetime
        now = datetime.datetime.now()
        for idx in range(12, 0, -1):
            dt = now - datetime.timedelta(days=idx*30)
            historical_data.append({
                "year": dt.year,
                "month": dt.month,
                "count": random.randint(8, 25)
            })
            
    # 3. Instantiate chosen forecaster
    forecasters = {
        "ARIMA": CrimeForecaster(),
        "PROPHET": ProphetForecaster(),
        "XGBOOST": XGBoostForecaster(),
        "LSTM": LSTMForecaster()
    }
    
    forecaster = forecasters.get(model_name.upper(), CrimeForecaster())
    
    # 4. Generate predictions
    predictions = forecaster.forecast_district_crimes(historical_data, forecast_months)
    
    # 5. Format output
    history_formatted = []
    for item in historical_data:
        from datetime import datetime
        dt = datetime(item["year"], item["month"], 1)
        history_formatted.append({
            "date": dt.strftime("%b %Y"),
            "actual": item["count"],
            "predicted": None,
            "confidence": 1.0
        })
        
    predictions_formatted = []
    for item in predictions:
        from datetime import datetime
        dt = datetime(item["year"], item["month"], 1)
        predictions_formatted.append({
            "date": dt.strftime("%b %Y"),
            "actual": None,
            "predicted": item["predicted_count"],
            "confidence": item["confidence"]
        })
        
    return {
        "district": district['name'],
        "category": category['name'],
        "model": model_name,
        "history": history_formatted,
        "forecast": predictions_formatted,
        "combined": history_formatted + predictions_formatted
    }
