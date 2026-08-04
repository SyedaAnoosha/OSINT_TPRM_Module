"""Postgres-backed store — the Neon deployment's data layer.

Satisfies the `storage.Store` protocol method-for-method (duck-typed), so the pipeline and
API use whichever the factory returns without caring which. The two guarantees that make
the evidence store a legal artefact (Finding A) are preserved Postgres-side:

  * **Append-only.** plpgsql BEFORE UPDATE/DELETE triggers RAISE EXCEPTION on both the
    `evidence` and `scores` tables — a future bug cannot rewrite history at the DB level,
    exactly as the SQLite triggers do.
  * **Byte-identical.** Uses the SAME canonical-JSON + sha256 helpers as the SQLite store,
    so a given CollectorResult produces an identical `content_hash` in either backend —
    stored evidence is portable and its hash is reproducible on any machine.

Connection is sync psycopg3 with autocommit (one statement per transaction — friendly to
Neon's PgBouncer pooler). Async callers wrap store calls in `asyncio.to_thread` so a
round-trip to Neon never blocks the event loop.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row

from .canonical import canonical_json as _canonical_json
from .canonical import finding_payload as _finding_payload
from .canonical import payload_of as _payload_of
from .canonical import sha256 as _sha256
from .models import (
    BenchmarkSnapshot,
    CollectorResult,
    Decision,
    Dispute,
    Evidence,
    GapAnalysisRecommendationEvent,
    GapAnalysisRecord,
    PersistedFinding,
    Score,
    VendorProfile,
    utcnow,
)

if TYPE_CHECKING:
    from .scoring.normalize import NormalizedFinding

# Cohort peers on ANY SUBSET of the four dimensions — the widening ladder's one query. Window
# functions pick each vendor's CURRENT profile and CURRENT score, so a re-scored vendor contributes
# one data point rather than one per run. The caller appends the dimension WHERE clauses and
# ORDER BY. Mirrors EvidenceStore.cohort_peers exactly, because a benchmark that differs between the
# two backends is a benchmark nobody can trust.
_COHORT_PEERS_SQL = """
WITH current_profile AS (
    SELECT vendor_ref, cohort_key, sector, revenue_band, employee_band, region,
           ROW_NUMBER() OVER (PARTITION BY vendor_ref ORDER BY computed_at DESC) AS rn
    FROM vendor_profiles WHERE cohort_key IS NOT NULL
),
current_score AS (
    SELECT vendor_ref, posture, blocked, refused, overall_confidence, computed_at, score_json,
           ROW_NUMBER() OVER (PARTITION BY vendor_ref ORDER BY computed_at DESC) AS rn
    FROM scores
)
SELECT p.vendor_ref, s.posture, s.overall_confidence, s.computed_at, s.score_json
FROM current_profile p
JOIN current_score s ON s.vendor_ref = p.vendor_ref AND s.rn = 1
WHERE p.rn = 1
  AND s.posture IS NOT NULL AND s.blocked = false AND s.refused = false
"""

# `(vendor_ref, signal, band)` for every peer's current run — the input to signal prevalence.
_COHORT_SIGNALS_SQL = """
WITH current_profile AS (
    SELECT vendor_ref, sector, revenue_band, employee_band, region,
           ROW_NUMBER() OVER (PARTITION BY vendor_ref ORDER BY computed_at DESC) AS rn
    FROM vendor_profiles WHERE cohort_key IS NOT NULL
),
latest_run AS (
    SELECT DISTINCT ON (vendor_ref) vendor_ref, run_id
    FROM findings ORDER BY vendor_ref, stored_at DESC
),
current_findings AS (
    SELECT DISTINCT f.vendor_ref, f.signal, f.band_key
    FROM findings f
    JOIN latest_run lr ON lr.vendor_ref = f.vendor_ref
       AND f.run_id IS NOT DISTINCT FROM lr.run_id
)
SELECT cf.vendor_ref, cf.signal, cf.band_key
FROM current_profile p
JOIN current_findings cf ON cf.vendor_ref = p.vendor_ref
WHERE p.rn = 1
"""

# Benchmarking v2 peers, on any subset of {sector, sector_group, bm_size_band, delivery_model}. Same
# window-function discipline as the v1 query above — each supplier's CURRENT profile and CURRENT
# score, so a re-scored supplier contributes ONE point to the distribution rather than one per run.
# Getting that wrong would let a frequently-rescored supplier dominate its own cohort's median.
#
# `sector_group` is resolved in Python and passed as a sector list, because the mapping is a published
# config rollup rather than a stored column — keeping it out of the schema means a group can be
# re-cut in YAML without a migration.
_BM_COHORT_PEERS_SQL = """
WITH current_attrs AS (
    SELECT supplier_ref, sector, size_band, delivery_model,
           ROW_NUMBER() OVER (PARTITION BY supplier_ref ORDER BY created_at DESC) AS rn
    FROM supplier_attributes
),
current_score AS (
    SELECT vendor_ref, posture, blocked, refused, overall_confidence, computed_at, score_json,
           ROW_NUMBER() OVER (PARTITION BY vendor_ref ORDER BY computed_at DESC) AS rn
    FROM scores
)
SELECT p.supplier_ref AS vendor_ref, s.posture, s.overall_confidence, s.computed_at, s.score_json
FROM current_attrs p
JOIN current_score s ON s.vendor_ref = p.supplier_ref AND s.rn = 1
WHERE p.rn = 1
  AND s.posture IS NOT NULL AND s.blocked = false AND s.refused = false
