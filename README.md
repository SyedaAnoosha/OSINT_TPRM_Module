# OSINT for Third-Party Risk

A vendor name or domain yields a defensible, evidence-linked risk record assembled from
lawfully-public OSINT. Risk (0–100) and confidence (0–1) are reported as separate axes and are
never collapsed into a single figure.

**The methodology is the product.** The rationale is documented in
[`docs/methodology.md`](docs/methodology.md) and the model itself is machine-readable in
[`scoring.yaml`](scoring.yaml). This document covers installation and operation; see
[`docs/running_guide.md`](docs/running_guide.md) for Postgres/Neon configuration, monitoring and
troubleshooting.

```
┌──────────┐   POST /score    ┌─────────────────────────┐   SSE progress   ┌──────────┐
│ frontend │ ───────────────► │ backend (FastAPI)       │ ───────────────► │ scorecard│
│  :5173   │ ◄─────────────── │ collectors, scoring,    │ ◄─────────────── │  renders │
└──────────┘   /api proxy     │ append-only evidence db │   full record    └──────────┘
                              └─────────────────────────┘
```

## Prerequisites

- **Python ≥ 3.11**
- **Node ≥ 18** and npm (verified against Node 26)
- No paid credentials required. Core sources are unauthenticated; several optional collectors
  (ABN Lookup, Companies House, OTX) use free API keys and are skipped cleanly when unset.
- **Postgres** — set `DATABASE_URL` (any Postgres instance; a Neon connection string is
  sufficient). There is no local-file fallback.

---

## 1. Backend (FastAPI API)

```bash
cd backend

python -m venv .venv
# Windows (Git Bash):   source .venv/Scripts/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # optional: contact User-Agent, API keys

uvicorn app.api:app --port 8000 --reload
```

The service listens on `127.0.0.1:8000`, with OpenAPI documentation at `/docs`.

**Storage: Postgres only.** Set `DATABASE_URL` (a Neon connection string, or any Postgres) — the
application fails at startup without it. There is no local-file fallback: the append-only,
hash-stamped evidence store is the legal artefact the score is published from (Finding A), and a
weaker persistence guarantee is not a substitute for it.

### API surface

The examples below assume `API=http://127.0.0.1:8000`; substitute the deployed origin as
appropriate.

```bash
# submit a vendor for scoring — returns a job id and an SSE stream URL
curl -s -X POST "$API/api/vendors/score" \
     -H 'Content-Type: application/json' -d '{"domain":"atlassian.com"}'

# stream collector progress for a running job
curl -N "$API/api/jobs/<job_id>/stream"

# retrieve the completed record (risk, confidence, quadrant, categories)
curl -s "$API/api/vendors/atlassian" | python -m json.tool

# retrieve the hash-stamped evidence receipts behind each finding
curl -s "$API/api/vendors/atlassian/evidence"

# vendor identity — industry, size, country, ownership, and assigned peer cohort
curl -s "$API/api/vendors/atlassian/profile" | python -m json.tool

# peer comparison, or the stated reason no comparison is published
curl -s "$API/api/vendors/atlassian/benchmark" | python -m json.tool

# comparison is cohort-bounded: mismatched vendors return 409 naming both cohorts
curl -s -X POST "$API/api/compare" \
     -H 'Content-Type: application/json' -d '{"refs":["atlassian","snowflake"]}'
```

Scoring can also be driven directly, without the service:

```bash
python -m app.harness --domain atlassian.com --ref atlassian --name Atlassian   # all collectors
python -m app.harness --domain atlassian.com --ref atlassian --only dns          # one collector
```

---

## 2. Frontend (streaming scorecard)

With the API running, in a separate shell:

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

Vite proxies `/api` to the backend origin, keeping the two same-origin as SSE requires. The
interface accepts a vendor name (`Atlassian`) or domain (`snowflake.com`) and renders the scorecard
as results stream in. See [`frontend/README.md`](frontend/README.md) for the designed states.

### Optional: AI evidence summary

An optional read-layer LLM digest of a completed record. It is **disabled by default** and
provider-agnostic, targeting any OpenAI-compatible `chat/completions` endpoint. Setting the three
variables below enables the **Summarise evidence** action on the scorecard:

