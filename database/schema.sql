-- KSP Sentinel Relational Database Schema (PostgreSQL + PostGIS + pgvector)

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Districts
CREATE TABLE IF NOT EXISTS districts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    population INT NOT NULL DEFAULT 100000,
    risk_score INT DEFAULT 50,
    risk_factors TEXT,
    urbanization_rate DOUBLE PRECISION DEFAULT 30.0,
    literacy_rate DOUBLE PRECISION DEFAULT 75.0,
    unemployment_rate DOUBLE PRECISION DEFAULT 5.0,
    poverty_rate DOUBLE PRECISION DEFAULT 15.0,
    geom geometry(MultiPolygon, 4326)
);

-- 2. Taluks
CREATE TABLE IF NOT EXISTS taluks (
    id SERIAL PRIMARY KEY,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    geom geometry(MultiPolygon, 4326)
);

-- 3. Police Stations
CREATE TABLE IF NOT EXISTS police_stations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom geometry(Point, 4326),
    UNIQUE(name, district_id)
);

-- 4. Crime Categories
CREATE TABLE IF NOT EXISTS crime_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    major_head VARCHAR(200),
    minor_head VARCHAR(200)
);

-- 5. Crime Subcategories
CREATE TABLE IF NOT EXISTS crime_subcategories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category_id INT REFERENCES crime_categories(id) ON DELETE CASCADE,
    UNIQUE(name, category_id)
);

-- 6. FIR Cases
CREATE TABLE IF NOT EXISTS fir_cases (
    id SERIAL PRIMARY KEY,
    fir_number VARCHAR(50) NOT NULL UNIQUE,
    police_station_id INT REFERENCES police_stations(id) ON DELETE SET NULL,
    subcategory_id INT REFERENCES crime_subcategories(id) ON DELETE SET NULL,
    date_reported TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date_occurred TIMESTAMP WITH TIME ZONE,
    description TEXT,
    status VARCHAR(50) DEFAULT 'REGISTERED', -- REGISTERED, INVESTIGATING, CHARGE_SHEETED, CLOSED, TRIAL
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geom geometry(Point, 4326)
);

-- 7. Victims
CREATE TABLE IF NOT EXISTS victims (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    name VARCHAR(100),
    age INT,
    gender VARCHAR(20),
    category VARCHAR(50), -- SENIOR_CITIZEN, WOMAN, CHILD, GENERAL
    injured INT DEFAULT 0,
    dead INT DEFAULT 0
);

-- 8. Accused Details
CREATE TABLE IF NOT EXISTS accused (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    gender VARCHAR(20),
    age INT,
    repeat_offender BOOLEAN DEFAULT FALSE,
    history_sheet BOOLEAN DEFAULT FALSE,
    gang VARCHAR(200),
    prior_offenses_count INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'ACTIVE' -- ACTIVE, ABSCONDING, ARRESTED, CONVICTED, INACTIVE
);

-- Many-to-many link table for FIRs and Accused
CREATE TABLE IF NOT EXISTS fir_accused (
    fir_id INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    PRIMARY KEY (fir_id, accused_id)
);

-- 9. Arrest Details
CREATE TABLE IF NOT EXISTS arrests (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    arrest_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'ARRESTED',
    officer VARCHAR(100),
    court VARCHAR(100)
);

