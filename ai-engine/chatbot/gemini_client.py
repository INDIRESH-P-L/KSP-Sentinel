import os
import re
import requests
from sqlalchemy.orm import Session
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.app.database.models import FIR, District, PoliceStation, CrimeCategory

class InvestigationAssistant:
    def __init__(self, db: Session):
        self.db = db
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    def answer_query(self, query_text: str):
        """Answers investigation query using Gemini API or local SQL compiler fallback"""
        query_text_lower = query_text.lower()
        
        # 1. Try local NLP SQL compiler fallback first for structured data queries
        parsed_answer = self._try_local_query(query_text_lower)
        if parsed_answer:
            return parsed_answer
            
        # 2. If it's a general question and Gemini API is configured, use it
        if self.api_key:
            try:
                # Let's pull some statistics to inject into the Gemini context so it can answer intelligently
                summary_stats = self._get_db_summary_stats()
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
                prompt = f"""
                You are KSP Sentinel Copilot, an AI assistant for the Karnataka State Police.
                You have access to a database of crime records with these summary statistics:
                {summary_stats}
                
                Officer Query: "{query_text}"
                
                Provide a professional, clear, and actionable response. Use bullet points and markdown tables if helpful.
                """
                
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                print(f"Gemini API request failed: {e}")
                
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

    def _try_local_query(self, query: str):
        """Attempts to parse crime queries and run structured SQLite queries"""
        # Look for years
        year_match = re.search(r'\b(2023|2024|2025|2026)\b', query)
        year = int(year_match.group(1)) if year_match else None
        
        # Look for districts
        districts = ["bengaluru city", "bengaluru rural", "mysuru", "hubballi-dharwad", "mangaluru", "belagavi", "kalaburagi"]
        district = None
        for d in districts:
            if d in query:
                district = d
                break
                
        # Look for crime categories
        crimes = {
            "murder": "Murder",
            "assault": "Assault",
            "theft": "Vehicle Theft",
            "break-in": "House Break-in",
            "cyber": "Phishing Fraud",
            "narcotics": "NDPS Possession",
            "violence": "Domestic Violence",
            "robbery": "Chain Snatching"
        }
        crime_sub = None
        for k, v in crimes.items():
            if k in query:
                crime_sub = v
                break

        # If a query matches "highest" and "station" or "robbery rate"
        if "highest" in query or "most" in query:
            if "station" in query:
                # Query stations with most crimes
                from sqlalchemy import func
                top_station = self.db.query(
                    PoliceStation.name, func.count(FIR.id).label('fir_count')
                ).join(FIR, FIR.police_station_id == PoliceStation.id).group_by(PoliceStation.name).order_type = 'fir_count'
                # Sort by count desc
                res = self.db.execute(
                    text("SELECT ps.name, COUNT(f.id) as cnt FROM police_stations ps JOIN fir_cases f ON f.police_station_id = ps.id GROUP BY ps.name ORDER BY cnt DESC LIMIT 3")
                ).fetchall()
                
                answer = "### 🚨 Stations with Highest Crime Volume\nHere are the top police stations by recorded cases:\n\n"
                answer += "| Police Station | Case Count |\n| --- | --- |\n"
                for row in res:
                    answer += f"| {row[0]} | {row[1]} cases |\n"
                answer += "\n*Recommendation: Deploy additional night patrols and surveillance teams to these station zones.*"
                return answer

        # Filter query for specific filters
        if year or district or crime_sub:
            db_query = self.db.query(FIR)
            
            filter_text = []
            if district:
                db_query = db_query.join(PoliceStation).join(District).filter(func_lower(District.name) == district)
                filter_text.append(f"District: **{district.title()}**")
            if year:
                # filter by date_reported year
                from sqlalchemy import extract
                db_query = db_query.filter(extract('year', FIR.date_reported) == year)
                filter_text.append(f"Year: **{year}**")
            if crime_sub:
                from backend.app.database.models import CrimeSubcategory
                db_query = db_query.join(CrimeSubcategory).filter(CrimeSubcategory.name == crime_sub)
                filter_text.append(f"Crime Subcategory: **{crime_sub}**")
                
            results = db_query.limit(5).all()
            total_matches = db_query.count()
            
            filter_str = ", ".join(filter_text)
            response = f"### 🔍 Database Query Results\nI found **{total_matches}** cases matching: {filter_str}.\n\n"
            
            if results:
                response += "Here are the top matches:\n\n"
                response += "| FIR Number | Station | Status | Description |\n| --- | --- | --- | --- |\n"
                for f in results:
                    desc_truncated = f.description[:70] + "..." if len(f.description) > 70 else f.description
                    response += f"| `{f.fir_number}` | {f.station.name} | **{f.status}** | {desc_truncated} |\n"
                response += f"\n*Viewing 5 of {total_matches} cases.*"
            else:
                response += "No records match these criteria in our active database."
                
            return response
            
        return None

    def _get_generic_chatbot_response(self, query_text):
        if "hello" in query_text or "hi" in query_text:
            return "Greetings Officer! I am **KSP-Sentinel AI Assistant**. You can ask me to search cases, query crime rates, or identify repeat offender graphs. For example, try asking: *'Show murder cases in Bengaluru during 2024'* or *'Which police station has the highest crime?'*"
        
        return f"I received your inquiry: '{query_text}'.\nTo fetch relevant files, please try searching with specific filters (e.g. Year, District, Crime Type like Theft or Narcotics). If you have a Gemini API key loaded, I can generate contextual solutions."

def func_lower(col):
    from sqlalchemy import func
    return func.lower(col)
