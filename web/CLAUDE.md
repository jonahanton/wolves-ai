# Web app architecture memory

Next.js App Router, TypeScript strict, Tailwind 4. Mobile-first at 390px; five bottom tabs (Today, Path, Bracket, Live, More). The app is a pure function of (snapshot, previous snapshot, static data): no client fetching, no app state store.

## Data flow

```
snapshot JSON (S3 in prod, ../runs locally; served by the Python backend in backend/)
  -> lib/load-snapshot.ts (server-side fetch of BACKEND_URL/snapshots/latest, bundled fixture fallback)
  -> lib/*-view.ts pure derive modules (bracket-view, spine-view, markets, derive)
  -> RSC pages (src/app/*/page.tsx) build view models server-side
  -> client islands receive plain props ("use client" only where interaction demands it)
```

All AWS access lives in the Python backend (`backend/`). The web app never touches AWS: browser calls go to `/api/*`, which `src/app/api/[...slug]/route.ts` forwards verbatim to `BACKEND_URL` (snapshots, admin run-history/schedule/run-now/stop).

- `lib/snapshot.ts` mirrors the engine's frozen snapshot schema (engine/wolves/snapshot.py). Do not edit casually; it is a cross-language contract pinned by Python parity tests.
- Optional agent fields (`agent.narrative`, `agent.ledger_entries`, future `markets`) are read ONLY through the tolerant accessors in `lib/agent-fields.ts` and `lib/markets.ts`; every surface renders a quiet honest placeholder when they are absent.
- `lib/schedule.json` and `lib/venues.json` are verbatim copies of `data/format/*.json` (canonical, engine-owned). `lib/schedule.ts` / `lib/venues.ts` are their typed registries. Never hand-write tournament facts anywhere else; insight comes from the agent's narrative fields, not hardcoded trait chips.

## What lives where

- `src/app/` - one RSC page per tab plus the single `api/[...slug]` proxy route. Pages only load the snapshot, call derive functions and compose components.
- `src/lib/` - pure modules, no React: bracket graph maths (`bracket.ts`), view-model builders (`bracket-view.ts`, `spine-view.ts`), canvas layout (`bracket-canvas.ts`), formatting (`format.ts`), delta computation (`derive.ts`).
- `src/hooks/` - focused client hooks; `use-pan-zoom.ts` is the hand-rolled pan/zoom controller (refs + rAF, transform-only updates, no React re-render per frame).
- `src/components/` - grouped by tab (`today/`, `path/`, `bracket/`, `live/`, `more/`) plus `shell/`, `charts/`, `mascot/`, `ui/`. Leaves are pure functions of props.
- `src/components/ui/` - only primitives actually in use (`segmented`, `sheet` on Base UI). Add primitives when a consumer exists, never speculatively.

## Conventions

- Kebab-case files, one main component each, local `interface XxxProps` above the component, never `React.FC`, casts via `unknown`, no barrels, direct `@/` imports.
- State lives in the page-level orchestrator (`bracket-board.tsx`, `path-spine.tsx`, `today-board.tsx`) and flows down; logic extracted to `lib/`.
- Charts are hand-rolled inline SVG (`prob-bar`, `sparkline`, the bracket canvas); no chart library. 1.5px strokes, 11px axis labels, a plain-English sentence above each chart.
- Type: Funnel Display (`font-display`, via next/font/google) for page titles and headline numbers; Switzer (self-hosted in `src/fonts/`) for UI text. Both have uniform-width digits and `html` sets `font-variant-numeric: tabular-nums`; only swap fonts for faces that keep that true.
- Dark theme is a four-step luminance scale (`--background` #0b0b0d, `--card` #141417, `--secondary`/`--muted` #1c1c21, `--popover` #26262c), alpha-white hairlines, off-white text ramp; no shadows or blur on dark surfaces, no radius above 12px (`--radius-xl` is the cap).
- Probabilities render as whole numbers clamped to `<1%`/`>99%` (`format.ts`), with `PctValue` for big numerals and `ProbBar` thin underlines; table cells heat-fill via `lib/heat.ts` (one hue, gold ramp only for England rows).
- Motion budget: the Today hero digit roll (`use-rolling-value`), one `.foil-once` shimmer per session, 150ms fades elsewhere; `prefers-reduced-motion` switches each off. The `.foil` sheen is static and is the only gradient allowed.
- Run-over-run movement comes from `lib/snapshot-history.ts` (localStorage, last 12 run summaries) via `use-snapshot-history`; delta badges use the desaturated `--delta-up`/`--delta-down` pair, never gold.
- Gold is spent on England and the headline number, nothing else.
- British English, no em-dashes, in code, copy and comments alike.

## Wolf mascot

Larry-the-chat cat-loader architecture: one canonical wolf SVG (`components/mascot/wolf-mascot.tsx`) with classed parts, variant registry in `components/mascot/variants.ts` (`idle`, `juggle`, `howl`, `pace`), variant classes scoping keyframes in `globals.css`. Every part animation resolves through `--wolf-anim`, so the idle layer (blink, ear twitch, tail sway) is always on and `prefers-reduced-motion` switches the whole character off with one declaration. `mood` drives the face, `variant` the action; `MOOD_VARIANTS` maps one to the other for headline placements.

## Verification

No frontend test files. Gates: `npm run lint`, `npx tsc --noEmit`, `npm run build`, browser verification at 390px (canvas also at 430px). Dev server: `npm run dev -- -p <port>`; point `BACKEND_URL` at a running backend (which reads `SNAPSHOT_DIR`) to preview a specific snapshot, or rely on the bundled fixture.
