"""E12 — whether the fan-out can be switched on, answered by measurement rather than by assertion.

`estate.probe_cap` has shipped at 1 since E12 was built, described as *"a capacity and resourcing
decision rather than a technical design problem."* That framing is half right, and the missing half
is the point of this module: the fan-out's input is certificate transparency, **CT availability is
not a constant**, and a cap raised on a day when CT is answering looks free while the same cap on a
day it is not costs every vendor confidence and returns nothing.

The two rules under test are the ones a future "just turn it on" change would break:

  * READY is non-compensatory. Availability alone is not enough — no vendor that publishes a
    posture today may stop publishing one, and no amount of estate coverage elsewhere compensates
    a buyer for losing a vendor's posture entirely.
  * The confidence fall for vendors with no estate is CORRECT and must not be engineered away.
    Rebasing the denominator per vendor is the move `assessment_depth.py` refuses for P5's depths.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import estate_readiness as er
from app.models import utcnow


def _ct(names):
    return SimpleNamespace(source="ct", fetched_at=utcnow(),
                           raw={"unique_subdomains": names, "ct_source": "certspotter"})


class _Store:
    def __init__(self, vendors):
        # ref -> (estate_size | None, confidence)
        self.vendors = vendors

    def latest_scores_all(self):
        return [SimpleNamespace(vendor_ref=r, blocked=False, refused=False,
                                overall_confidence=c, computed_at=utcnow())
                for r, (_, c) in self.vendors.items()]

    def for_vendor(self, ref):
        size = self.vendors[ref][0]
        return [_ct(size)] if size is not None else []


def test_a_vendor_with_one_name_has_no_estate_to_sample():
    """A rate of "0 of 1" is not a rate, and probing the single name is the apex again."""
    r = er.measure(_Store({"a": (1, 0.8), "b": (40, 0.8)}))
    assert r.with_usable_estate == 1


def test_availability_below_the_threshold_is_not_ready():
    r = er.measure(_Store({f"v{i}": (None, 0.9) for i in range(9)} | {"v9": (50, 0.9)}))
    assert r.availability == pytest.approx(0.1)
    assert not r.ready


def test_ready_requires_availability_AND_nobody_going_dark():
    """NON-COMPENSATORY, and the second condition is not a threshold to trade against the first.
    A vendor going dark is the loss of the number, not a worse number."""
    r = er.EstateReadiness(vendors=10, with_ct_row=10, with_usable_estate=9,
                           estate_sizes=[40] * 9)
    assert r.ready

    r.would_go_dark = ["somebody"]
    assert not r.ready, "one vendor losing its posture cannot be bought off with coverage elsewhere"
    assert "DO NOT SWITCH ON" in r.verdict()


def test_a_vendor_close_to_the_ghost_floor_is_projected_dark_before_the_switch_is_thrown():
    """THE HARD STOP, found by projection rather than by a buyer noticing a card went blank.

    A vendor with no estate gains two PLANNED signals it cannot cover, so its ratio falls; one WITH
    an estate gains them as covered too, so its ratio barely moves. Only the first can go dark.
    """
    r = er.measure(_Store({
        "no_estate_near_floor": (None, 0.42),
        "no_estate_comfortable": (None, 0.90),
        "has_estate_near_floor": (60, 0.42),
    }))
    assert r.would_go_dark == ["no_estate_near_floor"]


def test_the_verdict_names_the_unblocker_rather_than_the_symptom():
    """The resourcing item is a CREDENTIAL, not capacity. A verdict that said "raise the cap when
    ready" would send somebody to tune the wrong number."""
    r = er.measure(_Store({f"v{i}": (None, 0.9) for i in range(10)}))
    verdict = r.verdict()
    assert "NOT READY" in verdict
    assert "API KEY" in verdict and "not a bigger cap" in verdict


def test_the_probe_budget_is_reported_per_candidate_cap():
    """`_validate_estate` refuses an absurd cap at startup; this is how somebody sees the cost
    BEFORE writing one into the config."""
    r = er.measure(_Store({"a": (500, 0.9), "b": (10, 0.9)}))
    # two handshakes per host, capped per vendor
    assert r.probes_per_sweep(25) == 2 * (25 + 10)
    assert r.probes_per_sweep(5) == 2 * (5 + 5)


def test_relationships_are_counted_apart_from_the_seeded_corpus():
    """The book-wide figure is dominated by the 114-vendor corpus, and a feature can be worth
    switching on for the vendors somebody actually buys from even when the corpus drags the average
    down. Averaging the two into one number hides both."""
    from app.inherent_register import relationships

    rel = relationships()[0].ref
    r = er.measure(_Store({rel: (60, 0.9), "some-corpus-vendor": (None, 0.9)}))
    assert r.relationships == 1 and r.relationships_with_estate == 1
    assert r.relationship_availability == 1.0
    assert r.availability == 0.5


def test_the_shipped_cap_is_still_one_and_the_config_says_why():
    """A config value that changed without the basis changing is the drift `_validate_no_dead_config`
    exists to catch, one level up. If somebody raises the cap, this test should fail until they
    have written down what they measured."""
    from app.scoring_config import get_scoring_config

    cfg = get_scoring_config()
    assert cfg.estate_probe_cap() == 1
    basis = Path("../scoring.yaml").read_text(encoding="utf-8")
    block = basis.split("\nestate:", 1)[1].split("\ngates:", 1)[0]
    assert "estate_readiness" in block, "the cap's basis must cite the measurement that set it"


def test_the_estate_signals_are_unreachable_at_cap_one_and_leave_the_denominator():
    """The original E12 finding, still holding: adding the two rates to the model dropped every
    corpus vendor's coverage ~7% while `probe_cap: 1` guaranteed no collector could emit them.
    Absent evidence lowers confidence; UNPRODUCIBLE evidence must not."""
    from app.scoring_config import get_scoring_config

    cfg = get_scoring_config()
    unreachable = cfg.unreachable_signals()
    assert {"estate_tls_legacy", "estate_cert_expired"} <= unreachable
    assert not any(s in unreachable for s in ("tls_version", "dmarc"))


def test_the_module_reads_stored_evidence_and_never_re_queries_ct():
    """Asking CT 146 more times to find out whether CT is rate-limiting us would be a strange way
    to answer the question, and it would spend the budget the measurement exists to protect."""
    tree = ast.parse(Path("app/estate_readiness.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not {m for m in imported if "collector" in m or m == "pipeline"}
