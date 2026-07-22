/**
 * Mock data for screens whose real endpoint isn't wired yet.
 * Each export matches the corresponding shape in `lib/types.ts` (spec §7),
 * so a view can swap `mockX` for `await authFetch(...)` in one line.
 *
 * Data uses real Karnataka districts/stations — NOT the garbled placeholder
 * text from the reference mockups.
 */
import type {
  DashboardKpis, MonthlyTrendPoint, TopDistrict, HotStation, SocioEconomic,
  Anomaly, SearchResult, District, RiskExplanation, Hotspot, DistrictRanking,
  Forecast, NetworkData, ConsoleUser,
} from "./types";

export const mockKpis: DashboardKpis = {
  total_firs: 2049,
  solve_rate: 78.4,
  monthly_growth: -2.3,
  active_investigations: 184,
};

export const mockMonthlyTrends: MonthlyTrendPoint[] = [
  { month: "Apr 2023", count: 92 },
  { month: "May 2023", count: 148 },
  { month: "Jun 2023", count: 171 },
  { month: "Jul 2023", count: 160 },
  { month: "Aug 2023", count: 224 },
  { month: "Sep 2023", count: 198 },
  { month: "Oct 2023", count: 176 },
  { month: "Nov 2023", count: 205 },
  { month: "Dec 2023", count: 189 },
  { month: "Jan 2024", count: 168 },
  { month: "Feb 2024", count: 132 },
  { month: "Mar 2024", count: 108 },
];

export const mockTopDistricts: TopDistrict[] = [
  { name: "Bengaluru City", rate: 240.2 },
  { name: "Belagavi Dist", rate: 133.5 },
  { name: "Tumakuru", rate: 96.1 },
  { name: "Shivamogga", rate: 71.4 },
  { name: "Mandya", rate: 58.9 },
];

export const mockHotStations: HotStation[] = [
  { station: "Kalasipalya PS", count: 142 },
  { station: "Koramangala PS", count: 118 },
  { station: "Indiranagar PS", count: 96 },
  { station: "Madiwala PS", count: 87 },
  { station: "Yeshwanthpur PS", count: 74 },
];

export const mockSocioEconomic: SocioEconomic = {
  // Nested metric -> category -> coefficient, matching the real
  // /api/dashboard/socio-economic response shape.
  correlations: {
    poverty_rate: { Theft: 0.24, "Crime (All)": -0.31 },
    literacy_rate: { "Cyber Crime": -0.42 },
    unemployment_rate: { Theft: 0.18 },
    urbanization_rate: { "Cyber Crime": 0.51, Theft: 0.63 },
  },
  scatter_data: Array.from({ length: 40 }, (_, i) => {
    const urb = 4 + Math.random() * 62;
    return {
      urbanization: +urb.toFixed(1),
      threat_score: +Math.min(95, urb * 1.15 + (Math.random() * 24 - 12)).toFixed(1),
      district: `District ${i + 1}`,
    };
  }),
};

export const mockAnomalies: Anomaly[] = [
  { district: "Chikkamagaluru", z_score: 2.9, message: "Spike detected in CrPC cases", severity: "CRITICAL" },
  { district: "Ramanagara", z_score: 2.4, message: "Spike detected in CrPC cases", severity: "WARNING" },
  { district: "Bengaluru City", z_score: 2.1, message: "Spike detected in Cyber Crime", severity: "WARNING" },
  { district: "Bagalkot", z_score: 1.7, message: "Unusual property-crime activity", severity: "INFO" },
];

export const mockSearchResults: SearchResult[] = [
  { fir_number: "0092/2024", description: "Suspect stole a black Pulsar motorcycle near the KBS bus stand during night hours.", score: 0.91 },
  { fir_number: "0148/2024", description: "Two-wheeler theft reported outside Majestic bus terminal, dark-coloured bike, no plate.", score: 0.86 },
  { fir_number: "0203/2023", description: "Silver Alto car reported stolen near Outer Ring Road service lane.", score: 0.74 },
  { fir_number: "0311/2023", description: "Chain-snatching from pillion rider on a speeding motorcycle at a bus stop.", score: 0.69 },
];

export const mockDistricts: District[] = [
  { id: 1, name: "Bagalkot", risk_score: 62 },
  { id: 2, name: "Bengaluru City", risk_score: 96 },
  { id: 3, name: "Belagavi", risk_score: 74 },
  { id: 4, name: "Mysuru City", risk_score: 68 },
  { id: 5, name: "Tumakuru", risk_score: 59 },
  { id: 6, name: "Shivamogga", risk_score: 55 },
  { id: 7, name: "Mangaluru", risk_score: 71 },
];