-- 10. Investigations
CREATE TABLE IF NOT EXISTS investigations (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    assigned_officer VARCHAR(100),
    status VARCHAR(50) DEFAULT 'ASSIGNED', -- ASSIGNED, ONGOING, SUSPENDED, COMPLETED
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. Charge Sheets
CREATE TABLE IF NOT EXISTS chargesheets (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    filed_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sections VARCHAR(200),
    status VARCHAR(50) DEFAULT 'FILED'
);

-- 12. Convictions
CREATE TABLE IF NOT EXISTS convictions (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    conviction_date TIMESTAMP WITH TIME ZONE,
    sentence_months INT,
    status VARCHAR(50) DEFAULT 'CONVICTED',
    court VARCHAR(100),
    sentence VARCHAR(200),
    years DOUBLE PRECISION,
    fine DOUBLE PRECISION
);

-- 13. Officers
CREATE TABLE IF NOT EXISTS officers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    badge_number VARCHAR(50) UNIQUE NOT NULL,
    rank VARCHAR(50),
    station_id INT REFERENCES police_stations(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'ACTIVE'
);

-- 14. Monthly Crime Reviews
CREATE TABLE IF NOT EXISTS crime_review_monthly (
    id SERIAL PRIMARY KEY,
    source_file VARCHAR(200),
    sl_no INT,
    month INT NOT NULL,
    year INT NOT NULL,
    heads_of_crime VARCHAR(200),
    major_head VARCHAR(300),
    minor_head VARCHAR(300),
    upto_end_of_month INT,
    corresponding_month_prev_year INT,
    previous_month INT,
    current_month INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 15. Yearly Crime Reviews
CREATE TABLE IF NOT EXISTS crime_review_yearly (
    id SERIAL PRIMARY KEY,
    year INT NOT NULL,
    head_of_crime VARCHAR(200) NOT NULL,
    count INT NOT NULL,
    increase_percentage DOUBLE PRECISION,
    UNIQUE(year, head_of_crime)
);

-- 16. Crime Statistics
CREATE TABLE IF NOT EXISTS crime_statistics (
    id SERIAL PRIMARY KEY,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE,
    year INT NOT NULL,
    month INT NOT NULL,
    category_id INT REFERENCES crime_categories(id) ON DELETE CASCADE,
    total_count INT NOT NULL,
    rate_per_lakh DOUBLE PRECISION,
    UNIQUE(district_id, year, month, category_id)
);

-- 17. Crime Embeddings (pgvector)
CREATE TABLE IF NOT EXISTS crime_embeddings (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES fir_cases(id) ON DELETE CASCADE UNIQUE,
    embedding vector(384)
);

-- 18. Crime Clusters
CREATE TABLE IF NOT EXISTS crime_clusters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    district_ids VARCHAR(200),
    count INT DEFAULT 0
);

-- 19. Crime Forecasts (formerly predictions)
CREATE TABLE IF NOT EXISTS crime_forecasts (
    id SERIAL PRIMARY KEY,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE,
    year INT NOT NULL,
    month INT NOT NULL,
    category_id INT REFERENCES crime_categories(id) ON DELETE CASCADE,
    predicted_count INT NOT NULL,
    confidence DOUBLE PRECISION,
    UNIQUE(district_id, year, month, category_id)
);

-- 20. Crime Risk Scores
CREATE TABLE IF NOT EXISTS crime_risk_scores (
    id SERIAL PRIMARY KEY,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE UNIQUE,
    score INT DEFAULT 50,
    safety_index DOUBLE PRECISION DEFAULT 50.0,
    population_density DOUBLE PRECISION DEFAULT 100.0
);

-- 21. Crime Alerts
CREATE TABLE IF NOT EXISTS crime_alerts (
    id SERIAL PRIMARY KEY,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(50) DEFAULT 'WARNING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 22. Crime Network (Accused connections)
CREATE TABLE IF NOT EXISTS crime_network (
    id SERIAL PRIMARY KEY,
    source_accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    target_accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    connection_strength DOUBLE PRECISION DEFAULT 1.0,
    common_firs_count INT DEFAULT 1,
    UNIQUE(source_accused_id, target_accused_id)
);

-- 23. Crime Similarity
CREATE TABLE IF NOT EXISTS crime_similarity (
    id SERIAL PRIMARY KEY,
    fir_id_1 INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    fir_id_2 INT REFERENCES fir_cases(id) ON DELETE CASCADE,
    similarity_score DOUBLE PRECISION NOT NULL,
    UNIQUE(fir_id_1, fir_id_2)
);

-- 24. Patrol Routes
CREATE TABLE IF NOT EXISTS patrol_routes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    geom geometry(LineString, 4326),
    assigned_officer_id INT REFERENCES officers(id) ON DELETE SET NULL
);
