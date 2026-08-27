import os
import re
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import extract, text
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.database.models import FIR, District, PoliceStation, CrimeCategory, CrimeSubcategory, Accused
from explainability.explanations import ExplainableRiskEngine
from integrations.llm_provider import get_llm

CRIME_SYNONYMS = {
    "murder": "MURDER", "kill": "MURDER", "homicide": "MURDER",
    "cyber": "CYBER CRIME", "phishing": "CYBER CRIME", "hacking": "CYBER CRIME", "online fraud": "CYBER CRIME",
    "kidnap": "KIDNAPPING", "abduct": "KIDNAPPING", "ransom": "KIDNAPPING",
    "burglary": "BURGLARY", "break-in": "BURGLARY", "break in": "BURGLARY", "housebreak": "BURGLARY",
    "assault": "ASSAULT", "hurt": "ASSAULT",
    "fraud": "FRAUD", "cheat": "FRAUD", "embezzle": "FRAUD", "forgery": "FRAUD",
    "theft": "THEFT", "steal": "THEFT", "robbery": "THEFT", "pickpocket": "THEFT", "chain snatching": "THEFT",
    "riot": "RIOTS", "communal": "RIOTS",
}

STATUS_SYNONYMS = [
    (("chargesheet", "charge sheet", "charge-sheeted"), "CHARGE_SHEETED"),
    (("closed", "solved"), "CLOSED"),
    (("investigat", "pending", "open case"), "INVESTIGATING"),
]


