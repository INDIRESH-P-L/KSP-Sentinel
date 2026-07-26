"""
chatbot_grok.py
-----------------
Grok-powered AI Copilot chatbot for KSP Sentinel.

Unlike the previous Gemini chatbot (which used a SQLite database), this endpoint:
1. Pulls live real-time context from the in-memory Zoho Catalyst FileStore dataset
   (total FIRs, top crime districts, top categories, recent monthly trends, etc.)
2. Injects that context into the Grok system prompt for grounded, factual answers
3. Handles multi-turn conversation history sent by the frontend
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
import requests
import os

from app import filestore_crime_data

router = APIRouter(prefix="/grok", tags=["Grok Chatbot"])


class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str

class ChatbotRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


def _build_live_context() -> str:
    """Pull real statistics from the Zoho Catalyst FileStore dataset for the system prompt."""
    ds = filestore_crime_data.get_dataset()
    if ds is None:
        return "Note: The real-time crime dataset is currently unavailable — provide general guidance."

    df, districts_df, stations_df, categories_df, *_ = ds

    total_firs   = len(df)
    total_dist   = len(districts_df)
    total_stat   = len(stations_df)

    # Top 5 crime districts by FIR volume
    top_dist_text = "N/A"
    if "District_Name" in df.columns:
        top = df["District_Name"].value_counts().head(5)
        top_dist_text = ", ".join([f"{d}: {c}" for d, c in top.items()])

    # Top 5 crime categories
    top_cat_text = "N/A"
    if "crime_category" in df.columns:
        top = df["crime_category"].value_counts().head(5)
        top_cat_text = ", ".join([f"{c}: {n}" for c, n in top.items()])

    # Current year FIR volume (approximate using Year column)
    curr_year_firs = "N/A"
    if "Year" in df.columns:
        import datetime
        yr = datetime.datetime.now().year
        curr_year_firs = int(df[df["Year"] == yr].shape[0])

    # Solve rate
    solve_rate = "N/A"
    if "Status" in df.columns:
        solved = df["Status"].str.lower().isin(["true", "solved", "closed"]).sum()
        solve_rate = f"{round(solved / total_firs * 100, 1)}%"

    # District risk scores (from the districts table if available)
    high_risk_districts = "N/A"
    if "risk_score" in districts_df.columns and "name" in districts_df.columns:
        top_risk = districts_df.nlargest(5, "risk_score")[["name", "risk_score"]]
        high_risk_districts = ", ".join([f"{r['name']} ({r['risk_score']}/100)" for _, r in top_risk.iterrows()])

    context = f"""
=== KSP SENTINEL LIVE DATASET CONTEXT (Zoho Catalyst, Karnataka) ===
Total FIRs in Database   : {total_firs:,}
Total Districts           : {total_dist}
Total Police Stations     : {total_stat}
FIRs This Year            : {curr_year_firs}
Overall Case Solve Rate   : {solve_rate}

Top 5 Districts by FIR Volume:
  {top_dist_text}

Top 5 Crime Categories:
  {top_cat_text}

Highest Risk Districts (by Risk Score):
  {high_risk_districts}
=== END CONTEXT ===
"""
    return context.strip()


def _call_grok(system_prompt: str, messages: List[dict], max_tokens: int = 700) -> str:
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROK_API_KEY is not configured.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "temperature": 0.5,
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
            detail=f"Grok API error: {error_msg}",
        )


@router.post("/chatbot-query")
def grok_chatbot_query(request: ChatbotRequest):
    """
    Grok-powered AI Copilot chatbot.
    
    Pulls real Karnataka crime data from the Zoho Catalyst FileStore dataset
    and injects it into the Grok system prompt so officers get factual,
    grounded answers about real crime trends, districts, and patterns.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Inject live real data into system prompt
    live_context = _build_live_context()

    system_prompt = f"""You are the KSP Sentinel AI Copilot — an advanced investigative intelligence assistant for the Karnataka State Police. You have direct access to the real-time KSP Sentinel crime database powered by Zoho Catalyst.

{live_context}

Your capabilities:
- Answer questions about crime statistics, trends, and patterns in Karnataka
- Identify high-risk districts, repeat offenders, and emerging crime patterns  
- Explain risk scores, forecast models, and socioeconomic correlations
- Guide officers through investigation strategies and resource allocation
- Cross-reference FIR data, district profiles, and category breakdowns

Rules:
- Always ground your answers in the real data shown above when relevant
- Be concise, professional, and actionable — you are talking to police officers
- If you don't know something specific, say so rather than fabricating data
- Format lists with dashes (not bullet symbols)
- Keep responses under 300 words unless a detailed breakdown is requested"""

    # Build message list for multi-turn
    messages = []
    for h in (request.history or []):
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": request.message})

    reply = _call_grok(system_prompt, messages, max_tokens=700)
    return {"query": request.message, "reply": reply}
