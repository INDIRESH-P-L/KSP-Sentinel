from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import requests
import os

from app import filestore_crime_data

router = APIRouter(prefix="/grok", tags=["Grok Insights"])


# ── Request models ────────────────────────────────────────────────────────────

class ForecastInsightRequest(BaseModel):
    district_name: str
    category_name: str
    model_name: str
    historical_data: List[Dict[str, Any]]  # [{label, actual}, ...]
    forecast_data: List[Any]               # predicted values

class SociologicalInsightRequest(BaseModel):
    district_name: str
    risk_score: float
    urbanization_rate: float
    top_factors: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]

class SearchAnalysisRequest(BaseModel):
    query: str
    results: List[Dict[str, Any]]   # list of FIR search-result dicts


# ── Core Grok caller ─────────────────────────────────────────────────────────

def call_grok_api(system_prompt: str, user_prompt: str, max_tokens: int = 600) -> str:
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROK_API_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.6,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            error_msg = f"{e.response.status_code} - {e.response.text[:400]}"
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch insight from Grok API: {error_msg}",
        )


# ── Helpers: pull real data from FileStore ───────────────────────────────────

def _real_district_stats(district_name: str) -> Dict[str, Any]:
    """Return real FIR-level stats for the district from the in-memory dataset."""
    ds = filestore_crime_data.get_dataset()
    if ds is None:
        return {}

    df, districts_df, stations_df, categories_df, *_ = ds
    d_row = districts_df[districts_df["name"].str.lower() == district_name.lower()]
    if d_row.empty:
        return {}

    district_id = int(d_row.iloc[0]["id"])
    subset = df[df["district_id"] == district_id] if "district_id" in df.columns else df[df["District_Name"].str.lower() == district_name.lower()]

    total = len(subset)
    solved = int(subset["Status"].str.lower().isin(["true", "solved", "closed"]).sum()) if "Status" in subset.columns else 0
    top_crimes = []
    if "crime_category" in subset.columns:
        top_crimes = subset["crime_category"].value_counts().head(5).to_dict()

    return {
        "total_firs": total,
        "solved": solved,
        "solve_rate_pct": round(solved / total * 100, 1) if total else 0,
        "top_crimes": top_crimes,
        "station_count": int(stations_df[stations_df["district_name"].str.lower() == district_name.lower()].shape[0]) if "district_name" in stations_df.columns else 0,
    }


def _real_forecast_history(district_name: str, category_name: str) -> List[Dict[str, Any]]:
    """Return real monthly FIR counts for the district+category combo."""
    ds = filestore_crime_data.get_dataset()
    if ds is None:
        return []

    df, districts_df, _, categories_df, *_ = ds

    d_row = districts_df[districts_df["name"].str.lower() == district_name.lower()]
    if d_row.empty:
        return []
    district_id = int(d_row.iloc[0]["id"])

    c_row = categories_df[categories_df["name"].str.lower().str.contains(category_name.lower()[:10])]
    category_id = int(c_row.iloc[0]["id"]) if not c_row.empty else None

    history = filestore_crime_data.get_forecast_history(district_id, category_id)
    return history[-12:] if history else []


