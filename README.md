# OSINT for Third-Party Risk — running the app

Vendor name or domain **in** → a defensible, evidence-linked risk record **out**, from
lawfully-public OSINT. Two axes (risk 0–100, confidence 0–1) that are never collapsed.

**The methodology is the product** — see [`docs/methodology.md`](docs/methodology.md) and the
machine-readable model in [`scoring.yaml`](scoring.yaml). This is the guide to *running* it.

```
┌──────────┐   POST /score    ┌─────────────────────────┐   SSE progress   ┌──────────┐
│ frontend │ ───────────────► │ backend (FastAPI)       │ ───────────────► │ scorecard│
│  :5173   │ ◄─────────────── │ collectors, scoring,    │ ◄─────────────── │  renders │
└──────────┘   /api proxy     │ append-only evidence db │   full record    └──────────┘
                              └─────────────────────────┘
```

## Prerequisites

- **Python ≥ 3.11**
- **Node ≥ 18** (repo tested on Node 26) + npm
- No paid keys required. Core sources are free/no-auth; a few optional collectors (ABN Lookup,
  Companies House, OTX) use **free** API keys and skip gracefully when unset.
- **Postgres required** — set `DATABASE_URL` (a Neon string works). No local-file fallback.

---

## 1. Backend (FastAPI API)

```bash
cd backend

# create + activate a virtualenv
python -m venv .venv
# Windows (Git Bash):   source .venv/Scripts/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate

pip install -r requirements.txt

# config (optional — sensible defaults; the app runs with none of this set)
cp .env.example .env        # then edit if you want a real contact UA / API keys

# run the API
uvicorn app.api:app --port 8000 --reload
```

The API is now at **http://127.0.0.1:8000** (interactive docs at `/docs`).

**Storage: Postgres only.** Set `DATABASE_URL` (a Neon connection string, or any Postgres) — the
app fails loudly at startup without it. There is no local-file fallback: the append-only,
hash-stamped evidence store is the legal artefact the score is published from (Finding A), and a
weaker persistence guarantee is not a substitute for it.

### Try it without the UI

```bash
# score a vendor: returns a job id + an SSE stream URL
curl -s -X POST http://127.0.0.1:8000/api/vendors/score \
     -H 'Content-Type: application/json' -d '{"domain":"atlassian.com"}'

# watch progress stream as each collector lands
curl -N http://127.0.0.1:8000/api/jobs/<job_id>/stream

# fetch the finished record (risk + confidence + quadrant + categories)
curl -s http://127.0.0.1:8000/api/vendors/atlassian | python -m json.tool

# pull a hash-stamped evidence receipt behind any finding
curl -s http://127.0.0.1:8000/api/vendors/atlassian/evidence

# WHO the vendor is — industry, size, country, ownership, and its peer cohort
curl -s http://127.0.0.1:8000/api/vendors/atlassian/profile | python -m json.tool

# how it reads against its peers — or the stated reason no comparison is published
curl -s http://127.0.0.1:8000/api/vendors/atlassian/benchmark | python -m json.tool

# comparison is cohort-bounded: mismatched vendors get a 409 naming both cohorts
curl -s -X POST http://127.0.0.1:8000/api/compare \
     -H 'Content-Type: application/json' -d '{"refs":["atlassian","snowflake"]}'
```

Or score straight from the command line, no server:

```bash
python -m app.harness --domain atlassian.com --ref atlassian --name Atlassian   # all collectors
python -m app.harness --domain atlassian.com --ref atlassian --only dns          # one collector
```

---

## 2. Frontend (streaming scorecard)

Open a **second terminal** (leave the API running):

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

Vite proxies `/api` → `http://127.0.0.1:8000`, so the two are same-origin (SSE needs this).
Type a vendor **name** (`Atlassian`) or **domain** (`snowflake.com`), hit **Score vendor**, and the
scorecard streams in. See [`frontend/README.md`](frontend/README.md) for the designed states.

### Optional: AI evidence summary

A **read-layer** LLM digest of a finished record. It is **off by default** and provider-agnostic —
point it at any OpenAI-compatible `chat/completions` endpoint (OpenRouter, Groq, Google's
OpenAI-compat surface). Set three env vars and the **Summarise evidence** button appears on the
scorecard:

```bash
# in backend/.env  — pick ONE provider (see .env.example for Groq / Gemini)
TPRM_LLM_BASE_URL=https://openrouter.ai/api/v1
TPRM_LLM_API_KEY=sk-...
TPRM_LLM_MODEL=google/gemini-2.0-flash-001
```

Guardrails, by design: the summary **never computes or changes a score** and **never writes to the
evidence store** — it reads the published score plus the hash-stamped receipt index, is returned
marked *AI-generated*, and cites the hashes it was built from. **Raw collector payloads are never
sent to the LLM** — only score roll-ups + receipt metadata leave the system (the single, documented
egress point; see [`docs/source_assessment.md`](docs/source_assessment.md) → *Data egress*). Without
the keys, `POST /api/vendors/{ref}/summary` returns **503** and the button stays hidden.

---

## 3. Tests & linting

```bash
# backend  (from backend/, venv active)
pytest -q                       # 109 tests
ruff check app tests            # lint

# frontend (from frontend/)
npm run lint
npm run build
```

