# KSP Sentinel Database Design

This document describes the database schema, table definitions, and view aggregations used in the **KSP-Sentinel** platform.

## Relational Entity Schema

The database uses a clean, normalised third normal form (3NF) relational design:

### 1. Core Reference Tables
- **`districts`**: Contains the demographic population details and active risk index score for each Karnataka district.
- **`police_stations`**: Police stations linked to districts along with baseline latitude/longitude coordinates.
- **`crime_categories`**: Core category mappings (e.g. Theft & Burglary, Crimes Against Persons, Cyber Crime).
- **`crime_subcategories`**: Granular classifications of crimes (e.g. House Break-in, Vehicle Theft, Murder).

### 2. Crime Records & Details
- **`firs`**: The central incident registry storing the unique FIR number, reporting times, coordinate points, and investigation statuses.
- **`victims`**: Demographic breakdowns (age, gender, classification) linked to specific cases.
- **`accused`**: Offender profiles tracking statuses and prior offense counts.
- **`fir_accused`**: Many-to-many bridge linking accused members to multiple FIRs.
- **`arrests`**: Incident arrests tracking booking times.
- **`convictions`**: Final case trial decisions.
- **`investigations`**: Assigned investigation officers and state timelines.

### 3. Predictive Modules
- **`crime_predictions`**: Pre-calculated and model-generated forecasting metrics per district and crime category.
- **`crime_hotspots`**: Future geographical density focal points calculated for active stations.

---

## Analytical SQL Views
The system implements three views in `database/views.sql` to speed up backend query processing:
1. **`v_district_crime_rates`**: Standardises raw case counts against population size, computing crime rates per lakh citizens.
2. **`v_police_station_kpis`**: Measures station performance indicators such as solve rates, arrest counts, and chargesheet rates.
3. **`v_accused_recidivism`**: Identifies repeat offenders and co-offender gang affiliations.
