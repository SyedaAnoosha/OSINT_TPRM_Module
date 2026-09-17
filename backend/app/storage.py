"""Store factory — one call the rest of the app uses to get the persistence backend.

The store is **Postgres only**. There is no local-file fallback: a defensible, reconstructible
evidence trail is the product (Finding A), and "it works on my machine with a throwaway file" is
not the same guarantee as "it is in the managed, append-only, hash-stamped store the score was
published from". So `get_store()` requires `DATABASE_URL` and fails loudly without it, rather than
silently degrading to something with weaker guarantees.

Each call returns a fresh store; callers close it when done — the same per-operation lifecycle
the API's request dependency and the collectors' harness already use. The *connection* underneath
it, however, is borrowed from a process-wide pool and returned on close, because opening one costs
a TLS handshake to Neon and the API was paying that on every request.
"""

from __future__ import annotations

import atexit
import threading
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from .config import get_settings
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
)

if TYPE_CHECKING:
    from .scoring.normalize import NormalizedFinding


@runtime_checkable
class Store(Protocol):
    """The contract the Postgres store satisfies. A Protocol, not a base class, so a test harness
    or a future backend can stand in wherever the guarantees below are met."""

    def put(self, result: CollectorResult) -> Evidence: ...
    def get(self, evidence_id: str) -> Evidence | None: ...
    def for_vendor(self, vendor_ref: str) -> list[Evidence]: ...
    def verify(self, evidence_id: str) -> bool: ...
    def put_score(self, score: Score) -> str: ...
    def latest_score(self, vendor_ref: str) -> Score | None: ...
    def score_history(self, vendor_ref: str) -> list[Score]: ...
    # The portfolio read model: latest score per vendor, from the same append-only table.
    def latest_scores_all(self) -> list[Score]: ...
    def put_findings(self, vendor_ref: str, findings: list[NormalizedFinding],
                     run_id: str | None = None) -> list[str]: ...
    def findings_for_vendor(self, vendor_ref: str, *,
                            latest_only: bool = True) -> list[PersistedFinding]: ...
    # Profiles + cohorts: WHO the vendor is, and who it may be compared with. Append-only, so a
    # benchmark published last quarter stays reconstructible against the cohort it was computed
    # against — a vendor that grows from `medium` to `large` must not silently re-write history.
    def put_profile(self, profile: VendorProfile) -> str: ...
    def latest_profile(self, vendor_ref: str) -> VendorProfile | None: ...
    # Book-wide reads. Same answers as calling the per-vendor methods in a loop, in one round trip
    # instead of one per vendor — which is the difference between a portfolio view that loads and
    # one that times out. `sources` is a collector-name filter; see `fourth_party.SOURCES`.
    def latest_profiles_all(self) -> dict[str, VendorProfile]: ...
    def raw_by_source_all(self, sources: Any) -> dict[str, dict[str, Any]]: ...
    def latest_supplier_attributes_all(self) -> dict[str, dict[str, Any]]: ...
    def findings_all(self, *, latest_only: bool = True) -> dict[str, list[PersistedFinding]]: ...
    def first_evidence_at_all(self) -> dict[str, Any]: ...
    # `dims` is any subset of sector / revenue_band / employee_band / region — passing fewer is
    # what the benchmark's widening ladder does when an exact four-factor cohort is too thin.
    def cohort_peers(self, dims: dict[str, str], *,
                     exclude_ref: str | None = None) -> list[dict[str, Any]]: ...
    def cohort_signal_bands(self, dims: dict[str, str], *,
                            exclude_ref: str | None = None) -> list[tuple[str, str, str]]: ...
    def cohort_members(self, cohort_key: str) -> list[tuple[str, int]]: ...
    # Disputes — the vendor-refute path (Phase 4). Append-only events; the current state of a
    # dispute is its latest event, and accepted refutes are honoured on every future score.
    def put_dispute(self, dispute: Dispute) -> str: ...
    def disputes_for_vendor(self, vendor_ref: str) -> list[Dispute]: ...
    def latest_dispute_event(self, dispute_id: str) -> Dispute | None: ...
    def accepted_dispute_targets(self, vendor_ref: str) -> dict[tuple[str, str], str]: ...
    # Decisions — the procurement/executive buyer action (Phase 6). Append-only; recorded alongside
    # the score, never inside it, so it can never move a number it is an output of.
    def put_decision(self, decision: Decision) -> str: ...
    def decisions_for_vendor(self, vendor_ref: str) -> list[Decision]: ...
    # Benchmark snapshots — where a vendor stood among peers AS AT one run (Phase 6). Append-only;
    # the percentile trend reads points frozen when true, not today's cohort on an old posture.
    def put_benchmark_snapshot(self, snap: BenchmarkSnapshot) -> str: ...
    def benchmark_history(self, vendor_ref: str) -> list[BenchmarkSnapshot]: ...
    # Benchmarking v2 — the enterprise peer-comparison layer (docs/design_decisions.md Part 1). All
    # append-only, for a reason that is stronger here than for a cache: a placement's whole claim is
    # "this was true against THAT population", so an UPDATE would let a historical comparison be
    # silently restated against a different peer group.
    #
    # `supplier_attributes` is the SOURCE OF TRUTH the cohort tables are a materialisation of, which
    # is what makes "rebuildable from raw data, no manual overrides" true rather than aspirational.
    def put_supplier_attributes(self, attrs: Any) -> str: ...
    def latest_supplier_attributes(self, supplier_ref: str) -> dict[str, Any] | None: ...
    # `dims` is any subset of sector / size_band / delivery_model, plus `sector_group` which arrives
    # as a resolved list of sectors. `data_access_scope` is deliberately absent: it is a relationship
    # property and routes to interpretation, never to cohort membership.
    def bm_cohort_peers(self, dims: dict[str, Any], *,
                        exclude_ref: str | None = None) -> list[dict[str, Any]]: ...
    # Latest-run signal bands for an already-resolved peer set. Separate from `bm_cohort_peers`
    # because that one runs per LADDER RUNG and most rungs are discarded; this runs once, on the
    # rung that won. Feeds both E10a's driver attribution and the per-cohort discrimination test,
    # which had been running on domains only because nothing populated `PeerRecord.signals`.
    def bm_peer_signals(self, refs: list[str]) -> dict[str, dict[str, str]]: ...
    # Snapshots are returned in their INTERNAL, member-bearing form. Every tenant-facing path calls
    # `.public()`, which structurally cannot carry member refs.
    def put_cohort_snapshot(self, snap: Any) -> str: ...
    def cohort_snapshot(self, snapshot_id: str) -> Any | None: ...
    def latest_cohort_snapshot(self, cohort_key: str) -> Any | None: ...
    def put_placement(self, placement: Any) -> str: ...
    def latest_placement(self, supplier_ref: str) -> Any | None: ...
    def placement_history(self, supplier_ref: str) -> list[Any]: ...
    def put_cohort_dispute(self, dispute: Any) -> str: ...
    def cohort_disputes_for_supplier(self, supplier_ref: str) -> list[Any]: ...
    def cohort_dispute_events(self, dispute_id: str) -> list[Any]: ...

    # Monitor run ledger — evidence that the schedule fires, which is a different fact from the
    # schedule existing. See `app/scheduler.py`.
    def put_monitor_run(self, event: Any) -> str: ...
    def monitor_runs(self, limit: int = 50) -> list[dict[str, Any]]: ...

    # E14 — gap analysis (a third audience view whose renderer is a model, over a finished
    # record). `gap_analyses` is append-only exactly like `benchmark_snapshots`: a past analysis is
    # a claim about what the model said against a SPECIFIC finished record, and must stay what it
    # was even after the vendor is rescored. `gap_analysis_events` is the analyst's accept / edit /
    # reject trail on ONE recommendation, append-only like `disputes` — a rejection is recorded,
    # never deleted, and an edit keeps the model's original alongside the analyst's rewrite.
    def put_gap_analysis(self, record: GapAnalysisRecord) -> str: ...
    def gap_analysis_history(self, vendor_ref: str) -> list[GapAnalysisRecord]: ...
    def latest_gap_analysis(self, vendor_ref: str) -> GapAnalysisRecord | None: ...
    def get_gap_analysis(self, analysis_id: str) -> GapAnalysisRecord | None: ...
    # Book-wide `analysis_id -> record`, for the acceptance-rate KPI's per-provider breakdown —
    # `gap_analysis_events_all()` carries no provider, and joining per vendor would be one query per
    # vendor exactly the way `program_kpis.compute` stopped doing for everything else.
    def gap_analyses_all(self) -> dict[str, GapAnalysisRecord]: ...
    def put_gap_analysis_event(self, event: GapAnalysisRecommendationEvent) -> str: ...
    def gap_analysis_events(self, analysis_id: str) -> list[GapAnalysisRecommendationEvent]: ...
    # Book-wide, in one query — the acceptance-rate KPI's population (app/program_kpis.py), same
    # discipline as `findings_all`/`latest_scores_all`: one round trip instead of one per vendor.
    def gap_analysis_events_all(self) -> list[GapAnalysisRecommendationEvent]: ...

    def close(self) -> None: ...


