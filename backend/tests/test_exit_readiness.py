"""P8 — exit readiness and substitutability: what happens if this vendor has to go.

`sole_source × poor Posture` is the single most useful procurement alert this system can raise.
`substitutability` is client-declared, never inferred — same path as `criticality`. Everything else
this module can add comes from public evidence already computed elsewhere: P1's fourth-party
dependencies, the peer cohort size, and a Continuity going-concern flag.
"""

from __future__ import annotations

from app.exit_readiness import as_dict, exit_readiness


# ============================================================ the core alert


def test_sole_source_and_poor_posture_is_the_critical_alert():
    report = exit_readiness("acme", substitutability="sole_source", posture=25)
    assert report.alert_level == "critical"
    assert report.posture_band == "poor"
    assert "SOLE SOURCE, POOR POSTURE" in report.headline()
    assert "single most useful procurement alert" in report.headline()


def test_sole_source_and_weak_posture_is_elevated_not_critical():
    report = exit_readiness("acme", substitutability="sole_source", posture=50)
    assert report.alert_level == "elevated"
    assert report.posture_band == "weak"
    assert "Sole source, weak posture" in report.headline()


def test_sole_source_and_strong_posture_raises_no_alert():
    """A strong posture on a sole-source vendor does not resolve the exposure — it is not scored
    as an alert either, because the module's own caveat says why: posture measures controls, not
    replaceability, and conflating them would bury the signal this module exists to raise."""
    report = exit_readiness("acme", substitutability="sole_source", posture=90)
    assert report.alert_level == "none"
    assert "No exit alert" in report.headline()


def test_a_replaceable_vendor_with_a_poor_posture_raises_no_exit_alert():
    """Poor posture alone is a Posture problem, not an exit problem — `high` substitutability means
    a replacement is not the hard part."""
    report = exit_readiness("acme", substitutability="high", posture=10)
    assert report.alert_level == "none"


def test_undeclared_substitutability_cannot_raise_the_alert_and_says_so():
    """Same rule E10b and P3 apply to their own undeclared inputs: guessing `low` would let every
    un-triaged relationship read as safe, which is the failure in the dangerous direction."""
    report = exit_readiness("acme", substitutability=None, posture=10)
    assert report.alert_level == "none"
    assert "not declared for this relationship" in report.headline()


def test_a_missing_posture_never_crashes_the_band_lookup():
    """Blocked / refused vendors publish no posture — the caller passes `posture=None`, and this
    module must not guess a band for a number that does not exist."""
    report = exit_readiness("acme", substitutability="sole_source", posture=None)
    assert report.posture_band is None
    assert report.alert_level == "none"


# ============================================================ what public evidence can add


def test_fourth_party_dependencies_travel_with_an_exit():
    report = exit_readiness("acme", substitutability="sole_source", posture=90,
                            dependency_providers=["Okta", "AWS"])
    payload = as_dict(report)
    assert payload["what_travels_with_an_exit"]["dependency_providers"] == ["Okta", "AWS"]
    assert "replacement" in payload["what_travels_with_an_exit"]["note"]


def test_no_dependencies_detected_says_so_rather_than_an_empty_list():
    payload = as_dict(exit_readiness("acme", substitutability=None, posture=None))
    assert payload["what_travels_with_an_exit"]["dependency_providers"] == []
    assert "No fourth-party dependencies were detected" in payload["what_travels_with_an_exit"]["note"]


def test_cohort_size_is_evidence_substitutes_exist_never_that_one_is_viable():
    report = exit_readiness("acme", substitutability="low", posture=80, cohort_peer_count=14)
    assert any("14 vendor(s)" in c and "not evidence any one of them is a viable replacement" in c
              for c in report.caveats)


def test_no_cohort_states_the_limit_rather_than_a_silent_zero():
    report = exit_readiness("acme", substitutability="low", posture=80, cohort_peer_count=None)
    assert any("No peer cohort is available" in c for c in report.caveats)


def test_a_going_concern_flag_turns_replaceable_into_urgent():
    report = exit_readiness("acme", substitutability="sole_source", posture=90,
                            going_concern_standing="watch")
    assert any("replace on a deadline" in c for c in report.caveats)


def test_a_sound_standing_adds_no_going_concern_caveat():
    report = exit_readiness("acme", substitutability="sole_source", posture=90,
                            going_concern_standing="sound")
    assert not any("going-concern flag is recorded" in c for c in report.caveats)


# ============================================================ what is NOT derivable


def test_switching_cost_and_lock_in_are_named_as_not_derivable_and_pointed_at_the_evidence_pack():
    payload = as_dict(exit_readiness("acme", substitutability="sole_source", posture=90))
    items = payload["not_derivable_from_osint"]["items"]
    assert "switching cost" in items
    assert "contractual lock-in" in items
    assert "data portability / export terms" in items
    assert "evidence-request-pack" in payload["not_derivable_from_osint"]["next_step"]


def test_substitutability_is_declared_client_side_and_the_caveat_says_so():
    payload = as_dict(exit_readiness("acme", substitutability="sole_source", posture=90))
    assert any("CLIENT-DECLARED, never inferred" in c for c in payload["caveats"])


def test_never_scored_no_posture_arithmetic_anywhere_in_the_shape():
    payload = as_dict(exit_readiness("acme", substitutability="sole_source", posture=25))
    assert payload["posture"] == 25            # copied, not recomputed
    assert "penalty" not in str(payload).lower()