```bash
# in backend/.env — configure a single provider (see .env.example for alternatives)
TPRM_LLM_BASE_URL=https://openrouter.ai/api/v1
TPRM_LLM_API_KEY=sk-...
TPRM_LLM_MODEL=google/gemini-2.0-flash-001
```

The constraints are structural. The summary **never computes or alters a score** and **never
writes to the evidence store**: it reads the published score and the hash-stamped receipt index, is
returned marked *AI-generated*, and cites the hashes it was derived from. **Raw collector payloads
are never transmitted to the model** — only score roll-ups and receipt metadata leave the system,
which is the single documented egress point (see [`docs/methodology.md`](docs/methodology.md)
Part 3, *Data egress*). Absent the credentials, `POST /api/vendors/{ref}/summary` returns **503**
and the action is not surfaced.

---

## 3. Tests and linting

```bash
# backend (from backend/, with the virtualenv active)
pytest -q                       # 1,332 passed, 2 xfailed
ruff check app tests            # lint

# frontend (from frontend/)
npm run lint
npm run build
```

> The suite requires `DATABASE_URL` (the same Postgres instance the application uses). Each test
> that touches the store runs in a disposable schema (`tprm_test_<uuid>`), created on entry and
> dropped in full afterwards, so the suite never reads from or writes to the `public` schema. The
> pure-logic tests (scoring, benchmarking, normalisation) run offline and require no database.

---

## Reference vendor set

`Atlassian` · `Snowflake` · `MYOB` · `OneTrust` · `Slack` — production TPRM targets spanning
listed and private ownership, software-shipping and pure-SaaS delivery, and single-register versus
corroborated identity. `Xero` exercises the sanctions gate: it is correctly blocked and routed to
human adjudication.

## Operational characteristics

- **Entity resolution does not guess.** Most collectors are domain-specific, so a bare name
  (`Atlassian`) is not scored automatically: the service returns candidate domains for
  confirmation and proceeds only once one is selected. Inferring `<slug>.com` and scoring it
  silently would risk assessing the wrong company. Supplying a domain scores directly.
- **Low-confidence results are the norm, and are reported as such.** A result banded
  low-confidence and labelled *The Ghost* means **unassessed**, not **safe** — an intended
  property of the model, not a defect.
- **`digital_footprint` depends on Certificate Transparency** (crt.sh, with a Cert Spotter
  fallback). crt.sh availability is inconsistent and the anonymous Cert Spotter tier is
  rate-limited. During a CT outage the category returns zero and a clean vendor may band as
  *The Ghost* — an honest and recoverable outcome. `TPRM_CERTSPOTTER_TOKEN` raises the CT limit;
  `TPRM_OTX_API_KEY` adds passive-DNS redundancy that carries the category when CT is unavailable.
- **Several sources require an identifying User-Agent.** Wikidata and HIBP expect a descriptive,
  contact-bearing `User-Agent`. The `.env.example` default is sufficient for evaluation; supply a
  real contact address for any deployment.
- **The sanctions gate terminates in human adjudication.** A watchlist match blocks the assessment
  and emits no score by design (Autonomous Sanctions Act s 16(7) — the adjudication record is the
  evidence).

---

## Peer benchmarking

A given posture carries different implications across industries, so the scorecard interprets it
against a **peer cohort defined on four factors — industry × revenue × headcount × region**. **This
changes no arithmetic:** identical findings produce an identical posture regardless of sector; only
the interpretation differs. The model file is unmodified and the frozen regression corpus continues
to pass.

**Revenue and headcount are treated as separate dimensions rather than a single blended size.**
They frequently disagree, and the disagreement carries information: a 40-person firm turning over
$400M presents concentrated transactional leverage, whereas a 4,000-person firm at equivalent
revenue presents a substantially larger attack surface.

**Cohort widening is what makes four factors tractable.** 12 sectors × 5 revenue bands × 5 headcount
bands × 5 regions yields **1,500 possible cohorts**, and exact matches rarely populate — a 114-vendor
run produced two populated cohorts, the largest containing four members. Where the exact cohort is
too thin, the system widens in a fixed order — dropping region, then revenue, then headcount — and
discloses the substitution on the card: *"wider peer group used: industry + headcount + region"*.
Widening never proceeds past industry; there is deliberately no rung that compares a vendor against
the entire scored population.

