-- KSP Sentinel Relational Database Schema

-- Districts
CREATE TABLE IF NOT EXISTS districts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    population INT NOT NULL DEFAULT 100000,
    risk_score INT DEFAULT 50,
    risk_factors TEXT
);

-- Police Stations
CREATE TABLE IF NOT EXISTS police_stations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    UNIQUE(name, district_id)
);

-- Crime Categories
CREATE TABLE IF NOT EXISTS crime_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Crime Subcategories
CREATE TABLE IF NOT EXISTS crime_subcategories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category_id INT REFERENCES crime_categories(id) ON DELETE CASCADE,
    UNIQUE(name, category_id)
);

-- FIR Details
CREATE TABLE IF NOT EXISTS firs (
    id SERIAL PRIMARY KEY,
    fir_number VARCHAR(50) NOT NULL UNIQUE,
    police_station_id INT REFERENCES police_stations(id),
    subcategory_id INT REFERENCES crime_subcategories(id),
    date_reported TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    date_occurred TIMESTAMP WITH TIME ZONE,
    description TEXT,
    status VARCHAR(50) DEFAULT 'REGISTERED', -- REGISTERED, INVESTIGATING, CHARGE_SHEETED, CLOSED, TRIAL
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

-- Victims
CREATE TABLE IF NOT EXISTS victims (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES firs(id) ON DELETE CASCADE,
    name VARCHAR(100),
    age INT,
    gender VARCHAR(20),
    category VARCHAR(50) -- SENIOR_CITIZEN, WOMAN, CHILD, GENERAL
);

-- Accused Details
CREATE TABLE IF NOT EXISTS accused (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age INT,
    gender VARCHAR(20),
    prior_offenses_count INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'ACTIVE' -- ACTIVE, ABSCONDING, ARRESTED, CONVICTED, INACTIVE
);

-- FIR - Accused mapping (Many-to-Many)
CREATE TABLE IF NOT EXISTS fir_accused (
    fir_id INT REFERENCES firs(id) ON DELETE CASCADE,
    accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    PRIMARY KEY (fir_id, accused_id)
);

-- Arrest Details
CREATE TABLE IF NOT EXISTS arrests (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES firs(id) ON DELETE CASCADE,
    accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    arrest_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'ARRESTED'
);

-- Convictions
CREATE TABLE IF NOT EXISTS convictions (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES firs(id) ON DELETE CASCADE,
    accused_id INT REFERENCES accused(id) ON DELETE CASCADE,
    conviction_date TIMESTAMP WITH TIME ZONE,
    sentence_months INT,
    status VARCHAR(50) DEFAULT 'CONVICTED'
);

-- Investigations
CREATE TABLE IF NOT EXISTS investigations (
    id SERIAL PRIMARY KEY,
    fir_id INT REFERENCES firs(id) ON DELETE CASCADE,
    assigned_officer VARCHAR(100),
    status VARCHAR(50) DEFAULT 'ASSIGNED', -- ASSIGNED, ONGOING, SUSPENDED, COMPLETED
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Crime Predictions (District-wise)
CREATE TABLE IF NOT EXISTS crime_predictions (
    id SERIAL PRIMARY KEY,
    district_id INT REFERENCES districts(id) ON DELETE CASCADE,
    year INT NOT NULL,
    month INT NOT NULL,
    category_id INT REFERENCES crime_categories(id) ON DELETE CASCADE,
    predicted_count INT NOT NULL,
    confidence DOUBLE PRECISION,
    UNIQUE(district_id, year, month, category_id)
);

-- Crime Hotspot Predictions
CREATE TABLE IF NOT EXISTS crime_hotspots (
    id SERIAL PRIMARY KEY,
    police_station_id INT REFERENCES police_stations(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    intensity DOUBLE PRECISION NOT NULL, -- 0.0 to 1.0
    prediction_date DATE NOT NULL
);
