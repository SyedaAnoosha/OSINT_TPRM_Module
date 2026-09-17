# Running Guide

How to get the backend, the database and the frontend up, and what to run once they are.

Everything here has been executed against this repository. Where a step is a decision rather than a
command, the decision is stated rather than hidden behind a default.

*For the fast path, see the root [`README.md`](../README.md) — same commands, without the
rationale. Come here for the Postgres/Neon specifics, monitoring, and troubleshooting.*

---

## 0 · What you need first

| Requirement | Why |
|---|---|
| **Python 3.12** | The backend targets it; `app/` uses 3.12 syntax throughout. |
| **Node 20+** | Vite 8 / React 19. |
| **A Postgres connection string** | **Non-negotiable.** There is no local-file fallback — see §2. |

Nothing else is required to start. Every collector works without an API key; keys raise rate
limits, they do not unlock functionality.

---

## 1 · Backend

### 1.1 Create the virtual environment and install

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt     # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS / Linux
```

`requirements.txt` includes `psycopg_pool`. It is technically optional — `app/storage.py` falls
back to opening a connection per store without it — but do not skip it. A Neon TLS handshake costs
about 0.7 s and the API builds a store per request; without the pool you pay that on every call.

### 1.2 Configure the environment

```bash
cp .env.example .env
```

Then edit `backend/.env`. Only two things actually matter to start:

```ini
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
TPRM_CONTACT_EMAIL=you@example.com
```

`TPRM_CONTACT_EMAIL` is not decoration. Wikidata and HIBP ask for a contact-bearing User-Agent and
Wikimedia returns 403 to a generic one — leave it at `REPLACE_ME` and you will lose those sources
and, with them, coverage.

> `.env` is gitignored and has never been committed. Keep it that way.

### 1.3 Run the API

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.api:app --reload --port 8000
```

**Use port 8000.** `frontend/vite.config.js` proxies `/api` to `http://127.0.0.1:8000`, so the SPA
and the API are same-origin in development. That is not a stylistic choice: `EventSource` (the
streaming score endpoint) has no CORS preflight escape hatch, so same-origin is the only simple
correct setup. Run the API on another port and the frontend will 404 every call.

- Interactive API docs: <http://127.0.0.1:8000/docs>
- On startup a background thread warms the connection pool. The first request after boot may be
  slightly slow; it is not waiting on you.

---

## 2 · Database

### 2.1 There is no SQLite mode

`app/storage.py` raises `StorageNotConfigured` when `DATABASE_URL` is unset, deliberately and
loudly. A defensible, reconstructible evidence trail is the product; "it works on my machine with a
throwaway file" is not the same guarantee as "it is in the managed, append-only, hash-stamped store
the score was published from".

### 2.2 Tables create themselves — once

**You do not run migrations.** The first store constructed in a process applies the whole schema:
tables, indexes, the `reject_mutation()` function and 24 append-only triggers. Everything is
`CREATE ... IF NOT EXISTS` / `CREATE OR REPLACE`, so pointing the app at an empty database is all
the setup there is.

Two details worth knowing, because they were both once bugs:

- **It runs once per process, not once per connection.** The DDL is guarded by an in-process set
  keyed on `(dsn, schema)`. It used to run on every store construction — 24 `CREATE OR REPLACE
  TRIGGER` statements, each taking an `AccessExclusiveLock`, in front of every HTTP request. That
  cost 2.6 s per call and deadlocked whenever two requests overlapped.
- **It is serialised cluster-wide** by a transaction-level advisory lock, so a uvicorn worker and a
  CLI run starting at the same moment cannot deadlock against each other.

### 2.3 The store is append-only, and Postgres enforces it

`UPDATE` and `DELETE` are rejected by trigger on `evidence`, `scores`, `findings`, `disputes`,
`decisions`, profiles, cohort tables and `monitor_runs`. This matters operationally:

- **You cannot clean up a mistake by editing rows.** Corrections are appended — a new score, a new
  dispute event, a new monitor run.
- **Tests cannot share a schema with real data.** `conftest.py` gives each test a fresh
  `tprm_test_<uuid>` schema and drops it afterwards (`DROP SCHEMA` is DDL, so the triggers do not
  block it).

### 2.4 Verify the connection

```bash
cd backend
.venv/Scripts/python.exe -c "from app.storage import get_store; s=get_store(); print(len(s.latest_scores_all()), 'vendors'); s.close()"
```

A fresh database prints `0 vendors`. That is success — it means the schema was created and read.

### 2.5 Neon pooled vs unpooled endpoints

The app uses the **pooled** endpoint (the host containing `-pooler`). The test suite rewrites the
DSN to the **unpooled** host, because it sets a per-run `search_path` and PgBouncer in transaction
mode will not carry a session setting across the pooling boundary. You do not need to configure
this — `conftest.py` does the rewrite — but if you see schema-isolation behaving oddly, that is
where to look.

---

## 3 · Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves on <http://127.0.0.1:5173> and proxies `/api` to the backend on :8000. **Start the
backend first**, or the first page load will show empty states rather than data.

Other scripts:

```bash
npm run lint       # eslint, including the react-hooks rules — treat warnings as failures
npm run build      # production bundle into dist/
npm run preview    # serve the built bundle
```

---

## 4 · Putting data in the book

A fresh database has a schema and no vendors. Nothing below is required to boot the app; all of it
is required before the portfolio, programme and inventory screens say anything.

### 4.1 Score a single vendor

```bash
cd backend
.venv/Scripts/python.exe -m app.score_harness --domain atlassian.com --name Atlassian
```

