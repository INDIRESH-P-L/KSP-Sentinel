from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.core.security import deny_admin_from_crime_data
from app.core.rate_limit import limiter
from app.core.guardrails import check_query, redact_response
from app.core.audit import log_action
from chatbot.gemini_client import InvestigationAssistant

router = APIRouter(prefix="/chatbot", tags=["AI Copilot Chatbot"])

def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

@router.post("/query")
@limiter.limit("20/minute")
def chat_with_assistant(
    request: Request,
    message: str = Body(..., embed=True, max_length=2000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data)
):
    """Processes natural language questions from officers and returns answers"""
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "unknown")[:500]

    block_reason = check_query(message)
    if block_reason:
        log_action(db, current_user.get("id"), "chatbot_guardrail_blocked", "chatbot", ip, ua,
                   success=False, username=current_user.get("username"), detail=block_reason)
        return {"query": message, "reply": None, "error": f"Access denied - {block_reason}"}

    assistant = InvestigationAssistant(db)
    response_text = assistant.answer_query(message)
    response_text = redact_response(response_text)

    log_action(db, current_user.get("id"), "chatbot_query", "chatbot", ip, ua,
               success=True, username=current_user.get("username"))

    return {
        "query": message,
        "reply": response_text
    }