"""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    id             TEXT PRIMARY KEY,
    vendor_ref     TEXT NOT NULL,
    source         TEXT NOT NULL,
    status         TEXT NOT NULL,
    fetched_at     TIMESTAMPTZ NOT NULL,
    source_version TEXT,
    payload_json   TEXT NOT NULL,
    reliability    DOUBLE PRECISION NOT NULL,
    notes          TEXT,
    content_hash   TEXT NOT NULL,
    stored_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_vendor ON evidence(vendor_ref);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(vendor_ref, source);

CREATE TABLE IF NOT EXISTS scores (
    id                 TEXT PRIMARY KEY,
    vendor_ref         TEXT NOT NULL,
    computed_at        TIMESTAMPTZ NOT NULL,
    blocked            BOOLEAN NOT NULL,
    refused            BOOLEAN NOT NULL,
    posture            INTEGER,
    grade              TEXT,
    overall_confidence DOUBLE PRECISION NOT NULL,
    confidence_band    TEXT,
    critical_ceiling_applied BOOLEAN NOT NULL,
    score_json         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scores_vendor ON scores(vendor_ref, computed_at);

-- Migrate a PRE-v4 scores table (old risk model) to the posture model, idempotently. No-op on
-- a freshly-created table; on an existing one it adds the new columns and drops the obsolete
-- risk columns. Old rows keep their score_json (read back with a null posture — harmless).
ALTER TABLE scores ADD COLUMN IF NOT EXISTS posture INTEGER;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS grade TEXT;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS confidence_band TEXT;
ALTER TABLE scores ADD COLUMN IF NOT EXISTS critical_ceiling_applied BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE scores DROP COLUMN IF EXISTS overall_risk;
ALTER TABLE scores DROP COLUMN IF EXISTS quadrant;
ALTER TABLE scores DROP COLUMN IF EXISTS knockout_applied;

-- Signal-level findings: interpreted evidence (observation -> severity -> penalty), append-only
-- and hash-stamped like evidence, linked to the raw Evidence via `evidence_id`.
CREATE TABLE IF NOT EXISTS findings (
    id            TEXT PRIMARY KEY,
    vendor_ref    TEXT NOT NULL,
    evidence_id   TEXT,
    source        TEXT NOT NULL,
    category      TEXT NOT NULL,
    signal        TEXT NOT NULL,
    band_key      TEXT NOT NULL,
    severity      TEXT,
    penalty       DOUBLE PRECISION NOT NULL,
    observed      TEXT NOT NULL,
    event_date    TIMESTAMPTZ,
    is_critical   BOOLEAN NOT NULL,
    is_sanctions  BOOLEAN NOT NULL,
    note          TEXT,
    content_hash  TEXT NOT NULL,
    stored_at     TIMESTAMPTZ NOT NULL
);
-- What was ACTUALLY charged after the NIST modifiers, and how many times the signal fired.
-- `penalty` alone cannot reproduce the score: a 4-year-old breach stores its -40 base against a
-- category that only lost -16.
ALTER TABLE findings ADD COLUMN IF NOT EXISTS effective_penalty DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE findings ADD COLUMN IF NOT EXISTS occurrences INTEGER NOT NULL DEFAULT 1;
-- Which scoring run produced the row. Findings are append-only, so without it "the findings for
-- this vendor" means every run ever stacked together.
ALTER TABLE findings ADD COLUMN IF NOT EXISTS run_id TEXT;
-- 'nullified' | 'mitigated' when an accepted refute changed this deduction (Phase 4). Recorded on
-- the finding so a discounted penalty says WHY it was discounted.
ALTER TABLE findings ADD COLUMN IF NOT EXISTS dispute TEXT;
CREATE INDEX IF NOT EXISTS idx_findings_vendor ON findings(vendor_ref);

-- Disputes: the vendor-refute path (Phase 4). Append-only EVENTS — a dispute moves from
-- `submitted` to `accepted`/`rejected` by APPENDING a new event, never editing a row, so who
-- submitted what and who decided is frozen and auditable. Current state of a dispute = its latest
-- event. Keyed to a specific (signal, band_key), so an accepted refute self-expires when the next
-- scan shows a different observation.
CREATE TABLE IF NOT EXISTS disputes (
    id           TEXT PRIMARY KEY,
    dispute_id   TEXT NOT NULL,
    vendor_ref   TEXT NOT NULL,
    event        TEXT NOT NULL,
    signal       TEXT NOT NULL,
    band_key     TEXT NOT NULL,
    kind         TEXT NOT NULL,
    evidence     TEXT NOT NULL,
    actor        TEXT,
    note         TEXT,
    content_hash TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_disputes_vendor ON disputes(vendor_ref, created_at);
CREATE INDEX IF NOT EXISTS idx_disputes_group ON disputes(dispute_id, created_at);

-- Procurement / executive DECISIONS. A decision is a buyer action, not a score: approve /
-- conditional / reject, recorded ALONGSIDE the immutable score, never inside it. Append-only and
-- stamped with the posture+grade AS AT the moment of the decision, so "we approved this vendor" is
-- reconstructible against the exact number that was on the card when the call was made — a later
-- re-score cannot retroactively make a past approval look better- or worse-founded than it was.
CREATE TABLE IF NOT EXISTS decisions (
    id           TEXT PRIMARY KEY,
    vendor_ref   TEXT NOT NULL,
    decision     TEXT NOT NULL,      -- approve | conditional | reject
    conditions   TEXT,               -- required when decision = conditional
    actor        TEXT,               -- who recorded it (role/name), client-supplied
    posture_at   INTEGER,            -- the posture on the card at decision time
    grade_at     TEXT,
    content_hash TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_vendor ON decisions(vendor_ref, created_at);

-- Benchmark snapshots: where a vendor stood among its peers AS AT one score run. Append-only, so a
-- percentile trend ("bottom quartile three quarters running") is read from points that were each
-- frozen when true — never a today's-cohort percentile pinned onto an old posture. Context beside
-- the score, never an input to it. available=false (thin/absent cohort) is a recorded value.
CREATE TABLE IF NOT EXISTS benchmark_snapshots (
    id                    TEXT PRIMARY KEY,
    vendor_ref            TEXT NOT NULL,
    cohort_key            TEXT,
    level                 TEXT,
    available             BOOLEAN NOT NULL DEFAULT FALSE,
    percentile            INTEGER,
    percentile_resolution INTEGER,
    quartile              INTEGER,
    peer_n                INTEGER NOT NULL DEFAULT 0,
    posture               INTEGER,
    content_hash          TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bmsnap_vendor ON benchmark_snapshots(vendor_ref, created_at);

-- Vendor profiles: WHO the vendor is, and the peer cohort that follows. Append-only for the same
-- reason scores are: a benchmark published last quarter was computed against the cohort the vendor
-- was in THEN, and an amended profile would silently re-write which population an old comparison
-- was made against (Finding B).
CREATE TABLE IF NOT EXISTS vendor_profiles (
    id            TEXT PRIMARY KEY,
    vendor_ref    TEXT NOT NULL,
    cohort_key    TEXT,
    sector        TEXT,
    size_band     TEXT,          -- legacy single band; superseded by the two below
    revenue_band  TEXT,
    employee_band TEXT,
    region        TEXT,
    criticality   TEXT,
    completeness  DOUBLE PRECISION NOT NULL DEFAULT 0,
    profile_json  TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL,
    stored_at     TIMESTAMPTZ NOT NULL
);
-- Split the legacy single `size_band` into separate revenue and headcount dimensions, idempotently.
-- Additive: rows written before the split keep `size_band` and get NULLs here, which is honest —
-- that run genuinely did not distinguish the two. They stop matching the size-aware rungs of the
-- widening ladder and still match on industry and region. Profiles are append-only, so re-scoring
-- a vendor writes a current, fully-populated row.
ALTER TABLE vendor_profiles ADD COLUMN IF NOT EXISTS revenue_band TEXT;
ALTER TABLE vendor_profiles ADD COLUMN IF NOT EXISTS employee_band TEXT;
CREATE INDEX IF NOT EXISTS idx_profiles_vendor ON vendor_profiles(vendor_ref, computed_at);
CREATE INDEX IF NOT EXISTS idx_profiles_cohort ON vendor_profiles(cohort_key);
CREATE INDEX IF NOT EXISTS idx_profiles_dims
    ON vendor_profiles(sector, employee_band, revenue_band, region);

-- ===========================================================================
-- BENCHMARKING v2 — the enterprise peer-comparison layer.
-- See docs/benchmarking-design.md. Additive throughout: the v1 columns and tables above are
-- untouched, so stored v1 snapshots keep deserialising through the deprecation release.
-- ===========================================================================

-- Supplier attributes: the RAW INPUTS the v2 cohort is derived from. Its own table rather than extra
-- columns on `vendor_profiles` for two reasons:
--
--   1. `VendorProfile.profile_json` is the v1 model and cannot round-trip these fields, so a value
--      written into a bolted-on column could not be recovered by a rebuild reading profile_json —
--      which would break the "cohorts are rebuildable from raw data" guarantee outright.
--   2. The v2 size vocabulary DIFFERS from v1 (mid/enterprise vs medium/mega). Sharing one column
--      would mix two schemes in one index, and a `medium` row would then match neither.
--
-- Append-only, like every other table here: an upheld dispute appends a corrected row, and the
-- rebuild that follows reads the latest. That is why the design forbids manual DB overrides — the
-- correction has to be an INPUT so the derivation can be re-run over it.
--
-- `data_access_scope` is stored here but is NOT a cohort dimension: it is a property of the
-- relationship, and the cohort query below deliberately never references it. Decision 1.
CREATE TABLE IF NOT EXISTS supplier_attributes (
    id                TEXT PRIMARY KEY,
    supplier_ref      TEXT NOT NULL,
    sector            TEXT,
    size_band         TEXT,            -- v2 vocabulary: micro|small|mid|large|enterprise
    delivery_model    TEXT,            -- saas|on_prem|managed
    data_access_scope TEXT,            -- low|medium|high|critical — interpretation only
    employees         INTEGER,
    revenue           DOUBLE PRECISION,
    revenue_currency  TEXT,
    size_band_basis   TEXT,            -- the derivation, in words, for the dispute path
    source            TEXT,            -- derived | client_supplied | dispute_upheld
    content_hash      TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_supplier_attrs_ref
    ON supplier_attributes(supplier_ref, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_supplier_attrs_dims
    ON supplier_attributes(sector, size_band, delivery_model);

-- Cohort snapshots: the frozen population a placement stays reproducible against. Append-only — a
-- rebuild mints a NEW row. That is what makes "why did my quartile change?" answerable: diff two
-- snapshots and the movement decomposes into "the supplier moved" and "the cohort moved".
--
-- `snapshot_json` carries member refs and the sorted peer values. Those are INTERNAL: the API serves
-- `CohortSnapshot.public()`, which structurally cannot hold them. Decision 4.
CREATE TABLE IF NOT EXISTS cohort_snapshots (
    id             TEXT PRIMARY KEY,
    cohort_key     TEXT NOT NULL,
    rung_label     TEXT,
    peer_n         INTEGER NOT NULL DEFAULT 0,
    median         INTEGER,
    is_synthetic   BOOLEAN NOT NULL DEFAULT FALSE,
    member_hash    TEXT NOT NULL,
    snapshot_json  TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    last_refreshed TIMESTAMPTZ NOT NULL,
    stored_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cohort_snap_key ON cohort_snapshots(cohort_key, last_refreshed DESC);
CREATE INDEX IF NOT EXISTS idx_cohort_snap_hash ON cohort_snapshots(member_hash);

-- Benchmark placements: where ONE supplier stood against ONE snapshot. Append-only, and carrying
-- `snapshot_id` rather than recomputing — a placement re-derived against today's cohort would
-- attribute the cohort's movement to the supplier.
--
-- Deliberately NOT storing quartile/percentile as the source of truth for the card: they are stored
-- for trend queries, and `placement_json` holds the full artefact including the reason a threshold
-- refused. A trend of quartiles with no record of WHY one was withheld reads as a gap in the data.
CREATE TABLE IF NOT EXISTS benchmark_placements (
    id               TEXT PRIMARY KEY,
    supplier_ref     TEXT NOT NULL,
    snapshot_id      TEXT NOT NULL,
    cohort_key       TEXT NOT NULL,
    posture          INTEGER,
    peer_n           INTEGER NOT NULL DEFAULT 0,
    sufficient       BOOLEAN NOT NULL DEFAULT FALSE,
    quartile         INTEGER,
    percentile       INTEGER,
    rank_of_n        INTEGER,
    bucket           TEXT,
    reliability      DOUBLE PRECISION,
    disputed         BOOLEAN NOT NULL DEFAULT FALSE,
    placement_json   TEXT NOT NULL,
    content_hash     TEXT NOT NULL,
    assessed_at      TIMESTAMPTZ NOT NULL,
    stored_at        TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bm_place_supplier
    ON benchmark_placements(supplier_ref, assessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_bm_place_snapshot ON benchmark_placements(snapshot_id);

-- Cohort disputes: append-only EVENTS, same shape as `disputes` above and for the same reason —
-- a dispute is not edited from `submitted` to `upheld`, a new event is appended, so who asserted
-- what and who decided is frozen.
--
-- WHAT IS DISPUTABLE IS THE INPUT: sector, size_band and its two raw values, delivery_model. Never
-- the cohort, the snapshot, or the resulting cell — a cell is a deterministic lookup over disputable
-- inputs and carries no independent judgement to contest.
--
-- AN UPHELD DISPUTE IS NOT AN UPDATE HERE. Cohorts are rebuildable from raw data by definition, so
-- the resolution changes the supplier ATTRIBUTE, a rebuild mints a new snapshot, and a new placement
-- follows. Historical placements keep pointing at the snapshot they were computed against.
CREATE TABLE IF NOT EXISTS cohort_disputes (
    id             TEXT PRIMARY KEY,
    dispute_id     TEXT NOT NULL,
    supplier_ref   TEXT NOT NULL,
    state          TEXT NOT NULL,
    target         TEXT NOT NULL,
    asserted_value TEXT,
    observed_value TEXT,
    cohort_key_at  TEXT,
    snapshot_id_at TEXT,
    evidence       TEXT NOT NULL,
    actor          TEXT,
    note           TEXT,
    content_hash   TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cohort_disp_supplier
    ON cohort_disputes(supplier_ref, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cohort_disp_group ON cohort_disputes(dispute_id, created_at);

-- EVIDENCE THAT THE SCHEDULE FIRED, which is a different fact from the schedule existing.
--
-- `app/monitor.py` is the unit of work and `app/scheduler.py` is what an OS timer invokes. Neither
-- can answer "has monitoring actually been happening", and that question is the one that separates
-- a Defined monitoring practice from a cron entry somebody added and nobody watched. The classic
-- failure of a scheduled job is not that it errors — it is that it silently stops, and every
-- downstream number keeps rendering as though it had not.
--
-- AN EVENT LOG, NOT A STATUS ROW, and for the same reason `disputes` is one: a run is not edited
-- from `started` to `finished`, a second row is appended. That keeps the table append-only like
-- every other table here, and — the operational point — a run that DIED leaves its `started` row
-- with no `finished` partner, which is precisely the state a status column would have overwritten
-- on the next successful run and hidden forever.
--
-- One event per INVOCATION, not per vendor: what was considered, what was actually re-scored, what
-- drifted, what failed, and how long it took.
CREATE TABLE IF NOT EXISTS monitor_runs (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,   -- groups the started/finished pair
    event           TEXT NOT NULL,   -- started | finished | failed
    trigger         TEXT NOT NULL,   -- scheduled | manual | dry_run
    mode            TEXT NOT NULL,   -- by_tier | stale_days
    considered      INTEGER NOT NULL DEFAULT 0,
    rescored        INTEGER NOT NULL DEFAULT 0,
    drifted         INTEGER NOT NULL DEFAULT 0,
    failed          INTEGER NOT NULL DEFAULT 0,
    duration_secs   DOUBLE PRECISION,
    error           TEXT,
    detail_json     TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitor_runs_time ON monitor_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_monitor_runs_group ON monitor_runs(run_id, created_at);

-- E14 — one generated gap analysis (a third audience view whose renderer is a model, over a
-- finished record it never adjusts). Append-only, same reasoning as `benchmark_snapshots`: a past
-- analysis is a claim about what the model said against a SPECIFIC finished record, and a later
-- rescore or re-generation must never rewrite it — a fresh analysis is a NEW row.
--
-- `gaps_json` / `recommendations_json` are the LLM's disposable prose, stored as JSON text rather
-- than typed further — they are regenerable and belong nowhere near the hash-stamped `findings`
-- shape that IS the legal artefact. `limitations_json` is the coverage statement COPIED at
-- generation time, never the model's own words — see app/gap_analysis.py.
CREATE TABLE IF NOT EXISTS gap_analyses (
    id                    TEXT PRIMARY KEY,
    vendor_ref            TEXT NOT NULL,
    provider              TEXT NOT NULL,
    model                 TEXT NOT NULL,
    prompt_version        TEXT NOT NULL,
    context_hash          TEXT NOT NULL,
    executive_summary     TEXT NOT NULL,
    gaps_json             TEXT NOT NULL,
    recommendations_json  TEXT NOT NULL,
    limitations_json      TEXT NOT NULL,
    dropped_evidence_ids  INTEGER NOT NULL DEFAULT 0,
    content_hash          TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gap_analyses_vendor ON gap_analyses(vendor_ref, created_at DESC);

-- One event in an analyst's accept / edit / reject of ONE recommendation on ONE analysis.
-- Append-only for the same reason `disputes` is: a rejection is a fact worth keeping ("a model
-- proposed this, a person declined it"), not a row to delete, and an edit keeps the model's
-- original alongside the analyst's rewrite rather than overwriting it. Feeds the acceptance-rate
-- KPI in app/program_kpis.py — the only honest measure of whether this feature is trusted.
CREATE TABLE IF NOT EXISTS gap_analysis_events (
    id            TEXT PRIMARY KEY,
    analysis_id   TEXT NOT NULL,
    vendor_ref    TEXT NOT NULL,
    rec_index     INTEGER NOT NULL,
    event         TEXT NOT NULL,   -- accepted | edited | rejected
    edited_text   TEXT,
    actor         TEXT,
    note          TEXT,
    content_hash  TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gap_analysis_events_analysis ON gap_analysis_events(analysis_id, created_at);
CREATE INDEX IF NOT EXISTS idx_gap_analysis_events_vendor ON gap_analysis_events(vendor_ref, created_at);

CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only: % forbidden', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

# (table, trigger name, operation) — created once per process, not once per connection.
#
# `CREATE OR REPLACE TRIGGER` takes an AccessExclusiveLock on its table: the strongest lock
# Postgres has. Twenty-four of them, re-run on every connection, is what made two concurrent
# API requests deadlock against each other (each holding locks the other was queued behind) and
# what put 2.6 seconds of DDL in front of every page load. See `_ensure_schema`.
_TRIGGERS = [
    ("evidence", "evidence_no_update", "UPDATE"),
    ("evidence", "evidence_no_delete", "DELETE"),
    ("scores", "scores_no_update", "UPDATE"),
    ("scores", "scores_no_delete", "DELETE"),
    ("findings", "findings_no_update", "UPDATE"),
    ("findings", "findings_no_delete", "DELETE"),
    ("vendor_profiles", "profiles_no_update", "UPDATE"),
    ("vendor_profiles", "profiles_no_delete", "DELETE"),
    ("disputes", "disputes_no_update", "UPDATE"),
    ("disputes", "disputes_no_delete", "DELETE"),
    ("decisions", "decisions_no_update", "UPDATE"),
    ("decisions", "decisions_no_delete", "DELETE"),
    ("benchmark_snapshots", "bmsnap_no_update", "UPDATE"),
    ("benchmark_snapshots", "bmsnap_no_delete", "DELETE"),
    # Benchmarking v2. The append-only guarantee is load-bearing here in a way it is not for a cache:
    # a placement's whole claim is "this was true against THAT population", and an UPDATE would let
    # a historical comparison be silently restated against a different one.
    ("supplier_attributes", "supplier_attrs_no_update", "UPDATE"),
    ("supplier_attributes", "supplier_attrs_no_delete", "DELETE"),
    ("cohort_snapshots", "cohort_snap_no_update", "UPDATE"),
    ("cohort_snapshots", "cohort_snap_no_delete", "DELETE"),
    ("benchmark_placements", "bm_place_no_update", "UPDATE"),
    ("benchmark_placements", "bm_place_no_delete", "DELETE"),
    ("cohort_disputes", "cohort_disp_no_update", "UPDATE"),
    ("cohort_disputes", "cohort_disp_no_delete", "DELETE"),
    # The monitor run ledger. Protected for a reason that is not about legal artefacts: an operator
    # who can edit the run history can make a monitoring practice look continuous after the fact,
    # and the whole value of the ledger is that it cannot be.
    ("monitor_runs", "monitor_runs_no_update", "UPDATE"),
    ("monitor_runs", "monitor_runs_no_delete", "DELETE"),
    # E14 — a generated analysis and its accept/edit/reject trail. The trail's whole evidentiary
    # value ("a model proposed this, a person declined it") depends on nobody being able to edit a
    # past decision after the fact.
    ("gap_analyses", "gap_analyses_no_update", "UPDATE"),
    ("gap_analyses", "gap_analyses_no_delete", "DELETE"),
    ("gap_analysis_events", "gap_analysis_events_no_update", "UPDATE"),
    ("gap_analysis_events", "gap_analysis_events_no_delete", "DELETE"),
]


# Which (dsn, schema) pairs this PROCESS has already brought up to schema. The DDL is idempotent,
# so re-running it was harmless — just ruinously expensive, and, run concurrently, deadlock-prone.
_schema_applied: set[tuple[str, str | None]] = set()
_schema_guard = threading.Lock()


def _advisory_key(schema: str | None) -> int:
    """A stable 63-bit lock key per schema, so two schemas never serialise against each other."""
    digest = hashlib.sha256((schema or "public").encode()).digest()
    return int.from_bytes(digest[:8], "big") >> 1


def _ensure_schema(conn: psycopg.Connection, dsn: str, schema: str | None) -> None:
    """Create tables, indexes and append-only triggers — at most once per process per schema.

    Two locks, guarding two different races:

      * `_schema_guard` (in-process) stops two request threads racing to be the first to apply.
      * `pg_advisory_xact_lock` (cluster-wide) stops two PROCESSES — a uvicorn worker and a CLI
        run, say — issuing overlapping AccessExclusiveLock DDL and deadlocking. A *transaction*
        advisory lock rather than a session one, because Neon fronts the app with PgBouncer in
        transaction mode: a session-level lock could be left held on a connection handed to
        somebody else. It releases when the wrapping transaction commits.
    """
    key = (dsn, schema)
    if key in _schema_applied:
        return
    with _schema_guard:
        if key in _schema_applied:
            return
        with conn.cursor() as cur:
            if schema:
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                cur.execute(f'SET search_path TO "{schema}"')
            with conn.transaction():
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (_advisory_key(schema),))
                cur.execute(_SCHEMA)
                for table, name, op in _TRIGGERS:
                    create = (f"CREATE OR REPLACE TRIGGER {name} BEFORE {op} ON {table} "
                              f"FOR EACH ROW EXECUTE FUNCTION reject_mutation()")
                    try:
                        # A nested `transaction()` is a SAVEPOINT: without it, a failed statement
                        # would poison the whole DDL transaction and the fallback could not run.
                        with conn.transaction():
                            cur.execute(create)
                    except psycopg.Error:
                        # CREATE OR REPLACE TRIGGER is PG14+. Older servers get drop-then-create.
                        try:
                            with conn.transaction():
                                cur.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
                                cur.execute(create.replace("CREATE OR REPLACE", "CREATE", 1))
                        except psycopg.Error:
                            pass
        _schema_applied.add(key)


class PostgresStore:
    """Thin, synchronous psycopg3 wrapper. One connection per store instance.

    `schema` isolates all tables into a named Postgres schema instead of `public`. That is the one
    lever the test harness needs: the store is append-only by design — the triggers below reject
    UPDATE and DELETE, which is exactly the Finding A legal-artefact guarantee — so a test suite
    running in `public` would permanently pollute real data it can never delete. Pointed at a
    per-run test schema instead, the suite creates its tables there, runs, and the fixture drops
    the whole schema afterwards (DROP SCHEMA is DDL, not a row mutation, so the triggers do not
    block it). Same database, real cohorts untouched.
    """

    def __init__(self, dsn: str, schema: str | None = None, *,
                 conn: psycopg.Connection | None = None,
                 on_close: Callable[[psycopg.Connection], None] | None = None) -> None:
        self.schema = schema
        # `conn`/`on_close` let a caller lend a connection it owns — `storage.get_store()` hands
        # one out of a pool and takes it back on close. Without them the store connects and
        # disconnects for itself, which is what the test harness and the CLI still do.
        self._on_close = on_close
        if conn is not None:
            self._conn = conn
        else:
            # `search_path` is set on the connection itself, so every statement this store runs —
            # schema DDL, inserts, the cohort queries — targets the isolated schema without
            # threading a qualifier through every SQL string.
            options = f"-c search_path={schema}" if schema else None
            self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row,
                                         options=options)
        _ensure_schema(self._conn, dsn, schema)

    def close(self) -> None:
        if self._on_close is not None:
            self._on_close(self._conn)
        else:
            self._conn.close()

    def __enter__(self) -> PostgresStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- evidence (append-only) ---

    def put(self, result: CollectorResult) -> Evidence:
        payload = _payload_of(result)
        canonical = _canonical_json(payload)
        content_hash = _sha256(canonical)
        record = Evidence(
            id=str(uuid.uuid4()), vendor_ref=result.vendor_ref, source=result.source,
            status=result.status, fetched_at=result.fetched_at,
            source_version=result.source_version, raw=result.raw,
            reliability=result.reliability, notes=result.notes, content_hash=content_hash,
        )
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO evidence (id, vendor_ref, source, status, fetched_at,
                     source_version, payload_json, reliability, notes, content_hash, stored_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (record.id, record.vendor_ref, record.source, record.status,
                 record.fetched_at, record.source_version, canonical, record.reliability,
                 record.notes, record.content_hash, record.stored_at),
            )
        return record

    def get(self, evidence_id: str) -> Evidence | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM evidence WHERE id = %s", (evidence_id,))
            row = cur.fetchone()
        return self._row_to_evidence(row) if row else None

    def for_vendor(self, vendor_ref: str) -> list[Evidence]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM evidence WHERE vendor_ref = %s ORDER BY stored_at", (vendor_ref,)
            )
            rows = cur.fetchall()
        return [self._row_to_evidence(r) for r in rows]

    def verify(self, evidence_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT payload_json, content_hash FROM evidence WHERE id = %s", (evidence_id,)
            )
            row = cur.fetchone()
        if row is None:
            return False
        return _sha256(row["payload_json"]) == row["content_hash"]

    # --- scores (append-only history) ---

    def put_score(self, score: Score) -> str:
        sid = str(uuid.uuid4())
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO scores (id, vendor_ref, computed_at, blocked, refused,
                     posture, grade, overall_confidence, confidence_band,
                     critical_ceiling_applied, score_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (sid, score.vendor_ref, score.computed_at, score.blocked, score.refused,
                 score.posture, score.grade, score.overall_confidence, score.confidence_band,
                 score.critical_ceiling_applied, score.model_dump_json()),
            )
        return sid

    def latest_score(self, vendor_ref: str) -> Score | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT score_json FROM scores WHERE vendor_ref = %s "
                "ORDER BY computed_at DESC LIMIT 1",
                (vendor_ref,),
            )
            row = cur.fetchone()
        return Score.model_validate_json(row["score_json"]) if row else None

    def score_history(self, vendor_ref: str) -> list[Score]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT score_json FROM scores WHERE vendor_ref = %s ORDER BY computed_at",
                (vendor_ref,),
            )
            rows = cur.fetchall()
        return [Score.model_validate_json(r["score_json"]) for r in rows]

    def latest_scores_all(self) -> list[Score]:
        """The most recent score for every vendor ever scored — the portfolio read model.

        DISTINCT ON keeps one row per vendor (the newest by computed_at), so this is the current
        state of the whole book without loading a vendor's full history. It reads from the same
        append-only `scores` table every other view reads — no separate 'portfolio' store that
        could drift from the record it summarises."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (vendor_ref) score_json FROM scores "
                "ORDER BY vendor_ref, computed_at DESC",
            )
            rows = cur.fetchall()
        return [Score.model_validate_json(r["score_json"]) for r in rows]

    # --- vendor profiles (append-only; the cohort index behind benchmarking) ---

    def put_profile(self, profile: VendorProfile) -> str:
        pid = str(uuid.uuid4())
        canonical = _canonical_json(json.loads(profile.model_dump_json()))
        cohort = profile.cohort
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO vendor_profiles
                   (id, vendor_ref, cohort_key, sector, size_band, revenue_band, employee_band,
                    region, criticality, completeness, profile_json, content_hash,
                    computed_at, stored_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (pid, profile.vendor_ref,
                 cohort.key if cohort else None,
                 cohort.sector if cohort else None,
                 # `size_band` is the legacy column; the employee band is its closer successor.
                 cohort.employee_band if cohort else None,
                 cohort.revenue_band if cohort else None,
                 cohort.employee_band if cohort else None,
                 cohort.region if cohort else None,
                 profile.criticality, profile.completeness, profile.model_dump_json(),
                 _sha256(canonical), profile.computed_at, utcnow()),
            )
        return pid

    def latest_profile(self, vendor_ref: str) -> VendorProfile | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT profile_json FROM vendor_profiles WHERE vendor_ref = %s "
                "ORDER BY computed_at DESC LIMIT 1",
                (vendor_ref,),
            )
            row = cur.fetchone()
        return VendorProfile.model_validate_json(row["profile_json"]) if row else None

    def latest_profiles_all(self) -> dict[str, VendorProfile]:
        """The latest profile for EVERY vendor, in one query — the book-wide counterpart to
        `latest_profile`.

        `/api/portfolio` called `latest_profile` once per vendor: 146 sequential round trips to
        Neon to answer one question about the book. Same DISTINCT ON shape as `latest_scores_all`,
        and the same guarantee — newest row per vendor from the append-only table, nothing cached.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (vendor_ref) vendor_ref, profile_json FROM vendor_profiles "
                "ORDER BY vendor_ref, computed_at DESC",
            )
            rows = cur.fetchall()
        return {r["vendor_ref"]: VendorProfile.model_validate_json(r["profile_json"])
                for r in rows}

    def raw_by_source_all(self, sources: Sequence[str]) -> dict[str, dict[str, Any]]:
        """`{vendor_ref: {source: raw}}` for the named sources only, across the whole book.

        Deliberately narrow. The fourth-party concentration view needs three collectors' payloads
        (`fourth_party.SOURCES`); reading it through `for_vendor` fetched every column of every
        collector's evidence for every vendor — megabytes of `payload_json` to look at three keys.

        Newest NON-EMPTY row per (vendor, source) wins. That qualifier is load-bearing and cost a
        real mismatch to find: `extract` builds its map with `if e.raw`, so a collector that later
        returned nothing does not evict the last payload that said something. Selecting the newest
        row outright and discarding it when empty silently drops the source instead — `archerirm`
        lost its whole dependency list that way. Ascending order plus the same falsy skip
        reproduces the original collapse exactly.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT vendor_ref, source, payload_json FROM evidence WHERE source = ANY(%s) "
                "ORDER BY vendor_ref, source, stored_at",
                (list(sources),),
            )
            rows = cur.fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            raw = json.loads(r["payload_json"]).get("raw")
            if raw:
                out.setdefault(r["vendor_ref"], {})[r["source"]] = raw
        return out

    def latest_supplier_attributes_all(self) -> dict[str, dict[str, Any]]:
        """Latest supplier attributes for every supplier, in one query."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (supplier_ref) * FROM supplier_attributes "
                "ORDER BY supplier_ref, created_at DESC",
            )
            rows = cur.fetchall()
        return {r["supplier_ref"]: dict(r) for r in rows}

    def findings_all(self, *, latest_only: bool = True) -> dict[str, list[PersistedFinding]]:
        """`{vendor_ref: findings}` for the whole book — the bulk form of `findings_for_vendor`.

        `latest_only` keeps the same meaning: only the most recent run per vendor. Expressed here
        as a window over one scan instead of a correlated subquery re-run once per vendor.
        """
        with self._conn.cursor() as cur:
            if latest_only:
                cur.execute(
                    """SELECT * FROM (
                           SELECT *, FIRST_VALUE(run_id) OVER (
                               PARTITION BY vendor_ref ORDER BY stored_at DESC) AS _latest_run
                           FROM findings
                       ) f
                       WHERE run_id IS NOT DISTINCT FROM _latest_run
                       ORDER BY vendor_ref, stored_at""",
                )
            else:
                cur.execute("SELECT * FROM findings ORDER BY vendor_ref, stored_at")
            rows = cur.fetchall()
        out: dict[str, list[PersistedFinding]] = {}
        for r in rows:
            out.setdefault(r["vendor_ref"], []).append(self._row_to_finding(r))
        return out

    def first_evidence_at_all(self) -> dict[str, Any]:
        """`{vendor_ref: earliest fetched_at}` — one aggregate instead of dragging every evidence
        row back to take a minimum in Python, which is all `_cycle_time` ever did with them."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT vendor_ref, MIN(fetched_at) AS first_at FROM evidence GROUP BY vendor_ref",
            )
            rows = cur.fetchall()
        return {r["vendor_ref"]: r["first_at"] for r in rows}

    def cohort_peers(self, dims: dict[str, str], *,
                     exclude_ref: str | None = None) -> list[dict[str, Any]]:
        """Vendors matching EVERY supplied cohort dimension — the widening ladder's one query.

        `dims` is any subset of sector / revenue_band / employee_band / region; passing fewer is
        what widening means. Excludes the vendor itself, blocked/refused scores, and superseded
        profiles and scores, exactly as the SQLite store does — each exclusion would otherwise
        skew a published percentile."""
        allowed = {"sector", "revenue_band", "employee_band", "region"}
        clauses, params = [], []
        for key, value in dims.items():
            if key not in allowed:
                raise ValueError(f"unknown cohort dimension {key!r}")
            clauses.append(f"p.{key} = %s")
            params.append(value)
        if exclude_ref:
            clauses.append("p.vendor_ref <> %s")
            params.append(exclude_ref)
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        with self._conn.cursor() as cur:
            cur.execute(_COHORT_PEERS_SQL + where, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def cohort_signal_bands(self, dims: dict[str, str], *,
                            exclude_ref: str | None = None) -> list[tuple[str, str, str]]:
        """`(vendor_ref, signal, band)` for every peer's current run — the input to prevalence."""
        allowed = {"sector", "revenue_band", "employee_band", "region"}
        clauses, params = [], []
        for key, value in dims.items():
            if key not in allowed:
                raise ValueError(f"unknown cohort dimension {key!r}")
            clauses.append(f"p.{key} = %s")
            params.append(value)
        if exclude_ref:
            clauses.append("cf.vendor_ref <> %s")
            params.append(exclude_ref)
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        with self._conn.cursor() as cur:
            cur.execute(_COHORT_SIGNALS_SQL + where, params)
            rows = cur.fetchall()
        return [(r["vendor_ref"], r["signal"], r["band_key"]) for r in rows]

    def cohort_members(self, cohort_key: str) -> list[tuple[str, int]]:
        with self._conn.cursor() as cur:
            cur.execute(_COHORT_PEERS_SQL + " AND p.cohort_key = %s ORDER BY s.posture DESC",
                        (cohort_key,))
            rows = cur.fetchall()
        return [(r["vendor_ref"], int(r["posture"])) for r in rows]

    # --- benchmarking v2: attributes, cohorts, snapshots, placements, disputes (append-only) ---

    def put_supplier_attributes(self, attrs: Any) -> str:
        """Append the raw inputs a v2 cohort is derived from.

        Append-only, so an upheld dispute is a NEW row rather than an edit — the correction has to be
        an input, because the design's "no manual overrides in the DB" rule exists precisely so the
        derivation can be re-run over it and produce a fresh, diffable snapshot.
        """
        aid = str(uuid.uuid4())
        payload = {
            "supplier_ref": attrs.supplier_ref, "sector": attrs.sector,
            "size_band": attrs.size_band, "delivery_model": attrs.delivery_model,
            "employees": attrs.employees, "revenue": attrs.revenue,
        }
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO supplier_attributes
                   (id, supplier_ref, sector, size_band, delivery_model, data_access_scope,
                    employees, revenue, revenue_currency, size_band_basis, source, content_hash,
                    created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (aid, attrs.supplier_ref, attrs.sector, attrs.size_band, attrs.delivery_model,
                 attrs.data_access_scope, attrs.employees, attrs.revenue, attrs.revenue_currency,
                 attrs.size_band_basis, attrs.source, _sha256(_canonical_json(payload)), utcnow()),
            )
        return aid

    def latest_supplier_attributes(self, supplier_ref: str) -> dict[str, Any] | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM supplier_attributes WHERE supplier_ref = %s "
                "ORDER BY created_at DESC LIMIT 1", (supplier_ref,),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def bm_cohort_peers(self, dims: dict[str, Any], *,
                        exclude_ref: str | None = None) -> list[dict[str, Any]]:
        """Suppliers matching EVERY supplied v2 cohort dimension.

        `dims` is any subset of sector / size_band / delivery_model, plus the pseudo-dimension
        `sector_group`, which arrives as a LIST of sectors already resolved from the config rollup.

        `exclude_ref` is not optional in practice and the caller is expected to pass it. A cohort of
        one is not a peer group, and at the threshold boundary self-inclusion is worse than
        flattering: an "n=30" that counts the subject is 29 peers, and the percentile rule is then
        wrong by one on the exact case it exists to govern.
        """
        allowed = {"sector", "size_band", "delivery_model"}
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in dims.items():
            if key == "sector_group":
                sectors = list(value) if isinstance(value, (list, tuple, set)) else [value]
                if not sectors:
                    return []
                clauses.append("p.sector = ANY(%s)")
                params.append(sectors)
                continue
            if key not in allowed:
                raise ValueError(f"unknown v2 cohort dimension {key!r}")
            clauses.append(f"p.{key} = %s")
            params.append(value)
        if exclude_ref:
            # `p` is `current_attrs`, whose column is `supplier_ref`; `vendor_ref` is only the
            # SELECT alias, and a SELECT alias is not in scope in WHERE. This said `p.vendor_ref`
            # and so raised UndefinedColumn on every call that passed `exclude_ref` — which is
            # every call the service makes, since a cohort must never count the subject. The whole
            # v2 benchmark surface therefore 500'd against Postgres.
            clauses.append("p.supplier_ref <> %s")
            params.append(exclude_ref)
        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        with self._conn.cursor() as cur:
            cur.execute(_BM_COHORT_PEERS_SQL + where, params)
            return [dict(r) for r in cur.fetchall()]

    def bm_peer_signals(self, refs: list[str]) -> dict[str, dict[str, str]]:
        """Latest-run signal bands for a resolved peer set — `{ref: {signal: band}}`.

        SEPARATE FROM `bm_cohort_peers` DELIBERATELY. That query runs once per LADDER RUNG while a
        cohort is being resolved, and most rungs are discarded; joining every peer's findings into
        it would multiply the row count by ~27 to answer a question only the winning rung asks.
        This runs once, over the peers that were actually assigned.

        `signals` on `PeerRecord` has existed since EB and nothing populated it, which meant the
        per-cohort discrimination test silently ran on domains only — half the analysis it
        documents. E10a needs peer prevalence for driver attribution, so both are fixed by the
        same query.

        Latest run per vendor, matching `findings_for_vendor`: findings are append-only, so
        without the run filter a re-scored peer contributes its old bands alongside its new ones
        and a prevalence rate counts the same company twice.
        """
        if not refs:
            return {}
        with self._conn.cursor() as cur:
            cur.execute(
                """
                WITH latest AS (
                    SELECT vendor_ref, MAX(stored_at) AS at
                    FROM findings WHERE vendor_ref = ANY(%s) GROUP BY vendor_ref
                ),
                run AS (
                    SELECT f.vendor_ref, f.run_id
                    FROM findings f JOIN latest l
                      ON l.vendor_ref = f.vendor_ref AND l.at = f.stored_at
                )
                SELECT f.vendor_ref, f.signal, f.band_key
                FROM findings f
                JOIN run r ON r.vendor_ref = f.vendor_ref
                           AND f.run_id IS NOT DISTINCT FROM r.run_id
                WHERE f.vendor_ref = ANY(%s)
                """,
                (refs, refs),
            )
            out: dict[str, dict[str, str]] = {}
            for row in cur.fetchall():
                out.setdefault(row["vendor_ref"], {})[row["signal"]] = row["band_key"]
        return out

    def put_cohort_snapshot(self, snap: Any) -> str:
        """Freeze one cohort. Append-only: a rebuild writes a new row and never touches this one."""
        payload = {
            "cohort_key": snap.cohort_key, "rung": list(snap.rung), "n": snap.distribution.n,
            "member_hash": snap.member_hash, "is_synthetic": snap.is_synthetic,
            "last_refreshed": snap.last_refreshed.isoformat(),
        }
        canonical = _canonical_json(payload)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cohort_snapshots (id, cohort_key, rung_label, peer_n, median, "
                "is_synthetic, member_hash, snapshot_json, content_hash, last_refreshed, stored_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                (snap.snapshot_id, snap.cohort_key, snap.rung_label, snap.distribution.n,
                 snap.distribution.median, snap.is_synthetic, snap.member_hash,
                 snap.model_dump_json(), _sha256(canonical), snap.last_refreshed, utcnow()),
            )
        return snap.snapshot_id

    def cohort_snapshot(self, snapshot_id: str) -> Any | None:
        """One snapshot by id — the internal, member-bearing form.

        Used by the dispute-review path and by trend reconstruction. NOT reachable from a tenant
        route: every outbound path calls `.public()`, which cannot carry member refs.
        """
        from .benchmarking.models import CohortSnapshot

        with self._conn.cursor() as cur:
            cur.execute("SELECT snapshot_json FROM cohort_snapshots WHERE id = %s", (snapshot_id,))
            row = cur.fetchone()
        return CohortSnapshot.model_validate_json(row["snapshot_json"]) if row else None

    def latest_cohort_snapshot(self, cohort_key: str) -> Any | None:
        from .benchmarking.models import CohortSnapshot

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT snapshot_json FROM cohort_snapshots WHERE cohort_key = %s "
                "ORDER BY last_refreshed DESC LIMIT 1", (cohort_key,),
            )
            row = cur.fetchone()
        return CohortSnapshot.model_validate_json(row["snapshot_json"]) if row else None

    def put_placement(self, placement: Any) -> str:
        """Record where one supplier stood against one snapshot. Append-only."""
        pid = str(uuid.uuid4())
        o = placement.overall
        payload = {
            "supplier_ref": placement.supplier_ref, "snapshot_id": placement.snapshot.snapshot_id,
            "posture": o.subject, "n": o.n, "quartile": o.quartile, "percentile": o.percentile,
            "assessed_at": placement.assessed_at.isoformat(),
        }
        canonical = _canonical_json(payload)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO benchmark_placements (id, supplier_ref, snapshot_id, cohort_key, "
                "posture, peer_n, sufficient, quartile, percentile, rank_of_n, bucket, reliability, "
                "disputed, placement_json, content_hash, assessed_at, stored_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (pid, placement.supplier_ref, placement.snapshot.snapshot_id,
                 placement.assignment.cohort_key, o.subject, o.n, o.sufficient, o.quartile,
                 o.percentile, o.rank_of_n, o.bucket, placement.reliability.value,
                 placement.disputed, placement.model_dump_json(), _sha256(canonical),
                 placement.assessed_at, utcnow()),
            )
        return pid

    def latest_placement(self, supplier_ref: str) -> Any | None:
        from .benchmarking.models import BenchmarkPlacement

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT placement_json FROM benchmark_placements WHERE supplier_ref = %s "
                "ORDER BY assessed_at DESC LIMIT 1", (supplier_ref,),
            )
            row = cur.fetchone()
        return BenchmarkPlacement.model_validate_json(row["placement_json"]) if row else None

    def placement_history(self, supplier_ref: str) -> list[Any]:
        """Every placement, oldest first — the trend.

        Each point was frozen against the cohort in force at the time, so a run of quartiles is a
        real trajectory rather than today's population applied to yesterday's scores.
        """
        from .benchmarking.models import BenchmarkPlacement

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT placement_json FROM benchmark_placements WHERE supplier_ref = %s "
                "ORDER BY assessed_at ASC", (supplier_ref,),
            )
            rows = cur.fetchall()
        return [BenchmarkPlacement.model_validate_json(r["placement_json"]) for r in rows]

    def put_cohort_dispute(self, dispute: Any) -> str:
        """Append one dispute EVENT. State transitions are new rows, never edits."""
        payload = {
            "dispute_id": dispute.dispute_id, "supplier_ref": dispute.supplier_ref,
            "state": dispute.state, "target": dispute.target,
            "asserted_value": dispute.asserted_value, "observed_value": dispute.observed_value,
            "evidence": dispute.evidence, "created_at": dispute.created_at.isoformat(),
        }
        canonical = _canonical_json(payload)
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cohort_disputes (id, dispute_id, supplier_ref, state, target, "
                "asserted_value, observed_value, cohort_key_at, snapshot_id_at, evidence, actor, "
                "note, content_hash, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (dispute.id, dispute.dispute_id, dispute.supplier_ref, dispute.state,
                 dispute.target, dispute.asserted_value, dispute.observed_value,
                 dispute.cohort_key_at, dispute.snapshot_id_at, dispute.evidence, dispute.actor,
                 dispute.note, _sha256(canonical), dispute.created_at),
            )
        return dispute.id

    def cohort_disputes_for_supplier(self, supplier_ref: str) -> list[Any]:
        """The CURRENT state of each dispute — its latest event.

        Collapsed here rather than in the caller because "is this supplier's cohort disputed?" is
        asked on every placement render, and answering it from the raw event log at each call site is
        how two call sites end up disagreeing about whether a dispute is open.
        """
        from .benchmarking.models import CohortDispute

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (dispute_id) * FROM cohort_disputes WHERE supplier_ref = %s "
                "ORDER BY dispute_id, created_at DESC", (supplier_ref,),
            )
            rows = cur.fetchall()
        return [CohortDispute.model_validate(dict(r)) for r in rows]

    def cohort_dispute_events(self, dispute_id: str) -> list[Any]:
        """The full history of one dispute, oldest first — who asserted what, who decided, when."""
        from .benchmarking.models import CohortDispute

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM cohort_disputes WHERE dispute_id = %s ORDER BY created_at ASC",
                (dispute_id,),
            )
            rows = cur.fetchall()
        return [CohortDispute.model_validate(dict(r)) for r in rows]

    # --- findings (append-only, signal-level interpreted evidence) ---

    def put_findings(self, vendor_ref: str, findings: list[NormalizedFinding],
                     run_id: str | None = None) -> list[str]:
        run_id = run_id or str(uuid.uuid4())
        ids: list[str] = []
        with self._conn.cursor() as cur:
            for nf in findings:
                canonical = _canonical_json(_finding_payload(nf))
                fid = str(uuid.uuid4())
                cur.execute(
                    """INSERT INTO findings
                       (id, vendor_ref, evidence_id, source, category, signal, band_key, severity,
                        penalty, effective_penalty, occurrences, run_id, observed, event_date,
                        is_critical, is_sanctions, note, dispute, content_hash, stored_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (fid, vendor_ref, nf.evidence_id, nf.source, nf.category, nf.signal,
                     nf.band_key, nf.severity, nf.penalty, nf.effective_penalty, nf.occurrences,
                     run_id, nf.observed, nf.event_date,
                     nf.is_critical, nf.is_sanctions, nf.note, nf.dispute,
                     _sha256(canonical), utcnow()),
                )
                ids.append(fid)
        return ids

    def findings_for_vendor(self, vendor_ref: str, *, latest_only: bool = True) -> list[PersistedFinding]:
        """Current run by default — see the SQLite implementation for why. `IS NOT DISTINCT FROM`
        is Postgres's null-safe equality, so pre-`run_id` rows group as one legacy run."""
        with self._conn.cursor() as cur:
            if latest_only:
                cur.execute(
                    """SELECT * FROM findings
                       WHERE vendor_ref = %s
                         AND run_id IS NOT DISTINCT FROM
                             (SELECT run_id FROM findings WHERE vendor_ref = %s
                              ORDER BY stored_at DESC LIMIT 1)
                       ORDER BY stored_at""",
                    (vendor_ref, vendor_ref),
                )
            else:
                cur.execute(
                    "SELECT * FROM findings WHERE vendor_ref = %s ORDER BY stored_at", (vendor_ref,)
                )
            rows = cur.fetchall()
        return [self._row_to_finding(r) for r in rows]

    @staticmethod
    def _row_to_finding(row: dict[str, Any]) -> PersistedFinding:
        return PersistedFinding(
            id=row["id"], vendor_ref=row["vendor_ref"], evidence_id=row["evidence_id"],
            source=row["source"], category=row["category"], signal=row["signal"],
            band_key=row["band_key"], severity=row["severity"], penalty=row["penalty"],
            effective_penalty=row["effective_penalty"], occurrences=row["occurrences"],
            run_id=row["run_id"], observed=row["observed"], event_date=row["event_date"],
            is_critical=bool(row["is_critical"]), is_sanctions=bool(row["is_sanctions"]),
            note=row["note"], dispute=row.get("dispute"),
            content_hash=row["content_hash"], stored_at=row["stored_at"],
        )

    # --- disputes (append-only event log; the vendor-refute path, Phase 4) ---

    def put_dispute(self, dispute: Dispute) -> str:
        """Append one dispute event. Returns its id. Never overwrites an earlier event."""
        payload = {
            "dispute_id": dispute.dispute_id, "vendor_ref": dispute.vendor_ref,
            "event": dispute.event, "signal": dispute.signal, "band_key": dispute.band_key,
            "kind": dispute.kind, "evidence": dispute.evidence,
            "actor": dispute.actor, "note": dispute.note,
        }
        content_hash = _sha256(_canonical_json(payload))
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO disputes
                   (id, dispute_id, vendor_ref, event, signal, band_key, kind, evidence,
                    actor, note, content_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (dispute.id, dispute.dispute_id, dispute.vendor_ref, dispute.event,
                 dispute.signal, dispute.band_key, dispute.kind, dispute.evidence,
                 dispute.actor, dispute.note, content_hash, dispute.created_at),
            )
        return dispute.id

    def disputes_for_vendor(self, vendor_ref: str) -> list[Dispute]:
        """Every dispute event for a vendor, oldest first — the full audit trail."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM disputes WHERE vendor_ref = %s ORDER BY created_at",
                        (vendor_ref,))
            rows = cur.fetchall()
        return [self._row_to_dispute(r) for r in rows]

    def latest_dispute_event(self, dispute_id: str) -> Dispute | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM disputes WHERE dispute_id = %s ORDER BY created_at DESC "
                        "LIMIT 1", (dispute_id,))
            row = cur.fetchone()
        return self._row_to_dispute(row) if row else None

    def accepted_dispute_targets(self, vendor_ref: str) -> dict[tuple[str, str], str]:
        """`(signal, band_key) -> kind` for disputes whose CURRENT state is accepted.

        Current state is the latest event per dispute_id — a dispute later rejected, or superseded,
        drops out. This is what the scoring engine consults so an accepted refute is honoured on
        every future score until the underlying observation changes."""
        targets: dict[tuple[str, str], str] = {}
        latest: dict[str, Dispute] = {}
        for d in self.disputes_for_vendor(vendor_ref):
            latest[d.dispute_id] = d   # oldest-first, so the last write wins
        for d in latest.values():
            if d.event == "accepted":
                targets[(d.signal, d.band_key)] = d.kind
        return targets

    @staticmethod
    def _row_to_dispute(row: dict[str, Any]) -> Dispute:
        return Dispute(
            id=row["id"], dispute_id=row["dispute_id"], vendor_ref=row["vendor_ref"],
            event=row["event"], signal=row["signal"], band_key=row["band_key"], kind=row["kind"],
            evidence=row["evidence"], actor=row["actor"], note=row["note"],
            content_hash=row["content_hash"], created_at=row["created_at"],
        )

    # --- decisions (append-only; procurement/executive buyer actions, Phase 6) ---

    def put_decision(self, decision: Decision) -> str:
        """Append one buyer decision. Returns its id. Never overwrites an earlier decision — a
        change of mind is a NEW row, so the whole decision history for a vendor is auditable."""
        payload = {
            "vendor_ref": decision.vendor_ref, "decision": decision.decision,
            "conditions": decision.conditions, "actor": decision.actor,
            "posture_at": decision.posture_at, "grade_at": decision.grade_at,
        }
        content_hash = _sha256(_canonical_json(payload))
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO decisions
                   (id, vendor_ref, decision, conditions, actor, posture_at, grade_at,
                    content_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (decision.id, decision.vendor_ref, decision.decision, decision.conditions,
                 decision.actor, decision.posture_at, decision.grade_at,
                 content_hash, decision.created_at),
            )
        return decision.id

    def decisions_for_vendor(self, vendor_ref: str) -> list[Decision]:
        """Every decision recorded for a vendor, newest first — the current call plus its history."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM decisions WHERE vendor_ref = %s ORDER BY created_at DESC",
                        (vendor_ref,))
            rows = cur.fetchall()
        return [self._row_to_decision(r) for r in rows]

    @staticmethod
    def _row_to_decision(row: dict[str, Any]) -> Decision:
        return Decision(
            id=row["id"], vendor_ref=row["vendor_ref"], decision=row["decision"],
            conditions=row["conditions"], actor=row["actor"], posture_at=row["posture_at"],
            grade_at=row["grade_at"], content_hash=row["content_hash"], created_at=row["created_at"],
        )

    # --- benchmark snapshots (append-only; the percentile trend's raw points, Phase 6) ---

    def put_benchmark_snapshot(self, snap: BenchmarkSnapshot) -> str:
        """Append one benchmark snapshot — where the vendor stood among peers as at this run."""
        payload = {
            "vendor_ref": snap.vendor_ref, "cohort_key": snap.cohort_key, "level": snap.level,
            "available": snap.available, "percentile": snap.percentile,
            "quartile": snap.quartile, "peer_n": snap.peer_n, "posture": snap.posture,
        }
        content_hash = _sha256(_canonical_json(payload))
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO benchmark_snapshots
                   (id, vendor_ref, cohort_key, level, available, percentile,
                    percentile_resolution, quartile, peer_n, posture, content_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (snap.id, snap.vendor_ref, snap.cohort_key, snap.level, snap.available,
                 snap.percentile, snap.percentile_resolution, snap.quartile, snap.peer_n,
                 snap.posture, content_hash, snap.created_at),
            )
        return snap.id

    def benchmark_history(self, vendor_ref: str) -> list[BenchmarkSnapshot]:
        """Every benchmark snapshot for a vendor, oldest first — the percentile trend."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM benchmark_snapshots WHERE vendor_ref = %s ORDER BY created_at",
                        (vendor_ref,))
            rows = cur.fetchall()
        return [
            BenchmarkSnapshot(
                id=r["id"], vendor_ref=r["vendor_ref"], cohort_key=r["cohort_key"], level=r["level"],
                available=bool(r["available"]), percentile=r["percentile"],
                percentile_resolution=r["percentile_resolution"], quartile=r["quartile"],
                peer_n=r["peer_n"], posture=r["posture"], content_hash=r["content_hash"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # --- monitor run ledger (append-only; evidence the schedule actually fires) ---

    def put_monitor_run(self, event: Any) -> str:
        """Append one monitor run event. Two per healthy run: `started`, then `finished`.

        A run that dies leaves only its `started` row, and `monitoring_health` reads that gap as an
        incomplete run rather than losing it — which is the whole reason this is an event log and
        not a status column.
        """
        payload = {
            "run_id": event.run_id, "event": event.event, "trigger": event.trigger,
            "mode": event.mode, "considered": event.considered, "rescored": event.rescored,
        }
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO monitor_runs
                   (id, run_id, event, trigger, mode, considered, rescored, drifted, failed,
                    duration_secs, error, detail_json, content_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (event.id, event.run_id, event.event, event.trigger, event.mode,
                 event.considered, event.rescored, event.drifted, event.failed,
                 event.duration_secs, event.error, _canonical_json(event.detail),
                 _sha256(_canonical_json(payload)), event.created_at),
            )
        return event.id

    def monitor_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Run events, newest first. Raw dicts — the ledger is read by one module and shaping it
        into a model here would put the interpretation in two places."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM monitor_runs ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    # --- E14 gap analysis (append-only: an analysis, and its accept/edit/reject trail) ---

    def put_gap_analysis(self, record: GapAnalysisRecord) -> str:
        """Append one generated analysis. A re-generation is a NEW row, never an edit — see the
        schema comment on `gap_analyses`."""
        payload = {
            "vendor_ref": record.vendor_ref, "provider": record.provider, "model": record.model,
            "prompt_version": record.prompt_version, "context_hash": record.context_hash,
            "executive_summary": record.executive_summary, "gaps": record.gaps,
            "recommendations": record.recommendations, "limitations": record.limitations,
        }
        content_hash = _sha256(_canonical_json(payload))
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO gap_analyses
                   (id, vendor_ref, provider, model, prompt_version, context_hash,
                    executive_summary, gaps_json, recommendations_json, limitations_json,
                    dropped_evidence_ids, content_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (record.id, record.vendor_ref, record.provider, record.model,
                 record.prompt_version, record.context_hash, record.executive_summary,
                 _canonical_json(record.gaps), _canonical_json(record.recommendations),
                 _canonical_json(record.limitations), record.dropped_evidence_ids,
                 content_hash, record.created_at),
            )
        return record.id

    def gap_analysis_history(self, vendor_ref: str) -> list[GapAnalysisRecord]:
        """Every analysis generated for this vendor, newest first."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM gap_analyses WHERE vendor_ref = %s ORDER BY created_at DESC",
                (vendor_ref,),
            )
            rows = cur.fetchall()
        return [self._row_to_gap_analysis(r) for r in rows]

    def latest_gap_analysis(self, vendor_ref: str) -> GapAnalysisRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM gap_analyses WHERE vendor_ref = %s ORDER BY created_at DESC LIMIT 1",
                (vendor_ref,),
            )
            row = cur.fetchone()
        return self._row_to_gap_analysis(row) if row else None

    def get_gap_analysis(self, analysis_id: str) -> GapAnalysisRecord | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM gap_analyses WHERE id = %s", (analysis_id,))
            row = cur.fetchone()
        return self._row_to_gap_analysis(row) if row else None

    def put_gap_analysis_event(self, event: GapAnalysisRecommendationEvent) -> str:
        """Append one accept/edit/reject event. Never overwrites an earlier one — same discipline
        `put_dispute` follows, for the same reason: the audit trail IS the feature."""
        payload = {
            "analysis_id": event.analysis_id, "vendor_ref": event.vendor_ref,
            "rec_index": event.rec_index, "event": event.event,
            "edited_text": event.edited_text, "actor": event.actor, "note": event.note,
        }
        content_hash = _sha256(_canonical_json(payload))
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO gap_analysis_events
                   (id, analysis_id, vendor_ref, rec_index, event, edited_text, actor, note,
                    content_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (event.id, event.analysis_id, event.vendor_ref, event.rec_index, event.event,
                 event.edited_text, event.actor, event.note, content_hash, event.created_at),
            )
        return event.id

    def gap_analysis_events(self, analysis_id: str) -> list[GapAnalysisRecommendationEvent]:
        """Every event for one analysis, oldest first — the full audit trail."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM gap_analysis_events WHERE analysis_id = %s ORDER BY created_at",
                (analysis_id,),
            )
            rows = cur.fetchall()
        return [self._row_to_gap_analysis_event(r) for r in rows]

    def gap_analysis_events_all(self) -> list[GapAnalysisRecommendationEvent]:
        """Every recommendation event, book-wide, in one query — the acceptance-rate KPI's
        population. Same discipline `findings_all` follows: one round trip, not one per vendor."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM gap_analysis_events ORDER BY created_at")
            rows = cur.fetchall()
        return [self._row_to_gap_analysis_event(r) for r in rows]

    def gap_analyses_all(self) -> dict[str, GapAnalysisRecord]:
        """Every generated analysis, book-wide, keyed by id — the join `gap_analysis_events_all`
        needs to break the acceptance rate down per provider."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM gap_analyses")
            rows = cur.fetchall()
        return {r["id"]: self._row_to_gap_analysis(r) for r in rows}

    @staticmethod
    def _row_to_gap_analysis(row: dict[str, Any]) -> GapAnalysisRecord:
        return GapAnalysisRecord(
            id=row["id"], vendor_ref=row["vendor_ref"], provider=row["provider"],
            model=row["model"], prompt_version=row["prompt_version"],
            context_hash=row["context_hash"], executive_summary=row["executive_summary"],
            gaps=json.loads(row["gaps_json"]), recommendations=json.loads(row["recommendations_json"]),
            limitations=json.loads(row["limitations_json"]),
            dropped_evidence_ids=row["dropped_evidence_ids"], content_hash=row["content_hash"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_gap_analysis_event(row: dict[str, Any]) -> GapAnalysisRecommendationEvent:
        return GapAnalysisRecommendationEvent(
            id=row["id"], analysis_id=row["analysis_id"], vendor_ref=row["vendor_ref"],
            rec_index=row["rec_index"], event=row["event"], edited_text=row["edited_text"],
            actor=row["actor"], note=row["note"], content_hash=row["content_hash"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_evidence(row: dict[str, Any]) -> Evidence:
        payload = json.loads(row["payload_json"])
        return Evidence(
            id=row["id"], vendor_ref=row["vendor_ref"], source=row["source"],
            status=row["status"], fetched_at=row["fetched_at"],
            source_version=row["source_version"], raw=payload.get("raw"),
            reliability=row["reliability"], notes=row["notes"],
            content_hash=row["content_hash"], stored_at=row["stored_at"],
        )