Or through the API — the same pipeline, and what the `/assess` screen calls:

```bash
curl -X POST http://127.0.0.1:8000/api/vendors/score \
  -H 'Content-Type: application/json' \
  -d '{"domain":"atlassian.com","name":"Atlassian","criticality":"high"}'
```

Supply `criticality` when you have it. It is a client declaration nothing can observe, and it is
what unlocks residual risk reporting for that vendor.

### 4.2 Seed peer cohorts

Benchmarking needs peers. A percentile against three companies is not a percentile.

```bash
.venv/Scripts/python.exe -m app.seed_cohorts --list      # what would be seeded
.venv/Scripts/python.exe -m app.seed_cohorts --status    # cohort depth against every gate
.venv/Scripts/python.exe -m app.seed_cohorts --all       # slow: these are other people's free APIs
```

`--concurrency` defaults to **1** on purpose. Raising it makes you a worse citizen of every free
API this depends on. Seed a single sector first (`--sector technology`) rather than starting with
`--all`.

**If you scored vendors before August 2026, run the backfill once:**

```bash
.venv/Scripts/python.exe -m app.seed_cohorts --backfill-attributes --dry-run
.venv/Scripts/python.exe -m app.seed_cohorts --backfill-attributes
```

`supplier_attributes` is the only table the v2 cohort query reads, and until recently **nothing in
the scoring pipeline wrote it** — the only writers were the v2 attributes route and the inherent
register. So a vendor could be fully assessed, carry a sector resolved from Wikidata or GLEIF, and
still be invisible to every peer group. The pipeline records the row on each run now, but that only
helps vendors scored from here on; the backfill gives the ones you already have their row, **from
the profile already stored**. It queries no source and re-scores nothing.

It **merges, never overwrites**: only fields the stored row lacks are filled, so a client
correction, an upheld cohort dispute and any declared `data_access_scope` all survive.

### 4.3 Declare inherent risk tiers

```bash
.venv/Scripts/python.exe -m app.inherent_register --status     # the three populations, writes nothing
.venv/Scripts/python.exe -m app.inherent_register --dry-run    # what --apply would write
.venv/Scripts/python.exe -m app.inherent_register --apply      # append the declarations
```

`--status` reports against **relationships**, not against every scored row. A seeded corpus vendor
has no relationship with you and therefore has no inherent tier to declare; counting it as
undeclared makes the programme look negligent about a question that does not apply to it.

### 4.4 Monitoring

Two entry points, and the distinction matters:

```bash
.venv/Scripts/python.exe -m app.monitor --by-tier --dry-run    # ad-hoc: what is stale
.venv/Scripts/python.exe -m app.scheduler --run                # the scheduled sweep, ledgered
.venv/Scripts/python.exe -m app.scheduler --health             # exits 1 when the schedule is dead
```

Use `scheduler --run` from cron or Task Scheduler, never `monitor`. The scheduler writes a run
ledger; `monitor` does not. **A scheduled job's failure mode is silence, not error** — without the
ledger, `monitoring_currency` can read 100% on a schedule that stopped firing weeks ago. Ready-made
crontab, systemd units and a `Register-MonitorTask.ps1` are in [`ops/schedule/`](../ops/schedule/).

`--health` is the thing to alert on. It fails when no run has been recorded for 48 hours.

---

## 5 · Tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q
```

The suite needs `DATABASE_URL` and **skips** rather than fails without it. It creates and drops a
schema per test, so it costs Neon round trips — a full run takes several minutes. That is the price
of an append-only store: rows cannot be cleaned between tests, so isolation has to be a fresh
schema each time.

Run a subset while iterating:

```bash
.venv/Scripts/python.exe -m pytest tests/test_inherent_register.py -q
```

---

## 6 · Troubleshooting

**`StorageNotConfigured: DATABASE_URL is not set`**
`backend/.env` is missing or unreadable. The app will not fall back to a local file by design.

**`psycopg.errors.DeadlockDetected` on `cur.execute(_SCHEMA)`**
Fixed — the schema DDL now runs once per process under an advisory lock. If you see it again, you
are running code from before that change; check `_ensure_schema` exists in `app/pg_store.py`.

**Screens load slowly**
Check the API directly before suspecting the frontend:
```bash
curl -o /dev/null -s -w '%{time_total}s\n' http://127.0.0.1:8000/api/portfolio
```
`/api/portfolio` and `/api/program/kpis` are the two book-wide endpoints. Both should answer in a
few seconds. If either takes tens of seconds, something has reintroduced a per-vendor query loop —
these routes must read the book through the `*_all()` bulk store methods, not by calling a
per-vendor method 146 times.

**Frontend shows empty states everywhere**
The backend is not on :8000, or is not running. Vite's proxy target is fixed in
`frontend/vite.config.js`.

**`only one usage of each socket address` on startup**
A previous uvicorn is still bound to the port. Find and stop it:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
Stop-Process -Id <pid> -Force
```

**A collector returns nothing**
Expected, and handled. Sources fail independently: one silent source lowers *confidence*, never
*posture*. Check `TPRM_CONTACT_EMAIL` is set to a real address before investigating further —
several sources 403 a generic User-Agent.

---

## 7 · Quick reference

```bash
# terminal 1 — API
cd backend && .venv/Scripts/python.exe -m uvicorn app.api:app --reload --port 8000

# terminal 2 — SPA
cd frontend && npm run dev
```

| URL | What |
|---|---|
| <http://127.0.0.1:5173> | The application |
| <http://127.0.0.1:8000/docs> | OpenAPI browser |
| <http://127.0.0.1:8000/api/portfolio> | The whole book as JSON |
