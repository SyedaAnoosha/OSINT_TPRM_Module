"""Phase 0 exit criterion + the invariants that make the store a legal artefact.

These run against the disposable Postgres schema from conftest (`store` fixture). The invariants —
byte-identical read-back, append-only at the database level — are the Finding A / Finding B
guarantees, and they are enforced by the database itself, so they must be tested against the real
database, not a stand-in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from app.models import CollectorResult, Finding, Score, utcnow
from app.scoring.normalize import NormalizedFinding

# The append-only triggers raise a plpgsql exception; psycopg surfaces it as RaiseException.
Immutable = psycopg.errors.RaiseException


def _finding(signal: str = "dmarc", severity: str = "medium", penalty: float = 8.0,
             evidence_id: str = "ev-1") -> NormalizedFinding:
    return NormalizedFinding(
        evidence_id=evidence_id, source="dns", category="cyber_hygiene_technical",
        signal=signal, band_key="p_none", severity=severity, penalty=penalty,
        event_date=None, is_critical=False, is_sanctions=False, observed="p=none",
    )


def _score(vendor: str = "atlassian", posture: int = 78, conf: float = 0.5,
           when: datetime | None = None) -> Score:
    return Score(vendor_ref=vendor, posture=posture, grade="B", overall_confidence=conf,
                 confidence_band="Medium", computed_at=when or datetime.now(UTC))


def _sample_result(vendor: str = "atlassian") -> CollectorResult:
    return CollectorResult(
        source="dns",
        vendor_ref=vendor,
        status="ok",
        source_version="dmarc-lookup-v1",
        raw={
            "dmarc": "v=DMARC1; p=none; rua=mailto:dmarc@example.com",
            "spf": "v=spf1 include:_spf.example.com ~all",
            "nested": {"b": 2, "a": 1},  # deliberately unsorted to exercise canonicalisation
            "unicode": "café — façade",
        },
        findings=[Finding(source="dns", signal="dmarc", observed="p=none", value={"p": "none"})],
        reliability=0.95,
        notes="live lookup",
    )


def test_write_then_read_back_byte_identical(store):
    """THE Phase 0 exit criterion: an Evidence row is written and read back byte-identical."""
    result = _sample_result()
    written = store.put(result)
    read = store.get(written.id)

    assert read is not None
    assert read.raw == result.raw               # payload survives the round trip exactly
    assert read.content_hash == written.content_hash
    assert store.verify(written.id) is True     # stored bytes still hash to the stored hash
    assert read.fetched_at == result.fetched_at
    assert read.source_version == "dmarc-lookup-v1"


def test_hash_is_deterministic_across_key_order(store):
    """Same logical payload, different dict key order -> identical content hash."""
    a = _sample_result()
    b = _sample_result()
    # `fetched_at` defaults to utcnow(), so two constructions differ by microseconds and the hash
    # legitimately differs with them — provenance is part of what is hashed. Pin it to a's value
    # so this test isolates the property it names: KEY ORDER must not change the hash.
    b.fetched_at = a.fetched_at
    b.raw = {  # same content, keys reordered
        "unicode": "café — façade",
        "spf": a.raw["spf"],
        "nested": {"a": 1, "b": 2},
        "dmarc": a.raw["dmarc"],
    }
    assert store.put(a).content_hash == store.put(b).content_hash


def test_empty_status_is_persisted_not_dropped(store):
    """`empty` must be a first-class stored result — absence-of-evidence is evidence."""
    empty = CollectorResult(
        source="edgar", vendor_ref="myob", status="empty",
        source_version=None, raw=None, reliability=0.9,
        notes="no SEC filings — private company",
    )
    rec = store.put(empty)
    read = store.get(rec.id)
    assert read is not None
    assert read.status == "empty"
    assert read.raw is None


def test_store_is_append_only_update_forbidden(store):
    """The database itself must reject UPDATE — immutability is not left to convention."""
    rec = store.put(_sample_result())
    with pytest.raises(Immutable):
        store._conn.execute("UPDATE evidence SET status = 'error' WHERE id = %s", (rec.id,))


def test_store_is_append_only_delete_forbidden(store):
    rec = store.put(_sample_result())
    with pytest.raises(Immutable):
        store._conn.execute("DELETE FROM evidence WHERE id = %s", (rec.id,))


def test_fetched_at_must_be_timezone_aware():
    """A naive timestamp is rejected — 'as it stood at the time' needs an unambiguous instant."""
    with pytest.raises(ValueError):
        CollectorResult(
            source="dns", vendor_ref="x", status="ok",
            fetched_at=datetime(2026, 7, 20, 12, 0, 0),  # naive
            reliability=0.9,
        )


def test_for_vendor_returns_all_rows(store):
    store.put(_sample_result("canva"))
    store.put(_sample_result("canva"))
    store.put(_sample_result("medibank"))
    assert len(store.for_vendor("canva")) == 2
    assert len(store.for_vendor("medibank")) == 1


# --- scores: append-only history (Phase 3 /history + Phase 5 delta detection) ---

def test_scores_are_appended_as_history(store):
    """Re-scoring appends; latest_score returns the newest, history returns all in order."""
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    store.put_score(_score(posture=42, when=t0))
    store.put_score(_score(posture=55, when=t0 + timedelta(days=1)))
    hist = store.score_history("atlassian")
    assert len(hist) == 2
    assert [s.posture for s in hist] == [42, 55]          # chronological
    assert store.latest_score("atlassian").posture == 55  # newest wins
    assert store.latest_score("never-scored") is None


def test_scores_are_append_only(store):
    """A published rating must be reconstructable 'as it stood at the time' (Finding B):
    the scores table rejects UPDATE and DELETE at the database level, like evidence."""
    sid = store.put_score(_score())
    with pytest.raises(Immutable):
        store._conn.execute("UPDATE scores SET grade = 'x' WHERE id = %s", (sid,))
    with pytest.raises(Immutable):
        store._conn.execute("DELETE FROM scores WHERE id = %s", (sid,))


# --- findings: signal-level interpreted evidence (per-signal audit trail, Finding A) ---

def test_findings_persist_and_read_back(store):
    """The observation, its severity/penalty, and the evidence link are all stored and returned."""
    ids = store.put_findings("atlassian", [
        _finding("dmarc", "medium", 8.0, "ev-1"),
        _finding("tls_version", "high", 20.0, "ev-2"),
    ])
    assert len(ids) == 2
    rows = store.findings_for_vendor("atlassian")
    assert {r.signal for r in rows} == {"dmarc", "tls_version"}
    dmarc = next(r for r in rows if r.signal == "dmarc")
    assert dmarc.severity == "medium"
    assert dmarc.penalty == 8.0
    assert dmarc.observed == "p=none"
    assert dmarc.evidence_id == "ev-1"          # links back to the raw receipt
    assert dmarc.content_hash                    # hash-stamped


def test_findings_are_scoped_per_vendor(store):
    store.put_findings("atlassian", [_finding()])
    store.put_findings("snowflake", [_finding(), _finding("spf")])
    assert len(store.findings_for_vendor("atlassian")) == 1
    assert len(store.findings_for_vendor("snowflake")) == 2
    assert store.findings_for_vendor("never-scored") == []


def test_rescoring_a_vendor_returns_only_the_current_run(store):
    """Findings are append-only, so 'the findings for this vendor' would otherwise mean EVERY run
    ever stacked together — re-score a vendor and the scorecard shows each deduction twice,
    reconciling with no published score. The read defaults to the latest run."""
    store.put_findings("atlassian", [_finding("dmarc"), _finding("spf")], run_id="run-1")
    store.put_findings("atlassian", [_finding("dmarc")], run_id="run-2")

    current = store.findings_for_vendor("atlassian")
    assert [r.signal for r in current] == ["dmarc"]
    assert {r.run_id for r in current} == {"run-2"}


def test_the_full_history_is_still_retrievable_for_audit(store):
    """Nothing is deleted — the earlier run stays available, it just isn't the default read."""
    store.put_findings("atlassian", [_finding("dmarc"), _finding("spf")], run_id="run-1")
    store.put_findings("atlassian", [_finding("dmarc")], run_id="run-2")
    assert len(store.findings_for_vendor("atlassian", latest_only=False)) == 3


