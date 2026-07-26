from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import requests
import os

router = APIRouter(prefix="/grok", tags=["Grok Insights"])

class ForecastInsightRequest(BaseModel):
    district_name: str
    category_name: str
    model_name: str
    historical_data: List[Dict[str, Any]]
    forecast_data: List[Any]

class SociologicalInsightRequest(BaseModel):
    district_name: str
    risk_score: float
    urbanization_rate: float
    top_factors: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]

def call_grok_api(system_prompt: str, user_prompt: str) -> str:
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROK_API_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 250
    }

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if e.response is not None:
            error_msg = f"{e.response.status_code} - {e.response.text}"
        raise HTTPException(status_code=502, detail=f"Failed to fetch insight from Grok API: {error_msg}")

@router.post("/forecast-insight")
def generate_forecast_insight(request: ForecastInsightRequest):
    system_prompt = (
        "You are an expert crime data analyst and law enforcement strategist. "
        "Analyze the provided historical and forecasted crime data. "
        "Provide a concise, 2-3 sentence strategic summary and a specific recommendation "
        "for police commanders on how to allocate resources or conduct operations based on the trend. "
        "Do not use markdown, just plain text."
    )
    
    historical_summary = ", ".join([f"{item.get('label', 'Unknown')}: {item.get('actual', 0)}" for item in request.historical_data[-3:]])
    forecast_summary = ", ".join([f"Month {idx+1}: {val}" for idx, val in enumerate(request.forecast_data)])
    
    user_prompt = (
        f"District: {request.district_name}\n"
        f"Crime Category: {request.category_name}\n"
        f"Model: {request.model_name}\n"
        f"Recent History: {historical_summary}\n"
        f"Forecasted next 3 months: {forecast_summary}\n\n"
        "Please provide your strategic summary and recommendation."
    )
    
    insight = call_grok_api(system_prompt, user_prompt)
    return {"insight": insight}

@router.post("/sociological-insight")
def generate_sociological_insight(request: SociologicalInsightRequest):
    system_prompt = (
        "You are an expert sociologist and criminologist specializing in urban data. "
        "Analyze the provided socioeconomic factors and anomalies for a district. "
        "Provide a concise, 2-3 sentence insight explaining potential root causes for "
        "its risk score, and suggest one community-level intervention. "
        "Do not use markdown, just plain text."
    )
    
    factors_summary = ", ".join([f"{f.get('key', 'Unknown')}: {f.get('value', 0)}" for f in request.top_factors])
    anomalies_summary = ", ".join([f"{a.get('type', 'Unknown')} ({a.get('severity', 'Unknown')})" for a in request.anomalies])
    
    user_prompt = (
        f"District: {request.district_name}\n"
        f"Overall Risk Score: {request.risk_score}/100\n"
        f"Urbanization Rate: {request.urbanization_rate}%\n"
        f"Key Correlated Factors: {factors_summary}\n"
        f"Recent Anomalies: {anomalies_summary}\n\n"
        "Please provide your sociological insight."
    )
    
    insight = call_grok_api(system_prompt, user_prompt)
    return {"insight": insight}
