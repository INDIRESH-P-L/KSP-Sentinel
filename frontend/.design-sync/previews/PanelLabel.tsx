import { PanelLabel } from 'frontend';
import { MapPin, AlertTriangle } from 'lucide-react';

export function Default() {
  return <PanelLabel>Crime Frequency — Monthly Trend</PanelLabel>;
}

export function WithIcon() {
  return (
    <PanelLabel className="flex items-center gap-2">
      <MapPin className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Top Active Police Stations
    </PanelLabel>
  );
}

export function DangerTone() {
  return (
    <PanelLabel className="flex items-center gap-2 !text-[var(--color-danger)]">
      <AlertTriangle className="h-4 w-4" /> Statistical Anomaly Alert Feed
    </PanelLabel>
  );
}
