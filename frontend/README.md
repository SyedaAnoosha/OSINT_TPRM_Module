# Vendor Risk — frontend (Phase 4)

Streaming scorecard + methodology for the OSINT TPRM scoring API.
**React 19 + Vite + Tailwind v4 + React Router**, light/dark, with a fixed sidebar.
Fonts: **Plus Jakarta Sans** (primary) + **JetBrains Mono** (secondary), self-hosted via `@fontsource`.
Palette: navy `#111e41`, surface `#f6f7fb`, accent `#33a0e7`.

## Run

The frontend talks to the FastAPI backend over `/api` (Vite proxies it to `:8000`).

```bash
# 1. start the API (from ../backend, with a Python venv)
cd ../backend
uvicorn app.api:app --port 8000

# 2. start the UI
cd ../frontend
npm install
npm run dev            # http://localhost:5173
```

Type a vendor **name** (`Atlassian`) or **domain** (`snowflake.com`) and hit **Score vendor**.
Progress streams in over SSE as each collector lands; the scorecard renders when scoring completes.

## What it shows (the designed states — see `docs/methodology.md` §5.4)

- **Risk + confidence, always adjacent** — a bare score is never displayed.
- **Quadrant** — `Evidenced clean` / **`The Ghost`** / `Verified exposure` / `Uncorroborated signal`,
  each with a plain-language subtitle. The Ghost reads as *unassessed*, not *safe*.
- **Knockout-floor cause** stated on the card when a directly-observed critical raised the minimum.
- **Category breakdown** → expand → **evidence receipts** (hash-stamped, fetched on demand).
- **BLOCKED** (sanctions/ambiguous entity → human adjudication) and **Insufficient evidence** as
  distinct, unmissable states — not a red number.
- **Gap disclosure** (held sources + DFAT not screened), **NVD/HIBP/GDELT attribution**,
  **coverage-tracks-size** and **perimeter-not-posture** caveats — all on the card.

## Layout

- `src/main.jsx` — fonts, router, routes (`/` Score, `/methodology`).
- `src/components/Layout.jsx` — sidebar shell (nav + theme toggle) + responsive mobile drawer.
- `src/components/ui.jsx` — shadcn-style primitives (Button, Card, Badge, Progress, Meter).
- `src/pages/ScorePage.jsx` — input, SSE progress, dispatch.
- `src/pages/MethodologyPage.jsx` — two axes, framework/weights, system flow, sources.
- `src/Scorecard.jsx` — the result: scored / blocked / refused states, categories, receipts, disclosures.
- `src/api.js` — API client (POST score, consume SSE stream, fetch score + evidence).
- `src/lib/` — `utils.js` (`cn`, risk/confidence colors), `theme.js` (light/dark hook).
- `src/index.css` — Tailwind v4 + the palette mapped to light/dark design tokens.

> Styling is Tailwind v4 with shadcn-style components hand-built on the design tokens (no CLI/Radix
> tree). Dark mode is a `.dark` class on `<html>`, persisted to `localStorage`.
