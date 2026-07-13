-- KSP Sentinel Analytic Views

-- View for District Crime Statistics and Rankings
CREATE OR REPLACE VIEW v_district_crime_rates AS
SELECT 
    d.id AS district_id,
    d.name AS district_name,
    d.population,
    d.risk_score,
    COUNT(f.id) AS total_firs,
    ROUND((COUNT(f.id)::numeric / d.population) * 100000, 2) AS crime_rate_per_lakh,
    SUM(CASE WHEN f.status = 'CLOSED' THEN 1 ELSE 0 END) AS solved_cases,
    ROUND((SUM(CASE WHEN f.status = 'CLOSED' THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(f.id), 0)) * 100, 2) AS solve_rate_percentage
FROM districts d
LEFT JOIN police_stations ps ON ps.district_id = d.id
LEFT JOIN firs f ON f.police_station_id = ps.id
GROUP BY d.id, d.name, d.population, d.risk_score;

-- View for Police Station KPI Metrics
CREATE OR REPLACE VIEW v_police_station_kpis AS
SELECT 
    ps.id AS police_station_id,
    ps.name AS police_station_name,
    d.name AS district_name,
    COUNT(f.id) AS total_firs,
    SUM(CASE WHEN f.status = 'CHARGE_SHEETED' OR f.status = 'CLOSED' THEN 1 ELSE 0 END) AS chargesheeted_or_solved,
    ROUND((SUM(CASE WHEN f.status = 'CHARGE_SHEETED' OR f.status = 'CLOSED' THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(f.id), 0)) * 100, 2) AS chargesheet_rate_percentage,
    COUNT(DISTINCT a.accused_id) AS total_arrests
FROM police_stations ps
JOIN districts d ON ps.district_id = d.id
LEFT JOIN firs f ON f.police_station_id = ps.id
LEFT JOIN arrests a ON a.fir_id = f.id
GROUP BY ps.id, ps.name, d.name;

-- View for Accused Recidivism/Repeat Offender metrics
CREATE OR REPLACE VIEW v_accused_recidivism AS
SELECT 
    a.id AS accused_id,
    a.name AS accused_name,
    a.age,
    a.gender,
    a.prior_offenses_count,
    COUNT(fa.fir_id) AS recorded_fir_links,
    (a.prior_offenses_count + COUNT(fa.fir_id)) AS total_estimated_crimes
FROM accused a
LEFT JOIN fir_accused fa ON fa.accused_id = a.id
GROUP BY a.id, a.name, a.age, a.gender, a.prior_offenses_count;
