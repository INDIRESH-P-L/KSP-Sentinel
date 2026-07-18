/**
 * API response shapes — mirror the "REST API Endpoint Registry" (spec §7) exactly.
 * Views type their state against these so swapping a mock for a real `authFetch`
 * call is a one-line change, not a rewrite.
 */

// §7.2 GET /api/dashboard/kpis
export interface DashboardKpis {
  total_firs: number;
  solve_rate: number;
  monthly_growth: number;
  active_investigations: number;
}

// §7.2 GET /api/dashboard/charts/monthly-trends
export interface MonthlyTrendPoint {
  month: string;
  count: number;
}

// §7.2 GET /api/dashboard/top-districts
export interface TopDistrict {
  name: string;
  rate: number;
}

// §7.2 GET /api/dashboard/hot-stations
export interface HotStation {
  station: string;
  count: number;
}

// §7.2 GET /api/dashboard/socio-economic
export interface SocioEconomic {
  correlations: Record<string, number>;
  scatter_data: { urbanization: number; threat_score: number; district?: string }[];
}

// §7.2 GET /api/dashboard/anomalies
export interface Anomaly {
  district: string;
  z_score: number;
  message: string;
  severity?: "INFO" | "WARNING" | "CRITICAL";
}

// §7.3 GET /api/crimes/search
export interface SearchResult {
  fir_number: string;
  description: string;
  score: number;
}

// §7.3 GET /api/crimes/emerging-trends
export interface EmergingTrend {
  latitude: number;
  longitude: number;
  spike_percentage: number;
}

// §7.4 GET /api/districts/
export interface District {
  id: number;
  name: string;
  risk_score: number;
}

// §7.4 GET /api/districts/{id}/explain-risk
export interface RiskExplanation {
  literacy_impact: number;
  poverty_impact: number;
  urbanization_impact: number;
}

// §7.4 GET /api/districts/stations/{id}/hotspots
export interface Hotspot {
  lat: number;
  lng: number;
  intensity: number;
}

// §7.4 rankings (rendered ranking details)
export interface DistrictRanking {
  rank: number;
  name: string;
  crime_rate: number;
  conviction_rate: number;
  threat_score: number;
}

// §7.5 GET /api/forecast/
export interface Forecast {
  forecast: number[];
  lower_bounds: number[];
  upper_bounds: number[];
}

// §7.6 GET /api/network/
export interface NetworkNode {
  id: string;
  label: string;
  type: "accused" | "victim" | "fir" | "station";
  pagerank: number;
  gang?: string;
}
export interface NetworkLink {
  source: string;
  target: string;
}
export interface NetworkData {
  nodes: NetworkNode[];
  links: NetworkLink[];
}

// §7.7 POST /api/chatbot/query
export interface ChatReply {
  reply: string;
}

// §7.10 GET /api/users/
export interface ConsoleUser {
  id: number;
  username: string;
  role: "Admin" | "Superintendent" | "Investigator" | "Analyst";
  is_active: boolean;
  created_at?: string;
  created_by?: string;
}
