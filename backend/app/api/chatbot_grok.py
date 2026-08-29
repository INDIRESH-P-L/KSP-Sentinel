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

from fastapi import APIRouter, Body, Depends, HTTPException
from app.core.security import deny_admin_from_crime_data
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
import requests
import os

from app import filestore_crime_data
from integrations import llm_provider

# Router-level auth. Every route below reads operational crime data, so all of
# them require a valid bearer token (get_current_user, reached through this
# dependency, now 401s without one) and none of them may be called by an Admin
# account (separation of duties). These routers previously declared no auth
# dependency at all, which -- combined with get_current_user's anonymous
# fallback -- left them readable by any unauthenticated caller.
router = APIRouter(prefix="/grok", tags=["Grok Chatbot"],
                   dependencies=[Depends(deny_admin_from_crime_data)])


class ChatMessage(BaseModel):
    # Literal, not str: a caller-supplied "system" turn was previously copied
    # verbatim into the outbound payload AFTER the trusted system prompt, and
    # OpenAI-compatible APIs honour the later system message -- so a client could
    # replace the guardrails with its own instructions.
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)

class ChatbotRequest(BaseModel):
    # Capped to match app/api/chatbot.py. Without a bound, a single request could
    # forward an unlimited prompt to a metered provider.
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatMessage] = Field(default_factory=list, max_length=20)


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
        solve_rate = f"{round(solved / total_firs * 100, 1)}%" if total_firs else "N/A"

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


def _call_grok(system_prompt: str, messages: List[dict], max_tokens: int = 1400) -> str:
    """Delegates to the shared provider layer.

    This used to be a private copy of the HTTP call that read GROK_API_KEY straight
    from os.environ (the configured variable is GROQ_API_KEY -- so the key was never
    found and every request 500'd), hardcoded a model name that contradicted
    GROQ_MODEL, echoed the provider's raw error body back to the caller, and caught
    only RequestException so a non-JSON 200 became an unhandled 500. All of that now
    lives once in integrations/llm_provider.py.

    max_tokens defaults high because the configured model is a reasoning model: it
    spends part of the budget thinking before emitting any answer text.
    """
    try:
        return llm_provider.chat(system_prompt, messages, max_tokens=max_tokens, temperature=0.5)
    except llm_provider.LLMUnavailable as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))



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