def _statewide_summary() -> Dict[str, Any]:
    """Return high-level Karnataka-wide real stats."""
    ds = filestore_crime_data.get_dataset()
    if ds is None:
        return {}

    df, districts_df, stations_df, categories_df, *_ = ds

    total = len(df)
    top_districts = []
    if "District_Name" in df.columns:
        top_districts = df["District_Name"].value_counts().head(5).to_dict()
    top_categories = {}
    if "crime_category" in df.columns:
        top_categories = df["crime_category"].value_counts().head(5).to_dict()

    return {
        "total_firs_in_dataset": total,
        "total_districts": len(districts_df),
        "total_stations": len(stations_df),
        "top_crime_districts": top_districts,
        "top_crime_categories": top_categories,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/forecast-insight")
def generate_forecast_insight(request: ForecastInsightRequest):
    """Grok analysis of crime forecast data, enriched with real FileStore history."""
    # Pull real historical data from FileStore to supplement what the frontend sent
    real_history = _real_forecast_history(request.district_name, request.category_name)
    real_stats   = _real_district_stats(request.district_name)

    # Build real monthly summary
    if real_history:
        monthly_lines = ", ".join(
            [f"{h.get('year')}-{h.get('month'):02d}: {h.get('count')} cases" for h in real_history[-6:]]
        )
        data_note = f"(Real Catalyst dataset — last 6 months: {monthly_lines})"
    else:
        monthly_lines = ", ".join(
            [f"{item.get('label', 'Unknown')}: {item.get('actual', 0)}" for item in request.historical_data[-6:]]
        )
        data_note = f"(Frontend-provided data: {monthly_lines})"

    forecast_summary = ", ".join(
        [f"Month {idx+1}: {val}" for idx, val in enumerate(request.forecast_data)]
    )

    system_prompt = (
        "You are an expert crime data analyst and senior strategic advisor for the Karnataka State Police. "
        "You have access to real FIR data from the Zoho Catalyst database covering all 31 districts of Karnataka. "
        "Analyze the historical and forecasted crime trends for the given district and crime category. "
        "Provide a 3-4 sentence strategic analysis explaining the trend, its likely causes, and a specific "
        "resource allocation recommendation for police commanders (e.g. patrol deployment, preventive operations, "
        "staffing adjustments). Reference actual district conditions where possible. Be direct and actionable. "
        "Do not use markdown formatting — plain text only."
    )

    user_prompt = (
        f"District: {request.district_name}\n"
        f"Crime Category: {request.category_name}\n"
        f"Forecasting Model: {request.model_name}\n"
        f"Historical Crime Data {data_note}\n"
        f"AI Forecast — Next 3 Months: {forecast_summary}\n"
        f"District Stats: Total FIRs={real_stats.get('total_firs', 'N/A')}, "
        f"Solve Rate={real_stats.get('solve_rate_pct', 'N/A')}%, "
        f"Stations={real_stats.get('station_count', 'N/A')}, "
        f"Top Crimes={real_stats.get('top_crimes', {})}\n\n"
        "Provide your strategic analysis and recommendation for the Superintendent of Police."
    )

    insight = call_grok_api(system_prompt, user_prompt, max_tokens=600)
    return {"insight": insight, "real_data_used": bool(real_history)}


@router.post("/sociological-insight")
def generate_sociological_insight(request: SociologicalInsightRequest):
    """Grok sociological analysis enriched with real district data from FileStore."""
    real_stats = _real_district_stats(request.district_name)
    state_summary = _statewide_summary()

    factors_summary  = ", ".join([f"{f.get('key', f.get('metric', 'Unknown'))}: {f.get('value', 0):.3f}" for f in request.top_factors[:6]])
    anomalies_summary = ", ".join([f"{a.get('district', 'Unknown')} ({a.get('severity', 'N/A')}, z={a.get('z_score', 0):.1f}σ)" for a in request.anomalies[:4]])

    system_prompt = (
        "You are a senior criminologist and sociologist specializing in urban crime patterns in South India. "
        "You analyze data from the Karnataka State Police Sentinel system backed by real FIR records. "
        "For the given district, explain the sociological and socioeconomic root causes driving the crime risk score. "
        "Reference urbanization pressures, literacy gaps, or economic conditions. "
        "Suggest one concrete community-level intervention AND one police operational response. "
        "Be specific, evidence-grounded, and limit your response to 4-5 sentences. Plain text only — no markdown."
    )

    user_prompt = (
        f"District: {request.district_name}\n"
        f"Risk Score: {request.risk_score}/100\n"
        f"Urbanization Rate: {request.urbanization_rate}%\n"
        f"Top Correlated Socioeconomic Factors: {factors_summary}\n"
        f"Active Anomaly Alerts: {anomalies_summary}\n"
        f"Real Dataset — Total FIRs for District: {real_stats.get('total_firs', 'N/A')}, "
        f"Solve Rate: {real_stats.get('solve_rate_pct', 'N/A')}%, "
        f"Top Crime Types: {real_stats.get('top_crimes', {})}\n"
        f"Karnataka State Context: {state_summary.get('total_firs_in_dataset', 'N/A')} total FIRs across "
        f"{state_summary.get('total_districts', 'N/A')} districts\n\n"
        "Provide your sociological analysis and recommendations."
    )

    insight = call_grok_api(system_prompt, user_prompt, max_tokens=600)
    return {"insight": insight, "real_data_used": bool(real_stats)}


@router.post("/search-analysis")
def generate_search_analysis(request: SearchAnalysisRequest):
    """Grok analysis of semantic search results — patterns, links, and investigative angles."""
    if not request.results:
        raise HTTPException(status_code=400, detail="No search results provided to analyse.")

    state_summary = _statewide_summary()

    # Build a brief of the matched FIRs
    case_briefs = []
    for i, r in enumerate(request.results[:8], 1):
        desc   = (r.get("description") or "")[:200]
        score  = r.get("score", 0)
        station = r.get("station") or r.get("unit_name") or "Unknown"
        cat    = r.get("subcategory") or r.get("crime_category") or "Unknown"
        date   = r.get("date_reported") or r.get("date_occurred") or "Unknown"
        case_briefs.append(
            f"  Case {i}: Station={station}, Category={cat}, Date={date}, "
            f"Similarity={score:.2f}, Description: {desc}"
        )
    cases_text = "\n".join(case_briefs)

    system_prompt = (
        "You are a senior investigative analyst for the Karnataka State Police with access to the KSP Sentinel crime database. "
        "You are analysing semantic search results from real First Information Reports (FIRs) filed across Karnataka. "
        "Your job is to: (1) identify common patterns or modus operandi across the matched cases, "
        "(2) flag any temporal or geographic clustering that may indicate a criminal network or repeat offender, "
        "(3) suggest 2-3 concrete investigative follow-up actions for the investigating officer. "
        "Be specific and evidence-based. Use plain text, no markdown."
    )

    user_prompt = (
        f"Officer's Search Query: \"{request.query}\"\n"
        f"Number of Matching FIRs: {len(request.results)}\n"
        f"Karnataka Dataset Context: {state_summary.get('total_firs_in_dataset', 'N/A')} total FIRs, "
        f"top crime districts: {state_summary.get('top_crime_districts', {})}\n\n"
        f"Matched Cases:\n{cases_text}\n\n"
        "Provide your pattern analysis and investigative recommendations."
    )

    insight = call_grok_api(system_prompt, user_prompt, max_tokens=700)
    return {"insight": insight, "cases_analysed": len(request.results)}