> Tests need `DATABASE_URL` (the same Neon database the app uses). Each test that touches the
> store runs in its own **disposable schema** (`tprm_test_<uuid>`), created fresh and dropped whole
> afterwards, so the suite never touches — or pollutes — your real `public` data. The pure-logic
> tests (scoring, benchmarking, normalisation) stay offline and need no database.

---

## Reference vendor set

`Atlassian` · `Snowflake` · `MYOB` · `OneTrust` · `Slack` — real TPRM targets spanning
listed/private, software-shipping/pure-SaaS, single-register/corroborated. (`Xero` demonstrates the
sanctions gate: it is correctly **BLOCKED** and routed to human adjudication.)

## Notes & gotchas

- **Name vs domain — we don't guess.** Most collectors are domain-specific, so a bare **name**
  (`Atlassian`) is *not* auto-scored: the app returns a short list of **candidate domains** to
  confirm (or a field to type the exact one), and only analyses once you pick. Guessing a
  `<slug>.com` and silently scoring it would risk assessing the wrong company — so it asks.
  Enter a **domain** directly to score straight away.
- **Most vendors come back *quiet.*** A low-confidence result labelled **The Ghost** means
  *unassessed*, not *safe* — that is the point, not a bug.
- **`digital_footprint` depends on Certificate Transparency** (crt.sh, with a Cert Spotter fallback).
  crt.sh is famously flaky; the anonymous Cert Spotter tier is rate-limited. If CT is briefly down,
  that category zeros and a clean vendor can read as The Ghost — honest, and recoverable. Set
  `TPRM_CERTSPOTTER_TOKEN` (free key) to raise the CT limit, and/or `TPRM_OTX_API_KEY` (free
  AlienVault OTX key) to add **passive-DNS redundancy** that carries the category when CT is down.
- **Politeness:** several sources (Wikidata, HIBP) want a descriptive, contact-bearing `User-Agent`.
  The default in `.env.example` works; set your own contact for a real deployment.
- **The sanctions gate stays human.** A watchlist match BLOCKS and emits no score by design
  (Autonomous Sanctions Act s 16(7) — the adjudication is the evidence).

---

## Peer benchmarking

A posture means different things in different industries, so the scorecard reads it against a
**peer cohort on four factors — industry × revenue × headcount × region**. **This changes no
arithmetic:** the same findings produce the same posture for a bank and a bakery; only the reading
differs. The model file is untouched, and the frozen regression corpus still passes.

**Revenue and headcount are separate dimensions, not one blended "size".** They disagree often and
the disagreement is informative: a 40-person firm turning over $400M is a high-leverage money mover;
a 4,000-person firm at the same revenue is a large employer with a large attack surface.

**The widening ladder is what makes four factors workable.** 12 sectors × 5 revenue × 5 headcount ×
5 regions is **1,500 possible cohorts** — an exact match would almost never fill (a real 114-vendor
run produced two populated cohorts, the largest holding four). So when the exact cohort is too thin
the system steps out — drop region, then revenue, then headcount — and **says so on the card**:
*"wider peer group used: industry + headcount + region"*. It never widens past industry; there is
deliberately no rung comparing a bank to every vendor ever scored.

**The refusal is still the feature.** Below `cohort.min_cohort_n` peers at *every* rung (default
**8**, in [`benchmarks.yaml`](benchmarks.yaml)) the card reads *"insufficient peers (4 of 8) at
every cohort width"* rather than a percentile. Comparison is cohort-bounded at the API:
`POST /api/compare` on vendors from different cohorts returns **409** naming both.

**Honest statistics, not flattering ones.** The percentile is rounded to the step the sample can
actually express and publishes that step (`50 ±25` at n=4); a **quartile** rides alongside because
it survives one peer joining or leaving. Stale and thinly-evidenced peers are excluded and the
exclusion is disclosed. Every benchmark carries the standing caveat that peers are vendors *this
deployment happened to score* — a convenience sample, not an industry norm. Per-category variance is
reported too, because *"your breach history is 30 below peers"* is actionable where one overall
number is not.

`benchmarks.yaml` ships with **no sector targets**, deliberately. Nobody publishes them, and
asserting *"financial services should score 95"* has the same defect as the category weights §5.6
deleted. An `expected_posture` entry is only loadable with a `basis:` naming a real source.

```bash
# a cohort needs a population — seed one by scoring real vendors (global, 10 sectors)
python -m app.seed_cohorts --list                    # what would be scored
python -m app.seed_cohorts --sector technology       # one sector
python -m app.seed_cohorts --status                  # cohort depth vs the gate
```

**Two optional client-supplied inputs**, both recorded as client-supplied and neither scored:
`criticality` (how much *this* buyer depends on the vendor — not observable from outside) and
`size_band` (public sources publish an industry for most vendors but a headcount for far fewer, and
a sector with no size cannot form a cohort).

## Layout

```
scoring.yaml        the model (the deliverable) — bands, penalties, gates, confidence
benchmarks.yaml     peer cohorts, size bands, the minimum-peers gate — interpretation, no arithmetic
backend/            FastAPI API, collectors, scoring engine, append-only evidence store
frontend/           React + Vite single-screen streaming scorecard
docs/               methodology, scoring model, metrics, source assessment, running guide
ops/                scheduled monitoring (cron / systemd / Windows Task Scheduler)
```

See [`docs/`](docs/) for the full documentation set — start with
[`docs/methodology.md`](docs/methodology.md) (the research and rationale) and
[`docs/system_retrospective.md`](docs/system_retrospective.md) (current, verified status).

## License

[MIT](LICENSE)
