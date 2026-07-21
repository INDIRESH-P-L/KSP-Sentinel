# Design-sync notes — KSP Sentinel frontend

## Scope decision

This repo is the KSP Sentinel Next.js app itself, not a dedicated
design-system package. Only `components/ui/primitives.tsx` (5 generic
primitives: `SectionTitle`, `PanelLabel`, `Panel`, `Pill`, `Loading`) is
synced — set via `cfg.srcDir: "components/ui"`. Everything under
`components/views/`, `components/layout/`, `components/map/` is a full app
screen wired to this app's auth/API and was deliberately excluded (confirmed
with the user). If more reusable primitives are added to `components/ui/`
later, they'll be picked up automatically on the next sync.

## CSS: compiled, not copied raw

The app's `app/globals.css` is a Tailwind v4 entry (`@import "tailwindcss"`
+ `@theme` tokens) — the converter only copies CSS files verbatim, it does
not run a Tailwind build. `cfg.cssEntry` therefore points at the generated
`.ds-sync/compiled-tailwind.css` (gitignored, ephemeral), produced by the
**committed** `.design-sync/compile-css.mjs` (postcss + `@tailwindcss/postcss`,
scanning the whole repo from `base: '.'` so every utility class used anywhere
in the app is included — resolves `postcss`/`@tailwindcss/postcss` from the
app's own `node_modules` since both are already devDependencies here; no
extra install needed). **Re-run `node .design-sync/compile-css.mjs` before
every rebuild** if
`app/globals.css` (or any component using new utility classes) changed — the
build does not do this automatically. (The script previously lived under
`.ds-sync/` by mistake — that path is gitignored and regenerated only from
the skill's own bundled scripts, so a repo-authored script left there would
vanish on a fresh clone. It's now under `.design-sync/`, which is committed.)

## Weak `.d.ts` (synth-entry mode)

There's no real package build/dist for these components (they're plain app
source), so `resolvePackage` synthesizes an entry and the ts-morph prop
extraction can't resolve the destructured inline prop types — every emitted
`<Name>.d.ts` degrades to `[key: string]: unknown`. The real prop shapes are
documented by hand in `.design-sync/conventions.md` instead. If this
repo ever gets a real build step for these primitives, re-check whether prop
extraction improves.

## No Playwright — human-reviewed instead of graded

No Playwright/Chromium is installed in this environment, and the user chose
to skip auto-install (`--no-render-check` on every build/validate/resync
call). The user reviewed the 5 authored previews via the served
`.review.html` directly in a browser and confirmed they render correctly
(after a bug was found and fixed — see below) — that human review stands in
for the automated render-check + grading gate. `resync.mjs`'s capture stage
therefore always fails (`exit 2`, playwright not installed); this is
expected, not a regression, as long as a human has actually looked at
`.review.html` for the changed/added components before upload.

## Known render warns

- None yet — Playwright render-check has never run on this repo.

## Fixed during this sync

- The `Loading` preview initially appeared to render collapsed with no
  height when the user looked at a stale `.review.html` load (before the
  authored-preview rebuild had finished). Re-confirmed correct after a
  hard refresh — not a real bug, no code change needed.

## Re-sync risks

- `compile-css.mjs`'s output is a snapshot — it goes stale silently if
  `app/globals.css` changes or a synced primitive starts using a new
  Tailwind utility class that isn't used elsewhere in the app (the whole-repo
  scan should catch this in practice, but it's worth re-running before every
  resync regardless).
- No automated render-check has ever run here (no Playwright). If Playwright
  becomes available later, drop `--no-render-check` and do a full first real
  automated verification pass rather than assuming the human review still
  covers it.
- `componentSrcMap`/grouping: all 5 components fell into `general` since
  they share one source file — if they're ever split into per-component
  files, groups will change (harmless, but re-verify the project's card
  layout after).
