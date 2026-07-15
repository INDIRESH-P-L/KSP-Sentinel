"""
Catalyst Advanced I/O Function (Python) demonstrating the Functions-based deployment
pattern from the roadmap's Catalyst service mapping table ("Backend REST APIs -> Functions").

Structure follows the verified Catalyst Python Advanced I/O pattern (Flask-based
request/response, zcatalyst_sdk.initialize()) from:
https://docs.catalyst.zoho.com/en/serverless/help/functions/advanced-io/

IMPORTANT — this is a worked EXAMPLE, not the primary deployment target. This repo's
FastAPI backend has ~10 routers and a stateful SQLAlchemy layer; per the roadmap's own
mapping table, that whole app belongs on Catalyst AppSail as a lift-and-shift (see
catalyst/MIGRATION.md), not rewritten endpoint-by-endpoint as individual Functions.
This function exists to demonstrate the pattern for a single, small, standalone
endpoint -- exactly the case the roadmap calls out Functions for.

Assumption to verify before deploying: DATABASE_URL points at a Postgres-compatible
connection (this codebase's backend/app/database/models.py already branches on
USE_POSTGRES). If Catalyst Data Store in your account only exposes its own REST/SDK
query API rather than a Postgres wire-protocol endpoint, the query layer inside
InvestigationAssistant needs porting to zcatalyst_sdk's datastore() calls instead --
check the Data Store docs for your plan before assuming this connects as-is.
"""
import os
import sys
import json
import logging

from flask import Request, jsonify, make_response

# Reuse the existing chatbot query engine rather than reimplementing it —
# see ai-engine/chatbot/gemini_client.py for the actual NL-to-query logic.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai-engine"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

logger = logging.getLogger()


def handler(request: Request):
    import zcatalyst_sdk
    zcatalyst_sdk.initialize()

    if request.path == "/health":
        return make_response(jsonify({"status": "ok", "service": "ksp-copilot"}), 200)

    if request.path == "/chatbot/query":
        body = request.get_json(silent=True) or {}
        message = body.get("message", "")
        if not message.strip():
            return make_response(jsonify({"error": "message cannot be empty"}), 400)

        try:
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine
            from chatbot.gemini_client import InvestigationAssistant

            database_url = os.environ["DATABASE_URL"]
            engine = create_engine(database_url)
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            try:
                assistant = InvestigationAssistant(db)
                reply = assistant.answer_query(message)
            finally:
                db.close()

            return make_response(jsonify({"query": message, "reply": reply}), 200)
        except Exception as e:
            logger.error(f"chatbot/query failed: {e}")
            return make_response(jsonify({"error": str(e)}), 500)

    return make_response(jsonify({"error": f"Unknown path: {request.path}"}), 404)
