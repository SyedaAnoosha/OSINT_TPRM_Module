"""The blocked queue, assembled so a person can actually work it.

WHY THIS EXISTS. `blocked_pending_adjudication` counts the queue and nothing shows it. A count is
enough to know there is a problem and useless for fixing one, and the specific failure that follows
is the one the sanctions report already named: *"an 8.8% false-positive rate on household-name public
companies turns adjudication into a rubber stamp."* A queue nobody can work quickly is a queue that
gets cleared without being read, and a rubber-stamped s 16(7) record is worse than no record — it is
a statutory defence built on a decision nobody actually made.

So this module puts the DISCRIMINATING FACTS on the row. For a sanctions block that means: what
matched, at what strength, whether the listed party is an entity or a natural person, which list it
came from, and — the fact that settles most of them in one glance — whether the query token is an
ordinary English word or a coined corporate name. `experian` matching *Experian Holdings, Inc.* and
`wise` matching *Wise Road Capital* are the same match strength and completely different questions.

═══ IT DECIDES NOTHING ═══

**No score is read for its posture, no gate is cleared, nothing is written.** The gate stays human
because s 16(7) makes the human decision the evidence; a module that pre-sorted the queue into
"probably fine" would be making that decision in everything but the record. What it does is
reorder the SAME queue so the cheapest decisions are visible first, and annotate each row with what
a person would otherwise have to go and look up.

The ordering is by inherent exposure, then by how weak the match evidence looks. A critical-tier
relationship blocked on a strong full-name match is the row that matters; a low-tier corpus vendor
blocked on a head match against one common English word is the row that clears in five seconds.
Both stay in the queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .inherent_register import classify as register_classify
from .residual_risk import inherent_tier

#: Ordinary words of the language. A one-word query that is one of these is why `orange.com` collides
#: with ORANGE VOLUNTEERS and `wise.com` with Wise Road Capital, while `experian` and `atlassian`
#: collide with nothing — those are coined names, and a collision on a coined name is real evidence.
#:
#: THIS LIST NEVER SUPPRESSES A MATCH. It annotates one. The distinction matters: a suppression list
#: is a loosening of the gate that grows quietly every time somebody is inconvenienced, and within a
#: year it is the reason a real hit was missed. An annotation changes how long a decision takes and
#: not whether it is made.
_COMMON_WORDS = frozenset({
    "block", "box", "line", "orange", "wise", "square", "stripe", "sage", "monday", "asana",
    "canva", "grab", "zip", "slack", "brex", "judo", "elders", "seek", "iron", "apple", "amber",
    "arrow", "atlas", "beacon", "bridge", "circle", "coin", "crown", "eagle", "falcon", "field",
    "flow", "forge", "gate", "grid", "harbour", "harbor", "lantern", "lark", "lever", "lime",
    "link", "mesa", "north", "oak", "onward", "pace", "pilot", "pine", "prime", "pulse", "quill",
    "ridge", "river", "sail", "shield", "signal", "silver", "spark", "spring", "summit", "swift",
    "tide", "torch", "union", "vault", "wave", "west", "willow", "wren",
})

#: Roughly how much a reader should discount the match before reading it. Ordered weakest first, and
#: every level still blocks — this is a reading aid, not a threshold.
Weakness = str


@dataclass
class BlockedRecord:
    """One row of the queue, with everything needed to decide it on the page."""

    vendor_ref: str
    reason: str | None
    gate: str
    classification: str | None
    inherent_tier: str | None
    query: str | None = None
    screened: bool | None = None
    matches: list[dict[str, Any]] = field(default_factory=list)
    blocked_since: Any = None
    age_days: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def is_sanctions(self) -> bool:
        return self.gate == "sanctions"


def _gate_of(reason: str | None) -> str:
    """Which gate blocked this. Read from the stored reason rather than re-derived, so the queue
    cannot disagree with the record that produced it."""
    if not reason:
        return "unknown"
    head = reason.split(" ", 1)[0].strip().rstrip(":")
    return "sanctions" if "sanction" in head.lower() else head or "unknown"


def _annotate(query: str | None, match: dict[str, Any]) -> list[str]:
    """What a person would otherwise have to go and look up. One line each, no verdicts."""
    notes: list[str] = []
    strength = match.get("match_strength")
    kind = (match.get("type") or "").strip().lower()
    tokens = [t for t in (query or "").split() if t]

    if strength == "full":
        notes.append("FULL-NAME match — the query is this listed party's entire name, minus legal "
                     "suffixes. The strongest evidence this matcher produces.")
    elif strength == "head":
        notes.append("HEAD match — the query is the LEADING words of a longer listed name. Real "
                     "when the leading words are the distinctive part, weak when they are not.")

    if kind == "individual":
        notes.append("THE LISTED PARTY IS A NATURAL PERSON, and the subject here is a company. A "
                     "surname collision is the usual cause. It is still worth a look where the "
                     "company is named after its owner — which is exactly why this is not "
                     "auto-cleared.")

    if len(tokens) == 1 and tokens[0].lower() in _COMMON_WORDS:
        notes.append(f"THE QUERY IS ONE ORDINARY ENGLISH WORD ({tokens[0]!r}). Collisions on common "
                     f"words carry far less information than collisions on coined names — compare "
                     f"'experian', which collides with nothing. Weak evidence; still a decision.")
    elif len(tokens) == 1:
        notes.append(f"The query is a single distinctive token ({tokens[0]!r}) — not an ordinary "
                     f"word, so a collision here is meaningful.")

    alts = match.get("alt_names") or []
    if alts and match.get("name") and query:
        # Matching via an ALIAS rather than the primary name is worth saying out loud: a reader
        # scanning the primary name alone cannot see why the row is here at all.
        q = query.lower()
        if q not in str(match["name"]).lower():
            hit = next((a for a in alts if q in str(a).lower()), None)
            if hit:
                notes.append(f"MATCHED ON AN ALIAS, not the primary name: {hit!r}. The primary "
                             f"name alone does not explain this row.")
    return notes


def build(store: Any) -> list[BlockedRecord]:
    """Every blocked record, richest-context-first. Reads only; writes nothing; clears nothing."""
    from .models import utcnow

    now = utcnow()
    out: list[BlockedRecord] = []

    for score in store.latest_scores_all():
        if not score.blocked:
            continue
        reason = score.blocked_reason
        rec = BlockedRecord(
            vendor_ref=score.vendor_ref,
            reason=reason,
            gate=_gate_of(reason),
            classification=register_classify(score.vendor_ref),
            inherent_tier=None,
            blocked_since=score.computed_at,
            age_days=round((now - score.computed_at).total_seconds() / 86400.0, 1),
        )

        profile = store.latest_profile(score.vendor_ref)
        attrs = store.latest_supplier_attributes(score.vendor_ref) or {}
        rec.inherent_tier = inherent_tier(
            profile.criticality if profile else None, attrs.get("data_access_scope")).tier

        if rec.is_sanctions:
            rows = [e for e in store.for_vendor(score.vendor_ref) if e.source == "ita"]
            rows.sort(key=lambda e: e.fetched_at, reverse=True)
            if rows:
                raw = rows[0].raw or {}
                rec.query = raw.get("query")
                rec.screened = raw.get("screened")
                rec.matches = list(raw.get("matches") or [])
                for m in rec.matches:
                    rec.notes.extend(_annotate(rec.query, m))

        if rec.classification == "not_a_relationship":
            rec.notes.append(
                "THIS REF IS AN INVENTORY DEFECT on the register — a typo, a product, or the "
                "buyer's own domain. There may be no entity behind it to adjudicate at all. Fix "
                "the inventory instead of clearing the gate.")
        elif rec.classification == "corpus":
            rec.notes.append(
                "SEEDED BENCHMARKING VENDOR, not a relationship. It is blocked, so it publishes no "
                "posture and contributes nothing to its peer cohort — which is the actual cost of "
                "leaving this row in the queue.")
        out.append(rec)

    # Exposure first, then age. A queue sorted by weakness would be a queue that reads as a
    # recommendation, and the module refuses to make one.
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4}
    out.sort(key=lambda r: (rank.get(r.inherent_tier, 4), -(r.age_days or 0)))
    return out


def as_dict(records: list[BlockedRecord]) -> dict[str, Any]:
    by_gate: dict[str, int] = {}
    for r in records:
        by_gate[r.gate] = by_gate.get(r.gate, 0) + 1
    return {
        "queue_depth": len(records),
        "by_gate": by_gate,
        "by_classification": {
            k: sum(1 for r in records if r.classification == k)
            for k in ("relationship", "corpus", "not_a_relationship", None)
            if any(r.classification == k for r in records)
        },
        "records": [
            {
                "vendor_ref": r.vendor_ref,
                "gate": r.gate,
                "reason": r.reason,
                "classification": r.classification,
                "inherent_tier": r.inherent_tier,
                "blocked_since": r.blocked_since.isoformat() if r.blocked_since else None,
                "age_days": r.age_days,
                "sanctions": None if not r.is_sanctions else {
                    "query": r.query,
                    "screened": r.screened,
                    "match_count": len(r.matches),
                    "matches": [
                        {"name": m.get("name"), "type": m.get("type"),
                         "strength": m.get("match_strength"), "list": m.get("source"),
                         "alt_names": (m.get("alt_names") or [])[:5]}
                        for m in r.matches
                    ],
                },
                "what_to_check": r.notes,
            }
            for r in records
        ],
        "caveats": [
            "NOTHING HERE CLEARS A GATE. The decision stays human because s 16(7) makes the human "
            "decision the statutory-defence evidence; a queue that pre-sorted itself into "
            "'probably fine' would be making that decision without recording it.",
            "The ordering is by INHERENT EXPOSURE, not by how weak the match looks. A queue sorted "
            "weakest-first would read as a recommendation to clear from the top.",
            "`what_to_check` annotates; it never suppresses. A suppression list grows every time "
            "somebody is inconvenienced by it, and within a year it is why a real hit was missed.",
        ],
    }
