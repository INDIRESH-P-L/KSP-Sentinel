-- Database Indexes for KSP Sentinel

-- FIR performance indexes
CREATE INDEX IF NOT EXISTS idx_firs_police_station ON firs(police_station_id);
CREATE INDEX IF NOT EXISTS idx_firs_subcategory ON firs(subcategory_id);
CREATE INDEX IF NOT EXISTS idx_firs_date_reported ON firs(date_reported);
CREATE INDEX IF NOT EXISTS idx_firs_status ON firs(status);

-- Demographics indexes
CREATE INDEX IF NOT EXISTS idx_victims_fir ON victims(fir_id);
CREATE INDEX IF NOT EXISTS idx_victims_age_gender ON victims(age, gender);
CREATE INDEX IF NOT EXISTS idx_accused_name ON accused(name);

-- Join table indexes
CREATE INDEX IF NOT EXISTS idx_fir_accused_accused ON fir_accused(accused_id);

-- Predictions indexes
CREATE INDEX IF NOT EXISTS idx_predictions_lookup ON crime_predictions(district_id, year, month);