**Refusal to compare is a designed behaviour.** Where no rung reaches `cohort.min_cohort_n` peers
(default **8**, configured in [`benchmarks.yaml`](benchmarks.yaml)), the card reports *"insufficient
peers (4 of 8) at every cohort width"* in place of a percentile. Comparison is cohort-bounded at the
API: `POST /api/compare` across vendors from different cohorts returns **409** naming both.

**Statistical claims are bounded to what the sample supports.** Percentiles are rounded to the step
the sample can express, and that step is published (`50 ±25` at n=4); a quartile is reported
alongside, as it remains stable when a single peer joins or leaves. Stale and thinly-evidenced peers
are excluded, and the exclusion is disclosed. Every benchmark carries the standing caveat that peers
are the vendors this deployment has scored — a convenience sample, not an industry norm.
Per-category variance is also reported, since *"breach history is 30 points below peers"* is
actionable where a single aggregate figure is not.

`benchmarks.yaml` ships with **no sector targets**, deliberately. No authoritative source publishes
them, and asserting that *"financial services should score 95"* carries the same defect as the
category weights removed in §5.6. An `expected_posture` entry loads only with a `basis:` field
naming a real source.

```bash
# cohorts require a population; seed one by scoring real vendors (global, 10 sectors)
python -m app.seed_cohorts --list                    # preview the target set
python -m app.seed_cohorts --sector technology       # seed a single sector
python -m app.seed_cohorts --status                  # cohort depth against the gate
```

**Two optional client-supplied inputs** are recorded as client-supplied and neither is scored:
`criticality` (the buyer's own dependency on the vendor, not externally observable) and `size_band`
(public sources publish an industry for most vendors but a headcount for considerably fewer, and a
sector without a size cannot form a cohort).

## Layout

```
scoring.yaml        the model (the deliverable) — bands, penalties, gates, confidence
benchmarks.yaml     peer cohorts, size bands, the minimum-peers gate — interpretation, no arithmetic
backend/            FastAPI API, collectors, scoring engine, append-only evidence store
frontend/           React + Vite single-screen streaming scorecard
docs/               five documents — methodology, the model, design decisions (see below)
ops/                scheduled monitoring (cron / systemd / Windows Task Scheduler)
```

## Documentation

**Start here:** [`methodology.md`](docs/methodology.md) — the research and rationale; the document the
model is derived from. Then [`system_retrospective.md`](docs/system_retrospective.md) for current,
verified status.

Five documents. Each is split into parts; the part is the citable unit.

| Document | Part | What it covers |
|---|---|---|
| [`methodology.md`](docs/methodology.md) | **1 · Research methodology** | **The product.** Full derivation of the model and what OSINT can and cannot reach |
| | **2 · Legal & standards basis** | Model-level legal basis — *once collected, does the score stand up?* |
| | **3 · Source assessment** | Per-source signals, reliability, limits and legal/ToS position — *may we lawfully collect this?* |
| [`scoring_model.md`](docs/scoring_model.md) | **1 · The model in brief** | The guided summary of `scoring.yaml` — severity ladder, grades, roll-up, the three axes |
| | **2 · Metrics reference** | Every published metric and the arithmetic implemented, each constant read from code |
| | **3 · Vendor age differentiation** | How age is used — and why it never touches cybersecurity posture |
| [`design_decisions.md`](docs/design_decisions.md) | **1 · Peer benchmarking** | Cohort scoping, placement thresholds, the refusal-to-compare gate |
| | **2 · Financial data integration** | Collector chains, API surface, schema, the Business Stability axis |
| | **3 · Vendor comparison scenarios** | Nine acceptance scenarios in plain English, executable as a test file |
| [`system_retrospective.md`](docs/system_retrospective.md) | — | What was built, what was rejected, and the defects found and fixed along the way |
| [`running_guide.md`](docs/running_guide.md) | — | Postgres/Neon specifics, monitoring and troubleshooting — the long form of this README |

## License

[MIT](LICENSE)
