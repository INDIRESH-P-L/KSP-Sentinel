from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai-engine"))
from backend.app.database.session import get_db
from backend.app.dependencies import get_current_user
from chatbot.gemini_client import InvestigationAssistant

router = APIRouter(prefix="/chatbot", tags=["AI Copilot Chatbot"])

@router.post("/query")
def chat_with_assistant(
    message: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Processes natural language questions from officers and returns answers"""
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    assistant = InvestigationAssistant(db)
    response_text = assistant.answer_query(message)
    
    return {
        "query": message,
        "reply": response_text
    }
