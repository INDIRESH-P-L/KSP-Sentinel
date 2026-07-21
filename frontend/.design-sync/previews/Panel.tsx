import { Panel, PanelLabel, Pill } from 'frontend';
import { MapPin } from 'lucide-react';

export function Default() {
  return (
    <Panel>
      <PanelLabel className="mb-4 flex items-center gap-2">
        <MapPin className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Top Active Police Stations
      </PanelLabel>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[var(--color-ink)]">Indiranagar PS</span>
          <Pill tone="neutral">142 FIRs</Pill>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-[var(--color-ink)]">Kalasipalya PS</span>
          <Pill tone="warn">98 FIRs</Pill>
        </div>
      </div>
    </Panel>
  );
}

export function Hoverable() {
  return (
    <Panel hover className="max-w-xs">
      <PanelLabel className="mb-2">Gateway Status</PanelLabel>
      <p className="text-xs text-[var(--color-ink-muted)]">
        Hover this card — elevation and border lift on hover for interactive panels.
      </p>
    </Panel>
  );
}
