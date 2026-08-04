"""The blocked queue — and the line between annotating a decision and making it.

The sanctions review named the failure precisely: *"an 8.8% false-positive rate on household-name
public companies turns adjudication into a rubber stamp."* A queue nobody can work quickly gets
cleared without being read, and a rubber-stamped s 16(7) record is worse than no record — it is a
statutory defence resting on a decision nobody actually made.

So this module puts the discriminating facts on the row. What it must never do is use them: no
suppression, no auto-clear, no ordering that reads as a recommendation. These tests hold that line,
because it is the one that would be crossed by a well-meaning change.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import adjudication_queue as aq
from app.models import utcnow


def _ita(query, *matches):
    return SimpleNamespace(source="ita", fetched_at=utcnow(),
                           raw={"query": query, "screened": True, "matches": list(matches)})


def _match(name, *, strength="head", type=None, alt_names=None, source="SDN"):
    return {"name": name, "match_strength": strength, "type": type,
            "alt_names": alt_names or [], "source": source}


class _Store:
    def __init__(self, rows):
        self._rows = rows      # ref -> (blocked_reason, evidence, criticality, scope)

    def latest_scores_all(self):
        return [SimpleNamespace(vendor_ref=r, blocked=True, blocked_reason=v[0],
                                computed_at=utcnow())
                for r, v in self._rows.items()]

    def for_vendor(self, ref):
        return self._rows[ref][1]

    def latest_profile(self, ref):
        crit = self._rows[ref][2]
        return SimpleNamespace(criticality=crit) if crit else None

    def latest_supplier_attributes(self, ref):
        scope = self._rows[ref][3]
        return {"data_access_scope": scope} if scope else None


def _store(**rows):
    return _Store({k: v for k, v in rows.items()})


# ════════════════════════════════════════════════════ it decides nothing


def test_the_queue_never_writes_and_never_clears_a_gate():
    """The gate stays human because s 16(7) makes the human decision the statutory-defence
    evidence. A module that pre-sorted the queue into "probably fine" would be making that
    decision in everything but the record."""
    tree = ast.parse(Path("app/adjudication_queue.py").read_text(encoding="utf-8"))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not {c for c in called if c.startswith("put_") or c.startswith("adjudicat")}


def test_every_blocked_record_reaches_the_queue_however_weak_its_evidence_looks():
    """THE REFUSAL. `_COMMON_WORDS` annotates; it never filters. A suppression list grows every
    time somebody is inconvenienced by it, and within a year it is why a real hit was missed."""
    store = _store(
        wise=("sanctions gate", [_ita("wise", _match("Wise Road Capital"))], None, None),
        experian=("sanctions gate", [_ita("experian", _match("Experian Holdings, Inc."))],
                  None, None),
    )
    refs = {r.vendor_ref for r in aq.build(store)}
    assert refs == {"wise", "experian"}, "no row may be filtered out of the queue"


def test_the_queue_is_ordered_by_exposure_and_not_by_how_weak_the_match_looks():
    """A queue sorted weakest-first reads as a recommendation to clear from the top, which is the
    rubber stamp arriving by a different route."""
    store = _store(
        weak_but_critical=("sanctions gate", [_ita("orange", _match("ORANGE VOLUNTEERS"))],
                           "high", "critical"),
        strong_but_untiered=("sanctions gate",
                             [_ita("experian", _match("Experian Holdings, Inc.",
                                                      strength="full"))], None, None),
    )
    assert [r.vendor_ref for r in aq.build(store)] == \
        ["weak_but_critical", "strong_but_untiered"]


# ════════════════════════════════════════════════════ what it puts on the row


def test_an_ordinary_english_word_query_is_flagged_as_weak_evidence():
    """`orange` colliding with ORANGE VOLUNTEERS and `experian` colliding with Experian Holdings
    are the same match strength and completely different questions."""
    store = _store(orange=("sanctions gate", [_ita("orange", _match("ORANGE VOLUNTEERS"))],
                           None, None))
    notes = aq.build(store)[0].notes
    assert any("ORDINARY ENGLISH WORD" in n for n in notes)


def test_a_coined_name_query_is_flagged_as_meaningful():
    store = _store(experian=("sanctions gate",
                             [_ita("experian", _match("Experian Holdings, Inc."))], None, None))
    notes = aq.build(store)[0].notes
    assert any("single distinctive token" in n for n in notes)
    assert not any("ORDINARY ENGLISH WORD" in n for n in notes)


def test_a_natural_person_listing_is_named_as_such_but_still_queued():
    """A surname collision is the usual cause, and it is still worth a look where the company is
    named after its owner — which is exactly why this is annotated rather than auto-cleared."""
    store = _store(kogan=("sanctions gate",
                          [_ita("kogan", _match("KOGAN, Alexander Borisovich",
                                                type="Individual"))], None, None))
    rec = aq.build(store)[0]
    assert any("NATURAL PERSON" in n for n in rec.notes)
    assert rec.vendor_ref == "kogan"


def test_a_match_via_an_alias_says_so():
    """A reader scanning the primary name alone cannot see why the row is there at all."""
    store = _store(block=("sanctions gate",
                          [_ita("block", _match("NEKA NOVIN", type="Entity",
                                                alt_names=["BLOCK NIROU SUN CO"]))], None, None))
    notes = aq.build(store)[0].notes
    assert any("MATCHED ON AN ALIAS" in n and "BLOCK NIROU SUN CO" in n for n in notes)


def test_a_non_sanctions_gate_is_kept_apart_from_the_sanctions_ones():
    """`colesgroup` was blocked on `entity_dissolved`, not sanctions — and reading it as a
    sanctions false positive was the first thing that went wrong when the queue was worked by
    hand."""
    store = _store(colesgroup=("entity_dissolved — adjudication required: struck off", [],
                               None, None))
    rec = aq.build(store)[0]
    assert rec.gate == "entity_dissolved" and not rec.is_sanctions
    assert aq.as_dict([rec])["records"][0]["sanctions"] is None


def test_an_inventory_defect_says_to_fix_the_inventory_rather_than_clear_the_gate():
    """`jira` is a product, not a vendor. There may be no entity behind the ref to adjudicate at
    all, and clearing the gate would leave the real defect in place."""
    store = _store(jira=("sanctions gate", [_ita("jira")], None, None))
    rec = aq.build(store)[0]
    assert rec.classification == "not_a_relationship"
    assert any("INVENTORY DEFECT" in n for n in rec.notes)


def test_the_summary_counts_by_gate_and_by_classification():
    store = _store(
        wise=("sanctions gate", [_ita("wise", _match("Wise Road Capital"))], None, None),
        colesgroup=("entity_dissolved — struck off", [], None, None),
    )
    body = aq.as_dict(aq.build(store))
    assert body["queue_depth"] == 2
    assert body["by_gate"] == {"sanctions": 1, "entity_dissolved": 1}
    assert any("NOTHING HERE CLEARS A GATE" in c for c in body["caveats"])