class StorageNotConfigured(RuntimeError):
    """Raised when no DATABASE_URL is set. Loud, not a silent fallback."""


# --------------------------------------------------------------------- connection pooling
#
# Neon is a network hop away: a fresh TLS handshake costs ~0.7s, which the API was paying on
# every single request because `store_dep` builds a store per request. A process-wide pool
# amortises that to roughly one round trip. It is a `psycopg_pool.ConnectionPool` when that
# package is installed and a plain `psycopg.connect` otherwise — a missing optional dependency
# should slow the app down, not stop it.

_pool: Any = None
_pool_dsn: str | None = None
_pool_lock = threading.Lock()

# Neon's free tier caps concurrent connections, and a dashboard fans out ~10 requests at once.
# Small enough to stay well inside that cap, large enough that the fan-out does not queue.
POOL_MAX_SIZE = 10


def _get_pool(dsn: str) -> Any:
    """The process-wide pool, or None if psycopg_pool is not installed."""
    global _pool, _pool_dsn
    if _pool is not None and _pool_dsn == dsn:
        return _pool
    with _pool_lock:
        if _pool is not None and _pool_dsn == dsn:
            return _pool
        try:
            from psycopg_pool import ConnectionPool
        except ImportError:
            return None
        from psycopg.rows import dict_row

        pool = ConnectionPool(
            dsn,
            min_size=0,          # nothing is opened until something asks — CLI runs stay cheap
            max_size=POOL_MAX_SIZE,
            # Neon hangs up on idle connections, so a pooled one can be dead on arrival. `check`
            # spends a round trip proving it is alive rather than failing the request.
            check=ConnectionPool.check_connection,
            max_idle=240.0,
            kwargs={
                "autocommit": True,
                "row_factory": dict_row,
                # PgBouncer in transaction mode cannot carry server-side prepared statements
                # across the pooling boundary, and psycopg starts preparing after five reuses —
                # which only becomes reachable once connections are long-lived, as they now are.
                "prepare_threshold": None,
            },
            open=True,
            name="tprm",
        )
        _pool, _pool_dsn = pool, dsn
        atexit.register(close_pool)
        return pool


def close_pool() -> None:
    """Shut the pool down. Wired to FastAPI shutdown and to `atexit`; safe to call twice."""
    global _pool, _pool_dsn
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:  # noqa: BLE001 — shutdown must not raise
                pass
        _pool, _pool_dsn = None, None


def get_store() -> Store:
    """The Postgres store, or a clear error. Never a quiet local-file substitute."""
    settings = get_settings()
    dsn = settings.database_url.strip()
    if not dsn:
        raise StorageNotConfigured(
            "DATABASE_URL is not set. This application persists to Postgres only — set "
            "DATABASE_URL (e.g. your Neon connection string) in the environment or backend/.env."
        )
    from .pg_store import PostgresStore

    pool = _get_pool(dsn)
    if pool is None:
        return PostgresStore(dsn)
    conn = pool.getconn()
    try:
        return PostgresStore(dsn, conn=conn, on_close=pool.putconn)
    except Exception:
        # Never leak a checked-out connection when schema setup fails.
        pool.putconn(conn)
        raise
