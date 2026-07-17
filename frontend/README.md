# KSP-Sentinel: Frontend Developer Guide

This directory contains the Next.js frontend application for **KSP-Sentinel**. The user interface is structured as a single-page command console designed for the Karnataka State Police.

For complete, high-level project documentation covering system architecture, database design, API lists, and AI core logic, refer to the master [README.md](file:///c:/Users/jeltrin/OneDrive/Desktop/policce/KSP-Sentinel/README.md) at the repository root.

---

## 🚀 Getting Started

### 1. Installation
Install frontend-specific packages using npm:
```bash
npm install
```

### 2. Development Execution
Start the Next.js development server:
```bash
npm run dev
```

By default, the application runs on [http://localhost:3000](http://localhost:3000). If port 3000 is occupied, it automatically shifts to port 3001.

### 3. Production Build
To create a production-optimized build:
```bash
npm run build
```

---

## 📁 Directory Structure

```
frontend/
├── app/
│   ├── globals.css      # Core styles, variables, theme configuration
│   ├── layout.tsx       # Root layout configuration
│   └── page.tsx         # Route entry point, dispatches active view based on state
├── components/
│   ├── layout/
│   │   └── Shell.tsx    # App shell, navigation sidebar, and login page
│   ├── map/
│   │   └── MapContainer.tsx   # React-Leaflet integration wrapper
│   └── views/
│       ├── AdminUsersView.tsx  # Admin access-control dashboard
│       ├── ChatbotView.tsx     # AI copilot assistant chat console
│       ├── DashboardView.tsx   # Analytical charts and summaries
│       ├── ForecastView.tsx    # Predictive time-series settings
│       ├── MapView.tsx         # Spatiotemporal hotspot map
│       ├── NetworkView.tsx     # 2D/3D force-directed co-offender networks
│       ├── ReportsView.tsx     # Aggregation report triggers
│       ├── SearchView.tsx      # Semantic case search input
│       └── SociologicalView.tsx # Correlation matrix and demographic risk
├── lib/
│   └── api.ts           # Interceptor-enabled `authFetch` wrapper
└── types/
    ├── d3-force-3d.d.ts # TypeScript declarations for 3D force-directed layout
    └── leaflet-heat.d.ts # TypeScript declarations for Leaflet Heat plugin
```

---

## 🛠️ Main Libraries & Tools

- **Next.js 16 (App Router)**: Framework for server-side and client-side rendering.
- **React 19**: Frontend UI library.
- **Tailwind CSS v4 & Vanilla CSS**: Unified dark-theme design system.
- **Leaflet & React-Leaflet**: Geographic mapping engine for hotspot rendering.
- **Recharts**: Charting library for crime trend indicators.
- **d3-force & d3-force-3d**: Computes physics layout coordinate tables for co-offender networks.
- **Lucide React**: Icons for sidebar navigation and indicators.

---

## 🔒 Session & Authentication
The frontend manages session tokens inside localized browser storage:
- Auth logic resides in [Shell.tsx](file:///c:/Users/jeltrin/OneDrive/Desktop/policce/KSP-Sentinel/frontend/components/layout/Shell.tsx).
- All requests targeting API routes are dispatched through the [authFetch](file:///c:/Users/jeltrin/OneDrive/Desktop/policce/KSP-Sentinel/frontend/lib/api.ts) wrapper.
- If a request yields a `401 Unauthorized` response (due to token expiration or role updates), `authFetch` clears local storage variables and redirects the client to the login gate.
