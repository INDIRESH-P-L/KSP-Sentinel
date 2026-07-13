"use client";

import React from "react";
import DashboardView from "@/components/views/DashboardView";
import MapView from "@/components/views/MapView";
import ForecastView from "@/components/views/ForecastView";
import NetworkView from "@/components/views/NetworkView";
import SearchView from "@/components/views/SearchView";
import ChatbotView from "@/components/views/ChatbotView";
import ReportsView from "@/components/views/ReportsView";

export default function Home({ activeTab }: { activeTab?: string }) {
  // Dispatch views based on the selected tab from Shell
  switch (activeTab) {
    case "dashboard":
      return <DashboardView />;
    case "map":
      return <MapView />;
    case "forecast":
      return <ForecastView />;
    case "network":
      return <NetworkView />;
    case "search":
      return <SearchView />;
    case "chatbot":
      return <ChatbotView />;
    case "reports":
      return <ReportsView />;
    default:
      return <DashboardView />;
  }
}
