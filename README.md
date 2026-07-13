# KSP-Sentinel

### AI-Powered Crime Intelligence & Predictive Analytics Platform
KSP-Sentinel is a state-of-the-art predictive policing and crime analytics command center built for the **Karnataka State Police (KSP)**. The platform analyzes historical FIR data, builds criminal association networks, performs semantic matches, and forecasts potential future crime hotspots.

---

## 🚀 Key Modules
1. **Executive Dashboard**: Command KPIs (Growth, Arrest rates, Hot stations).
2. **Interactive Crime Map**: Filterable Leaflet heatmap with historical timeline control.
3. **AI Crime Forecasting**: Time series analysis predicting future occurrences per district.
4. **Predictive Hotspot Heatmap**: AI-driven future hotzone predictions.
5. **Pattern Clustering**: KMeans/DBSCAN cluster matching for specific behaviors.
6. **Criminal Network Analysis**: Node graphs mapping Repeat Offenders and gangs.
7. **Semantic FIR Search**: FAISS vector-based similarity finder for matching cases.
8. **AI Copilot Chatbot**: Police investigation companion chatbot.
9. **District Security Index**: Dynamic risk ranking of districts.
10. **Report Builder**: Instant generation of PDF and Excel briefings.

---

## 🛠️ Architecture
- **Frontend**: Next.js 14, Tailwind CSS, TypeScript, Leaflet, Recharts.
- **Backend**: FastAPI, Python, SQLAlchemy.
- **Database**: PostgreSQL (with local SQLite fallback).
- **Background Engine**: Celery + Redis.
- **AI/ML Engine**: Scikit-Learn, Statsmodels, FAISS, Sentence Transformers.

---

## 📦 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+

### Setup and Running
1. **Install dependencies**:
   ```bash
   npm run install-all
   ```
2. **Seed the database**:
   ```bash
   python scripts/load_data.py
   ```
3. **Run in development**:
   ```bash
   npm run dev
   ```
   This command starts the backend (port `8000`) and the frontend (port `3000`) concurrently.
