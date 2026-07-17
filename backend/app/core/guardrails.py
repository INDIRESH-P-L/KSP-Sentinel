"""AI assistant guardrails: blocks sensitive-data fishing and classic prompt-injection
attempts before they reach the chatbot engine, and redacts PII patterns that slip into
a response (the local SQL-compiler path returns real names from the DB; the Gemini
path incorporates the officer's free-text query into a response the model writes).

This is regex-based, not an LLM-based classifier -- sufficient for a demo/first pass,
and importantly a set of rules that are auditable and don't add a second network call
per chat message. Real deployment would want to combine this with the role-based
masking in masking.py (not yet threaded through the chatbot's local SQL-compiler
response strings -- see the note in InvestigationAssistant.answer_query call site).
"""
import re

# Classic prompt-injection phrasing: trying to override the assistant's instructions
# or extract system-level configuration rather than ask a legitimate investigation
# question.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above|earlier) instructions",
    r"disregard (your|the) (rules|guidelines|instructions)",
    r"system prompt",
    r"you are now (an?|acting as)",
    r"act as (an?|a) (unfiltered|unrestricted|jailbroken|dan)\b",
    r"reveal your (instructions|prompt|configuration)",
    r"pretend (you|to) (are|be)",
]

# Direct requests for the kind of PII the masking layer (masking.py) exists to
# protect -- phone numbers, Aadhaar/national ID, home address, witness identity --
# framed as a request rather than incidental mention.
PII_REQUEST_PATTERNS = [
    r"\b(phone|mobile|contact)\s*(number|no\.?|details)\b",
    r"\baadhaar\b",
    r"\b(home|residential)\s*address\b",
    r"\bwitness(es)?\b.*\b(name|identity|contact|detail)",
    r"\b(give|show|tell|list)\s+me\s+.*\b(personal|private)\s+(detail|info)",
]

# Literal ID-shaped numbers typed into a query -- someone trying to search/confirm a
# specific individual's phone or Aadhaar number rather than ask an investigative
# question about a case.
RAW_ID_PATTERNS = [
    r"\b\d{12}\b",         # Aadhaar-shaped
    r"\b\d{10}\b",         # Indian mobile-shaped
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_PII_REQUEST_RE = [re.compile(p, re.IGNORECASE) for p in PII_REQUEST_PATTERNS]
_RAW_ID_RE = [re.compile(p) for p in RAW_ID_PATTERNS]


def check_query(message: str) -> str | None:
    """Returns a rejection reason if the query should be blocked, else None."""
    for pattern in _INJECTION_RE:
        if pattern.search(message):
            return "This request appears to attempt to override the assistant's operating instructions."
    for pattern in _PII_REQUEST_RE:
        if pattern.search(message):
            return "Direct requests for personal contact/identity details are blocked. Use the case file view with your clearance level instead."
    for pattern in _RAW_ID_RE:
        if pattern.search(message):
            return "Queries containing what looks like a raw phone/ID number are blocked. Search by case or name instead."
    return None


# Output-side redaction: catches PII patterns that end up IN a generated response,
# independent of whether the query that produced it looked suspicious.
_PHONE_RE = re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b")
_AADHAAR_RE = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def redact_response(text: str) -> str:
    if not text:
        return text
    text = _EMAIL_RE.sub("[REDACTED]", text)
    text = _AADHAAR_RE.sub("[REDACTED]", text)
    text = _PHONE_RE.sub("[REDACTED]", text)
    return text