export const mockRiskExplanation: RiskExplanation = {
  literacy_impact: -5,
  poverty_impact: 12,
  urbanization_impact: 8,
};

export const mockRankings: DistrictRanking[] = [
  { rank: 1, name: "Bengaluru City", crime_rate: 45.21, conviction_rate: 78.5, threat_score: 96 },
  { rank: 2, name: "Mangaluru", crime_rate: 33.57, conviction_rate: 83.0, threat_score: 88 },
  { rank: 3, name: "Belagavi", crime_rate: 33.38, conviction_rate: 73.5, threat_score: 84 },
  { rank: 4, name: "Mysuru City", crime_rate: 26.10, conviction_rate: 70.0, threat_score: 80 },
  { rank: 5, name: "Hubballi-Dharwad", crime_rate: 20.78, conviction_rate: 80.0, threat_score: 79 },
  { rank: 6, name: "Kalaburagi", crime_rate: 43.36, conviction_rate: 80.0, threat_score: 76 },
  { rank: 7, name: "Tumakuru", crime_rate: 25.29, conviction_rate: 70.5, threat_score: 64 },
  { rank: 8, name: "Davanagere", crime_rate: 22.50, conviction_rate: 73.5, threat_score: 59 },
  { rank: 9, name: "Shivamogga", crime_rate: 32.59, conviction_rate: 71.8, threat_score: 48 },
  { rank: 10, name: "Ballari", crime_rate: 57.62, conviction_rate: 68.7, threat_score: 44 },
];

export function mockForecast(model: string): Forecast {
  // Slight per-model variation so switching models visibly changes output.
  const seed = { arima: 1, prophet: 1.08, lstm: 0.92, xgboost: 1.15 }[model] ?? 1;
  const base = [148, 162, 139];
  const forecast = base.map((v) => Math.round(v * seed));
  return {
    forecast,
    lower_bounds: forecast.map((v) => Math.round(v * 0.86)),
    upper_bounds: forecast.map((v) => Math.round(v * 1.16)),
  };
}

// Bengaluru-centred hotspots (spec §7.4 hotspots shape).
export const mockHotspots: Hotspot[] = Array.from({ length: 60 }, () => ({
  lat: 12.9716 + (Math.random() - 0.5) * 0.18,
  lng: 77.5946 + (Math.random() - 0.5) * 0.18,
  intensity: +(Math.random() * 9 + 1).toFixed(1),
}));

export function mockNetwork(): NetworkData {
  const gangs = ["Cell #0", "Cell #1", "Cell #2", "Cell #3"];
  const accused = Array.from({ length: 18 }, (_, i) => ({
    id: `A${i + 1}`,
    label: `Suspect ${i + 1}`,
    type: "accused" as const,
    pagerank: +(0.01 + Math.random() * 0.06).toFixed(3),
    gang: gangs[i % gangs.length],
  }));
  const firs = Array.from({ length: 12 }, (_, i) => ({
    id: `F${i + 1}`,
    label: `FIR ${100 + i}`,
    type: "fir" as const,
    pagerank: +(0.01 + Math.random() * 0.03).toFixed(3),
  }));
  const nodes = [...accused, ...firs];
  const links: { source: string; target: string }[] = [];
  accused.forEach((a) => {
    const n = 1 + Math.floor(Math.random() * 3);
    for (let k = 0; k < n; k++) {
      links.push({ source: a.id, target: firs[Math.floor(Math.random() * firs.length)].id });
    }
  });
  return { nodes, links };
}

export const mockUsers: ConsoleUser[] = [
  { id: 1, username: "keshav", role: "Superintendent", is_active: true, created_by: "system" },
  { id: 2, username: "admin", role: "Admin", is_active: true, created_by: "system" },
  { id: 3, username: "priya.sharma", role: "Investigator", is_active: true, created_by: "keshav" },
  { id: 4, username: "r.kumar", role: "Analyst", is_active: false, created_by: "keshav" },
];

export const mockChatReply =
  "Based on current records for Bengaluru during 2024: 42 total reported cases. " +
  "Key districts — Bengaluru City (25), Bengaluru Dist (10), Other (7). Primary modus " +
  "operandi: Blunt Force (15), Firearm (10), Sharp Object (8), Unknown (9). High-activity " +
  "zones: Chickpet, Madiwala, HSR Layout. A list of linked suspects and gang affiliations " +
  "is available upon request.";
