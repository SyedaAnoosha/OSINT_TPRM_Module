"""Canonical serialization + the exact payloads that get hashed and stored.

WHY THIS IS ITS OWN MODULE. These functions define the bytes behind every `content_hash` in the
evidence store — they ARE the tamper-evidence, and the same logical record must produce the same
hash on any machine, in any run, forever. They lived inside the SQLite store; that store is gone,
but the hashing contract is not backend-specific, so it lives here where the Postgres store (and
any future one) reads the one definition. A second copy of this logic would be a second, silently
diverging answer to "what did this record hash to".
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .models import CollectorResult

if TYPE_CHECKING:
    from .scoring.normalize import NormalizedFinding


def json_default(o: Any) -> str:
    """Serialize the few non-JSON-native types a collector might leave in `raw`.

    A collector's `raw` is meant to be JSON-native, but a stray datetime should degrade to a
    deterministic ISO string rather than crash the store — one collector must never be able to
    break the legal artefact. Determinism is preserved (same instant -> same text).
    """
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, (set, frozenset)):
        return sorted(o)  # type: ignore[return-value]
    raise TypeError(f"cannot serialize {type(o).__name__} into evidence payload")


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic serialization: sorted keys, compact, UTF-8, no NaN.

    Determinism is the whole point — the same logical payload must always produce the same bytes,
    and therefore the same hash, on any machine in any run.
    """
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False, default=json_default,
    )


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def payload_of(result: CollectorResult) -> dict[str, Any]:
    """The exact dict that gets hashed and stored. `findings` are re-derivable from `raw`, so the
    stored payload is the provenance (raw + how/when/what-version) an auditor needs to reconstruct
    the score."""
    return {
        "source": result.source,
        "vendor_ref": result.vendor_ref,
        "status": result.status,
        "fetched_at": result.fetched_at.isoformat(),
        "source_version": result.source_version,
        "reliability": result.reliability,
        "notes": result.notes,
        "raw": result.raw,
    }


def finding_payload(nf: NormalizedFinding) -> dict[str, Any]:
    """The exact dict hashed and stored for one signal-level finding — everything that fixes how an
    observation became a penalty, so the interpretation is tamper-evident and reconstructible."""
    return {
        "evidence_id": nf.evidence_id,
        "source": nf.source,
        "category": nf.category,
        "signal": nf.signal,
        "band_key": nf.band_key,
        "severity": nf.severity,
        "penalty": nf.penalty,
        "effective_penalty": nf.effective_penalty,
        "occurrences": nf.occurrences,
        "observed": nf.observed,
        "event_date": nf.event_date.isoformat() if nf.event_date else None,
        "is_critical": nf.is_critical,
        "is_sanctions": nf.is_sanctions,
        "note": nf.note,
        "dispute": nf.dispute,
    }