def test_legacy_rows_without_a_run_id_still_read_back(store):
    """Rows written before run_id existed are all NULL. Null-safe grouping keeps them readable as
    one legacy run instead of silently returning nothing.

    Simulated with a direct INSERT rather than an UPDATE — the append-only trigger correctly
    refuses to let a stored interpretation be rewritten, including by a test."""
    for signal in ("dmarc", "spf"):
        store._conn.execute(
            """INSERT INTO findings
               (id, vendor_ref, evidence_id, source, category, signal, band_key, severity,
                penalty, effective_penalty, occurrences, run_id, observed, event_date,
                is_critical, is_sanctions, note, content_hash, stored_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,NULL,false,false,NULL,%s,%s)""",
            (str(uuid.uuid4()), "atlassian", "ev-1", "dns", "cyber_hygiene_technical", signal,
             "absent", "medium", 8.0, 8.0, 1, "p=none", "hash", utcnow()),
        )
    assert len(store.findings_for_vendor("atlassian")) == 2


def test_findings_are_append_only(store):
    """Findings are the frozen interpretation behind a score — UPDATE/DELETE rejected at DB level."""
    (fid,) = store.put_findings("atlassian", [_finding()])
    with pytest.raises(Immutable):
        store._conn.execute("UPDATE findings SET severity = 'low' WHERE id = %s", (fid,))
    with pytest.raises(Immutable):
        store._conn.execute("DELETE FROM findings WHERE id = %s", (fid,))


def test_sanctions_finding_persists_without_severity(store):
    """A sanctions finding is gate input — stored as evidence, but carries no severity/penalty."""
    nf = NormalizedFinding(
        evidence_id="ev-9", source="ita", category="regulatory_legal_sanctions",
        signal="sanctions_hit", band_key="match", severity=None, penalty=0.0,
        event_date=None, is_critical=False, is_sanctions=True, observed="SDN match",
    )
    store.put_findings("acme", [nf])
    (row,) = store.findings_for_vendor("acme")
    assert row.severity is None
    assert row.is_sanctions is True
    assert row.penalty == 0.0
