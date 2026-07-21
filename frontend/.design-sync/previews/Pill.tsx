import { Pill } from 'frontend';
import { TrendingUp } from 'lucide-react';

export function AllTones() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill tone="ok">Active</Pill>
      <Pill tone="warn">98 FIRs</Pill>
      <Pill tone="danger">Inactive</Pill>
      <Pill tone="info">z = 2.4</Pill>
      <Pill tone="neutral">142 FIRs</Pill>
    </div>
  );
}

export function WithIcon() {
  return (
    <Pill tone="ok" className="px-3 py-1">
      <TrendingUp className="h-3 w-3" /> Live · Karnataka State
    </Pill>
  );
}
