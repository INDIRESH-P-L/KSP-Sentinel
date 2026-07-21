## KSP Sentinel UI conventions

This is a small, app-embedded set of 5 primitives (`SectionTitle`, `PanelLabel`,
`Panel`, `Pill`, `Loading`) plus the full design-token/CSS layer from KSP
Sentinel, a dark "command-center" police intelligence console. There is no
provider or theme component to import — everything is driven by CSS custom
properties and two utility classes.

### Setup

No wrapper/provider is required. The system defaults to **dark**. For light
mode, set `data-theme="light"` on the root element (e.g. `<html
data-theme="light">` or any ancestor) — every token below flips via a
`:root[data-theme="light"]` override already shipped in `styles.css`. The
`--font-sans` token references an Inter variable with a full fallback chain
(`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`), so the UI still
looks correct if the host page never loads Inter.

### Styling idiom: CSS custom properties + two utility classes

There are no component style props beyond `Pill`'s `tone`. Everything else is
built from **Tailwind utility classes referencing these tokens via arbitrary
values** (`text-[var(--color-ink)]`, `bg-[var(--color-accent-cyan)]/10`,
`rounded-[var(--radius-well)]`) — that is the idiom used throughout the real
app, not inline hex values.

- Surfaces: `--color-base`, `--color-surface`, `--color-surface-2`, `--color-elevated`
- Text: `--color-ink`, `--color-ink-muted`, `--color-ink-faint`
- Borders: `--color-hairline`, `--color-hairline-strong`
- Accents: `--color-accent-cyan`, `--color-accent-blue`, `--color-accent-green`, `--color-accent-purple`, `--color-accent-pink`, `--color-accent-amber`, `--color-accent-red`
- Status: `--color-ok`, `--color-warn`, `--color-danger`
- Radii: `--radius-panel` (16px, cards/panels), `--radius-pill` (badges), `--radius-well` (inputs, small tiles)
- Shadows: `--shadow-panel`, `--shadow-pop`

The `.glass` class is the core surface primitive — every panel-like container
in the real app uses `className="glass"`, and `.glass-hover` adds the
lift-on-hover transition for clickable cards. Reach for these two classes
instead of hand-rolling a translucent bordered box.

### Component props (the shipped `.d.ts` is a stub — use these instead)

Because this DS has no real package build, the emitted `.d.ts` files widen to
`[key: string]: unknown`. The real shapes, read from source:

- `SectionTitle({ children, className? })` — bold uppercase page/section heading.
- `PanelLabel({ children, className? })` — small bold uppercase panel header.
- `Panel({ children, className?, hover? })` — the `.glass` wrapper as a component; pass `hover` for the lift-on-hover treatment.
- `Pill({ children, tone?, className? })` — `tone` is one of `"ok" | "warn" | "danger" | "info" | "neutral"` (default `"neutral"`).
- `Loading({ label? })` — full-panel centered loading state; `label` defaults to `"Loading command datafeeds…"`.

### Where the truth lives

Link only `styles.css` at the project root — it `@import`s `_ds_bundle.css`
(tokens + `.glass` rules). Per-component usage is in
`components/general/<Name>/<Name>.prompt.md`.

### Build snippet (adapted from a verified preview)

```jsx
const { Panel, PanelLabel, Pill } = window.KspSentinel;

function TopStations() {
  return (
    <Panel>
      <PanelLabel className="mb-4">Top Active Police Stations</PanelLabel>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--color-ink)]">Indiranagar PS</span>
        <Pill tone="neutral">142 FIRs</Pill>
      </div>
    </Panel>
  );
}
```
