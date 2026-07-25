"use client";

import React, { useContext } from "react";
import { TabContext } from "@/components/layout/Shell";
import DashboardView from "@/components/views/DashboardView";
import MapView from "@/components/views/MapView";
import ForecastView from "@/components/views/ForecastView";
import NetworkView from "@/components/views/NetworkView";
import SearchView from "@/components/views/SearchView";
import ChatbotView from "@/components/views/ChatbotView";
import ReportsView from "@/components/views/ReportsView";
import SociologicalView from "@/components/views/SociologicalView";
import RecordsBrowserView from "@/components/views/RecordsBrowserView";

export default function Home() {
  const { activeTab } = useContext(TabContext);

  // Dispatch views based on the selected tab from Shell
  switch (activeTab) {
    case "dashboard":
      return <DashboardView />;
    case "map":
      return <MapView />;
    case "records":
      return <RecordsBrowserView />;
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
    case "sociological":
      return <SociologicalView />;
    default:
      return <DashboardView />;
  }
}
