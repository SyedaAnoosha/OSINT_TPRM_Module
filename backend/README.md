# WahidAI TPRM — backend

Proof-of-concept backend for **OSINT for Third-Party Risk**. Vendor in → evidence-linked
risk record out. The methodology is the product; this code demonstrates it. See
`../docs/methodology.md` (the model) and `../docs/system_retrospective.md` (current, verified status).

## Status

FastAPI service — collectors, scoring engine, benchmarking, business-stability/financial-risk
assessment, and an append-only evidence store, all sitting behind an SSE-streamed scoring job.
For the current collector count, test count and scoring-model version, see
[`../docs/system_retrospective.md`](../docs/system_retrospective.md) — the numbers here rot; that
document is re-verified against the running tree each time it's updated. The React streaming
scorecard is in `../frontend`.

> **How to run the whole app (backend + frontend):** see the root [`../README.md`](../README.md).

The evidence store and the shared contracts exist before any collector, on purpose —
the store is the legal artefact that discharges the "reasonable grounds" representation
(methodology Finding A), so it is built first.

### Collectors

Source collectors live in `app/collectors/` — DNS/TLS/headers, certificate transparency, breach
history (HIBP), vulnerability feeds (KEV/NVD), sanctions (ITA), entity registers (GLEIF, Wikidata,
OpenCorporates, regional company registries), regulatory/insolvency filings (SEC EDGAR/XBRL, EU/UK/
Canada/Germany insolvency registers), and adverse media (GDELT). Each returns the same
`CollectorResult` envelope; see [`../docs/methodology.md`](../docs/methodology.md) §4 and
[`../docs/source_assessment.md`](../docs/source_assessment.md) for the per-source legality and
reliability register.

Every collector returns the same `CollectorResult` envelope and is **failure-isolated**
(a raise → `error`, a hang → `timeout`, nothing-found → `empty`), so one dead source
can't sink an assessment. Run one or all via the harness:

```bash
python -m app.harness --domain atlassian.com --ref atlassian --name Atlassian          # all
python -m app.harness --domain atlassian.com --ref atlassian --only dns                 # one
```

Notable per-collector behaviour proven live:
- **`dns`** — DMARC ladder (absent → p=none → p=quarantine → p=reject); DKIM absence is
  *inconclusive* (selector unknowable) so it never penalises, only lowers coverage.
- **`tls`/`headers`** — our own handshake + one GET; the deliberate SSL Labs replacement.
- **`kev`/`nvd`** — product-scoped: software-shipping vendors (Atlassian) return findings;
  others return a clean receipt, which lowers *confidence*, not *risk* (the MYOB principle).
- **`gleif`/`wikidata`** — entity standing from two independent CC0 registers; Wikidata resolves
  by **domain** (official-website match) and only corroborates on a match, never a wrong guess.
- **`ita`** — the sanctions gate feed; keyless CSL download cached daily; a **clean screen
  is retained** as the s16(7) defence record, not discarded.
- **`trust`** — honours robots.txt; strips named-person emails at ingest (PII minimisation).

External services are flaky by nature: crt.sh (`ct`) frequently 502s/times out and GDELT
429s under rapid calls — both are isolated as `error`, never crashes.

| Piece | File | What it guarantees |
|---|---|---|
| Shared contracts | `app/models.py` | One schema for evidence store + API; provenance is explicit |
| Evidence store | `app/pg_store.py` (`PostgresStore`) | **Append-only, immutable** (DB triggers reject UPDATE/DELETE), **byte-identical** read-back (canonical JSON + sha256) |
| Settings | `app/config.py` | Contact-bearing `User-Agent` + optional free API keys (NVD/ITA/CertSpotter); **required** `DATABASE_URL` (Postgres only) |
| Scoring config | `app/scoring_config.py` | Loads the root `scoring.yaml`; enforces invariants (weights=100, sanctions=gate, direction not inverted) |
| Rate limiting | `app/ratelimit.py` | Per-host token buckets — `asyncio.gather` does not throttle a source for you |
| Logging | `app/logging_config.py` | One place for log format |

**Phase 0 exit criterion — met:** an evidence row is written and read back byte-identical
(`tests/test_evidence_store.py::test_write_then_read_back_byte_identical`).

## Setup

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Git Bash:            source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env        # optional — the app runs with defaults

uvicorn app.api:app --port 8000 --reload   # API at http://127.0.0.1:8000  (/docs for the UI)
```

`DATABASE_URL` is **required** (Postgres only — no local-file fallback). Other settings are optional
(anonymous source tiers, a working default UA).
For a real deployment set a contact-bearing `TPRM_USER_AGENT` (Wikidata/HIBP ask for one) and,
if you hit CT rate limits, a free `TPRM_CERTSPOTTER_TOKEN`. Full run guide: [`../README.md`](../README.md).

## Test & lint

```bash
pytest -q            # needs DATABASE_URL; store tests run in a disposable per-test schema
ruff check app tests # clean
```

## Design rules the code enforces (not just documents)

- **Evidence before scoring.** `EvidenceStore.put()` is called before any normalization.
- **`empty` is first-class.** A source returning nothing is stored and later reduces
  *confidence*, never *risk* (methodology §5.4). A collector must not raise on "nothing found".
- **`fetched_at` is timezone-aware and mandatory**, and `source_version` is retained —
  a screen must be reconstructable "as it stood at the time" (Finding B).
- **Sanctions is a gate, never a weight** — validated in `scoring_config.py`.
```