class InvestigationAssistant:
    def __init__(self, db: Session):
        self.db = db
        # Whichever LLM is configured (Groq / Gemini / Ollama / none). Resolved
        # once at process level; see integrations/llm_provider.py.
        self.llm = get_llm()

    def answer_query(self, query_text: str):
        """Answers investigation query using Gemini API or local SQL compiler fallback"""
        query_text_lower = query_text.lower()

        # 1. Try local NLP SQL compiler fallback first for structured data queries
        parsed_answer = self._try_local_query(query_text_lower)
        if parsed_answer:
            return parsed_answer

        # 2. Free-form question and an LLM is configured -> ask it.
        if self.llm.available():
            # Summary stats give the model real numbers to reason over instead of
            # inventing them -- the single most important guard against a confident
            # wrong answer on police data.
            summary_stats = self._get_db_summary_stats()

            prompt = f"""
            You are KSP Sentinel Copilot, an AI assistant for the Karnataka State Police.
            You have access to a database of crime records with these summary statistics:
            {summary_stats}

            Officer Query: "{query_text}"

            Provide a professional, clear, and actionable response. Use bullet points and markdown tables if helpful.
            Base every figure on the statistics above; if they do not cover the question, say so
            rather than estimating.
            """

            answer = self.llm.complete(prompt)
            if answer:
                return answer
            # complete() returns None on any provider failure and has already logged
            # why -- fall through to the local answer rather than surfacing an error.

        # 3. Fallback response if Gemini fails and local query doesn't match
        return self._get_generic_chatbot_response(query_text)

    def _get_db_summary_stats(self):
        try:
            total_firs = self.db.query(FIR).count()
            districts = self.db.query(District).all()
            dist_summary = ", ".join([f"{d.name} (Risk: {d.risk_score})" for d in districts])

            categories = self.db.query(CrimeCategory).all()
            cat_summary = ", ".join([c.name for c in categories])

            return f"Total FIRs: {total_firs}. Districts: {dist_summary}. Crime Categories: {cat_summary}."
        except Exception:
            return "Total FIRs: 250 across 7 districts."

    def _match_district(self, query: str):
        """Matches a District row against free text, tolerant of partial names like 'mysuru'."""
        districts = self.db.query(District).all()
        if not districts:
            return None

        # Pass 1: full district name appears verbatim in the query (longest names first
        # so "Bengaluru Rural" wins over a looser later match on "Bengaluru").
        for d in sorted(districts, key=lambda d: -len(d.name)):
            if d.name.lower() in query:
                return d

        # Pass 2: first word of the district name appears as a whole word (e.g. "mysuru").
        candidates = []
        for d in districts:
            first_word = d.name.lower().split()[0]
            if re.search(rf'\b{re.escape(first_word)}\b', query):
                candidates.append(d)
        if candidates:
            candidates.sort(key=lambda d: (-d.risk_score, len(d.name)))
            return candidates[0]

        return None

    def _match_crime(self, query: str):
        """Returns (kind, id, label) where kind is 'subcategory' or 'category'."""
        subs = self.db.query(CrimeSubcategory).all()
        for s in sorted(subs, key=lambda s: -len(s.name)):
            if s.name.lower() in query:
                return ("subcategory", s.id, s.name)

        cats = self.db.query(CrimeCategory).all()
        for c in sorted(cats, key=lambda c: -len(c.name)):
            if c.name.lower() in query or (c.major_head and c.major_head.lower() in query):
                return ("category", c.id, c.name)

        for kw, major_head in CRIME_SYNONYMS.items():
            if kw in query:
                cat = self.db.query(CrimeCategory).filter(CrimeCategory.major_head == major_head).first()
                if cat:
                    return ("category", cat.id, cat.name)

        return None

    def _match_status(self, query: str):
        for keywords, status in STATUS_SYNONYMS:
            if any(k in query for k in keywords):
                return status
        return None

    def _match_relative_days(self, query: str):
        m = re.search(r'last\s+(\d+)\s+day', query)
        return int(m.group(1)) if m else None

    def _try_local_query(self, query: str):
        """Attempts to parse crime queries and run structured SQLite queries"""
        year_match = re.search(r'\b(20\d{2})\b', query)
        year = int(year_match.group(1)) if year_match else None

        district = self._match_district(query)
        crime_match = self._match_crime(query)
        status = self._match_status(query)
        days = self._match_relative_days(query)

        # Risk explanation intent: "why is <district> high risk", "explain risk factors for X"
        if district and any(kw in query for kw in ["why", "explain", "risk factor", "reason"]):
            engine = ExplainableRiskEngine(self.db)
            result = engine.explain_district_risk(district.id)
            if "error" not in result:
                lines = [
                    f"### 🧭 Risk Explanation — {result['district_name']} ({result['risk_level']})",
                    f"Overall risk score: **{result['risk_score']}/100**\n",
                ]
                for e in result["explanations"]:
                    lines.append(f"* {e}")
                lines.append("\n**Recommended actions:**")
                for r in result["recommendations"]:
                    lines.append(f"* {r}")
                return "\n".join(lines)

        # Repeat offender / gang intent
        if any(kw in query for kw in ["repeat offender", "gang", "history sheet", "history-sheeter"]):
            offenders = (
                self.db.query(Accused)
                .filter(Accused.repeat_offender == True)  # noqa: E712
                .order_by(Accused.prior_offenses_count.desc())
                .limit(5)
                .all()
            )
            total = self.db.query(Accused).filter(Accused.repeat_offender == True).count()  # noqa: E712
            if offenders:
                response = f"### 🕵️ Repeat Offenders on Record\nFound **{total}** flagged repeat offenders in the database.\n\n"
                response += "| Name | Gang | Prior Offenses | Status |\n| --- | --- | --- | --- |\n"
                for a in offenders:
                    response += f"| {a.name} | {a.gang or '—'} | {a.prior_offenses_count} | {a.status} |\n"
                response += "\n*See the Network Analysis view for full linkage graphs and shared-incident edges.*"
                return response
            return "No repeat offenders are currently flagged in the active database."

        # "Highest crime station/district" intent
        if "highest" in query or "most" in query:
            if "station" in query:
                res = self.db.execute(text(
                    "SELECT ps.name, COUNT(f.id) as cnt FROM police_stations ps "
                    "JOIN fir_cases f ON f.police_station_id = ps.id "
                    "GROUP BY ps.name ORDER BY cnt DESC LIMIT 5"
                )).fetchall()
                answer = "### 🚨 Stations with Highest Crime Volume\nHere are the top police stations by recorded cases:\n\n"
                answer += "| Police Station | Case Count |\n| --- | --- |\n"
                for row in res:
                    answer += f"| {row[0]} | {row[1]} cases |\n"
                answer += "\n*Recommendation: Deploy additional night patrols and surveillance teams to these station zones.*"
                return answer

            if "district" in query or "crime" in query:
                res = self.db.execute(text(
                    "SELECT d.name, COUNT(f.id) as cnt FROM districts d "
                    "JOIN police_stations ps ON ps.district_id = d.id "
                    "JOIN fir_cases f ON f.police_station_id = ps.id "
                    "GROUP BY d.name ORDER BY cnt DESC LIMIT 5"
                )).fetchall()
                answer = "### 🚨 Districts with Highest Crime Volume\nHere are the top districts by recorded cases:\n\n"
                answer += "| District | Case Count |\n| --- | --- |\n"
                for row in res:
                    answer += f"| {row[0]} | {row[1]} cases |\n"
                answer += "\n*Recommendation: Prioritize these districts for resource reallocation and patrol density review.*"
                return answer

        # Filter query for specific filters
        if year or district or crime_match or status or days:
            db_query = self.db.query(FIR)
            filter_text = []

            if district:
                db_query = db_query.join(PoliceStation, FIR.police_station_id == PoliceStation.id).filter(
                    PoliceStation.district_id == district.id
                )
                filter_text.append(f"District: **{district.name}**")
            if year:
                db_query = db_query.filter(extract('year', FIR.date_reported) == year)
                filter_text.append(f"Year: **{year}**")
            if days:
                cutoff = datetime.utcnow() - timedelta(days=days)
                db_query = db_query.filter(FIR.date_reported >= cutoff)
                filter_text.append(f"Last **{days}** days")
            if status:
                db_query = db_query.filter(FIR.status == status)
                filter_text.append(f"Status: **{status.replace('_', ' ').title()}**")
            if crime_match:
                kind, cid, label = crime_match
                if kind == "subcategory":
                    db_query = db_query.filter(FIR.subcategory_id == cid)
                else:
                    db_query = db_query.join(
                        CrimeSubcategory, FIR.subcategory_id == CrimeSubcategory.id
                    ).filter(CrimeSubcategory.category_id == cid)
                filter_text.append(f"Crime: **{label}**")

            results = db_query.order_by(FIR.date_reported.desc()).limit(5).all()
            total_matches = db_query.count()

            filter_str = ", ".join(filter_text)
            response = f"### 🔍 Database Query Results\nI found **{total_matches}** cases matching: {filter_str}.\n\n"

            if results:
                response += "Here are the most recent matches:\n\n"
                response += "| FIR Number | Station | Status | Description |\n| --- | --- | --- | --- |\n"
                for f in results:
                    desc = f.description or ""
                    desc_truncated = desc[:70] + "..." if len(desc) > 70 else desc
                    station_name = f.station.name if f.station else "Unknown"
                    response += f"| `{f.fir_number}` | {station_name} | **{f.status}** | {desc_truncated} |\n"
                response += f"\n*Viewing {len(results)} of {total_matches} cases.*"
            else:
                response += "No records match these criteria in our active database."

            return response

        return None

    def _get_generic_chatbot_response(self, query_text):
        if "hello" in query_text or "hi" in query_text:
            return self._get_greeting()

        return (
            f"I received your inquiry: '{query_text}'.\n"
            "To fetch relevant files, try specific filters (Year, District, Crime Type, Status like 'closed' or "
            "'investigating', or 'last 30 days'). You can also ask *'why is [district] high risk'* or "
            "*'show repeat offenders'*. If a Gemini API key is configured, I can generate contextual answers "
            "for open-ended questions too."
        )

    def _get_greeting(self):
        return (
            "Greetings Officer! I am **KSP-Sentinel AI Assistant**. You can ask me to search cases, "
            "query crime rates, explain risk scores, or identify repeat offenders.\n\n"
            "Try asking me:\n"
            "* *'Show murder cases in Bengaluru during 2024'*\n"
            "* *'Which police station has the highest crime?'*\n"
            "* *'Why is Kalaburagi high risk?'*\n"
            "* *'Show repeat offenders'*\n"
            "* *'Cases closed in the last 30 days'*"
        )
