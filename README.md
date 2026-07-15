# KSP-Sentinel

### AI-Powered Crime Intelligence & Predictive Analytics Platform
KSP-Sentinel is a state-of-the-art predictive policing and crime analytics command center built for the **Karnataka State Police (KSP)**. The platform breaks down manual records and data silos using advanced machine learning, geospatial clustering, criminal network page-ranking, and dynamic demographic correlation engines.

---

## 🚀 Key Modules
1. **Executive Dashboard**: Command KPIs (Growth, Arrest rates, Hot stations).
2. **Interactive Command Map**: Dynamic Leaflet map with **District-level drill-down selection**, **Spatiotemporal Time of Day filters** (Morning, Afternoon, Evening, Night), and **Pulsing Red Halos** displaying active emerging crime spikes.
3. **Sociological & AI Predictive Dashboard**: 
   - Pearson correlation matrices matching socio-economic parameters (urbanization, literacy, unemployment, poverty rate) to crime rates.
   - Demographic threat index scatter charts.
   - Drill-down SHAP explainability feature weight breakdowns for local threats.
   - Statistical anomaly warning board alerting when counts exceed $1.5\sigma$ standard deviations from the historical baseline.
4. **AI Crime Forecasting**: Time series forecasting console predicting future counts per district.
5. **Criminological Network Analysis**: Bipartite force-directed node graphs featuring **Repeat Suspect dossiers**, cross-jurisdictional case histories, Modus Operandi (MO) descriptors, and **Community Gang Cell highlighter filters**.
6. **Semantic FIR Search**: FAISS vector-based similarity finder for matching cases.
7. **AI Copilot Chatbot**: Police investigation assistant powered by LLM memory.
8. **Briefing Report Builder**: Automated generation of PDF and Excel briefings.

---

## 🛠️ Architecture
- **Frontend**: Next.js 16, Tailwind CSS, TypeScript, Leaflet, Recharts.
- **Backend**: FastAPI, Python, SQLAlchemy, NumPy.
- **Database**: SQLite (local seeded development database with 250+ FIR cases, realistic locations, and district demographics).
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
2. **Seed the database & Sync monthly reviews**:
   ```bash
   source venv/bin/activate
   python scripts/load_data.py
   PYTHONPATH=. python scripts/run_full_import.py
   ```
3. **Run in development**:
   ```bash
   npm run dev
   ```
   This command starts the FastAPI backend (port `8000`) and the Next.js frontend (port `3000`) concurrently.

