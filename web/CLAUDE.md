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
- State lives in the page-level orchestrator (`bracket-board.tsx`, `path-spine.tsx`) and flows down; logic extracted to `lib/`.
- Charts are hand-rolled inline SVG (`prob-bar`, `sparkline`, the bracket canvas); no chart library.
- Sticker aesthetic comes from surface, border and the `.foil` shine only; card rotation is banned.
- Gold is spent on England and the headline number, nothing else.
- British English, no em-dashes, in code, copy and comments alike.

## Wolf mascot

Larry-the-chat cat-loader architecture: one canonical wolf SVG (`components/mascot/wolf-mascot.tsx`) with classed parts, variant registry in `components/mascot/variants.ts` (`idle`, `juggle`, `howl`, `pace`), variant classes scoping keyframes in `globals.css`. Every part animation resolves through `--wolf-anim`, so the idle layer (blink, ear twitch, tail sway) is always on and `prefers-reduced-motion` switches the whole character off with one declaration. `mood` drives the face, `variant` the action; `MOOD_VARIANTS` maps one to the other for headline placements.

## Verification

No frontend test files. Gates: `npm run lint`, `npx tsc --noEmit`, `npm run build`, browser verification at 390px (canvas also at 430px). Dev server: `npm run dev -- -p <port>`; point `BACKEND_URL` at a running backend (which reads `SNAPSHOT_DIR`) to preview a specific snapshot, or rely on the bundled fixture.
