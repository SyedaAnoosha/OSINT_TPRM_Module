"""Validate the real root scoring.yaml (penalty-based posture model), and prove the invariants
are actually enforced."""

from __future__ import annotations

import copy

import pytest

from app.scoring_config import (
    _DOCUMENTATION_ONLY,
    _ENGINE_READS,
    ScoringConfig,
    ScoringConfigError,
    load_scoring_config,
)


def test_real_scoring_yaml_loads_and_validates():
    cfg = load_scoring_config()  # the actual repo-root scoring.yaml
    # MAJOR bumped at E5: 4.x and 5.x postures are different measurements, not the same one
    # moving — see the design notes. E6 is a MINOR bump on top (5.1.0): same axes, same
    # divisor, one signal's banding input changed. `supersedes` must record what it replaced,
    # whatever the current version is.
    assert cfg.version.startswith("5.")
    assert cfg.data.get("supersedes"), "a version with no recorded predecessor is not traceable"
    assert cfg.data["supersedes"] < cfg.version, (
        f"supersedes {cfg.data['supersedes']!r} is not older than version {cfg.version!r}"
    )
    assert "posture" in cfg.direction.lower()
    assert "attack_surface_hygiene" in cfg.category_names()   # was cyber_hygiene_technical (E5)
    assert cfg.planned_signal_count() > 20


def test_severity_penalties_and_grades_readable():
    cfg = load_scoring_config()
    assert cfg.penalty_for("critical") > cfg.penalty_for("high") > cfg.penalty_for("low") > 0
    assert cfg.penalty_for("pass") == 0 and cfg.penalty_for("informational") == 0
    assert cfg.grade_for(100) == "A" and cfg.grade_for(0) == "F"
    # the DMARC ladder maps to severities now. DMARC moved to `identity_email` at E5 — it is one
    # decision at the apex, and Class-B, so it stays apart from the rate-normalised estate signals.
    assert cfg.signal_severity("identity_email", "dmarc", "absent") == "high"
    assert cfg.signal_severity("identity_email", "dmarc", "p_reject") == "pass"


def test_confidence_bands():
    cfg = load_scoring_config()
    assert cfg.confidence_band(0.95) == "High"
    assert cfg.confidence_band(0.75) == "Medium"
    assert cfg.confidence_band(0.30) == "Low"


def _minimal_valid() -> dict:
    return {
        "version": "4.0.0",
        "direction": "100 = strongest posture, 0 = weakest",
        "max_score": 100,
        "severity_penalties": {"critical": 40, "high": 20, "medium": 8, "low": 3, "informational": 0},
        "grades": {"A": {"min": 85}, "F": {"min": 0}},
        "categories": {"cyber_hygiene_technical": {"dmarc": {"absent": "high", "p_reject": "pass"}}},
        # E8 requires a substantive `basis` on every gate, enforced at load — a rule that stops a
        # company being onboarded needs a reason someone can be shown. The minimal fixture carries
        # a real one rather than filler, so it stays an example of a VALID config.
        "gates": {"sanctions": {
            "behaviour": "block",
            "basis": "Autonomous Sanctions Act 2011 (Cth) s16(7) — dealing with a designated "
                     "entity is a criminal offence and the decision is a legal adjudication.",
        }},
    }


def test_penalties_must_be_monotonic(tmp_path):
    bad = copy.deepcopy(_minimal_valid())
    bad["severity_penalties"]["low"] = 999  # low > medium breaks the ordering
    with pytest.raises(ScoringConfigError, match="monotonic"):
        ScoringConfig(bad, tmp_path / "s.yaml")


def test_direction_must_mention_posture(tmp_path):
    bad = copy.deepcopy(_minimal_valid())
    bad["direction"] = "0 = lowest risk, 100 = highest risk"  # the old risk convention
    with pytest.raises(ScoringConfigError):
        ScoringConfig(bad, tmp_path / "s.yaml")


def test_sanctions_gate_must_block(tmp_path):
    bad = copy.deepcopy(_minimal_valid())
    bad["gates"]["sanctions"]["behaviour"] = "penalize"
    with pytest.raises(ScoringConfigError, match="block"):
        ScoringConfig(bad, tmp_path / "s.yaml")


# ------------------------------------------------------- the drift guard (config nothing reads)

def test_config_nothing_reads_is_rejected(tmp_path):
    """The guard that prevents the drift class. A key the engine never reads is a claim the code
    does not honour — exactly how two NIST variables sat inert while the docs advertised them."""
    bad = copy.deepcopy(_minimal_valid())
    bad["supply_chain_weights"] = {"npm": 0.4}     # plausible-looking, read by nothing
    with pytest.raises(ScoringConfigError, match="nothing reads"):
        ScoringConfig(bad, tmp_path / "s.yaml")


def test_documentation_only_keys_are_allowed_but_must_be_declared(tmp_path):
    """Inert-by-design config is fine — it just has to say so in _DOCUMENTATION_ONLY."""
    ok = copy.deepcopy(_minimal_valid())
    ok["held_roadmap"] = {"esg_ethical": "no licence"}
    ok["excluded_signals"] = {"pep_links": "natural persons"}
    ScoringConfig(ok, tmp_path / "s.yaml")        # must not raise


def test_every_key_in_the_real_yaml_is_accounted_for():
    """The real scoring.yaml must classify every key as read-by-the-engine or documentation."""
    cfg = load_scoring_config()
    unclassified = set(cfg.data) - _ENGINE_READS - set(_DOCUMENTATION_ONLY)
    assert not unclassified, f"unclassified scoring.yaml keys: {sorted(unclassified)}"


def test_the_engine_actually_reads_what_we_claim_it_reads():
    """Both directions. Each _ENGINE_READS key must be present in the real file — otherwise the
    registry itself rots and the guard silently stops guarding."""
    cfg = load_scoring_config()
    missing = _ENGINE_READS - set(cfg.data)
    assert not missing, f"_ENGINE_READS lists keys absent from scoring.yaml: {sorted(missing)}"


# --------------------------------------------------------------------- E1: no sector arithmetic
# `industry_profiles` promoted a severity by one step where a sector profile named a cited
# instrument. The discipline around it was careful — promotion-only, one step, capped, anchored —
# but the mechanism is the one the research rejects: dynamic severity adjustment. The same evidence
# scored differently depending on a label WE assigned, which destroys cross-vendor comparability.
#
# The sector obligation was real and survives, as a Compliance Gap FINDING (E9c). See
# the design notes, which captured both `basis:` strings before deletion.


def test_scoring_yaml_declares_no_industry_profiles():
    """Gone from the config, not merely unread. A block nothing reads is the drift this file's
    own `_validate_no_dead_config` exists to prevent."""
    cfg = load_scoring_config()
    assert "industry_profiles" not in cfg.data
    assert "industry_profiles" not in _ENGINE_READS
    assert "industry_profiles" not in _DOCUMENTATION_ONLY


def test_the_promotion_machinery_is_gone_from_the_loader():
    """Deleting the config while leaving the code would let a future edit re-enable sector
    promotion by adding six lines of YAML. Remove the mechanism, not just its inputs."""
    cfg = load_scoring_config()
    for gone in ("promote_severity", "industry_profile", "industry_profiles"):
        assert not hasattr(cfg, gone), f"ScoringConfig.{gone} should have been removed at E1"


# --------------------------------------------------------------------- E2: stop penalising the norm
# DNSSEC sits at 7-18% adoption, CAA near 1.6%, security.txt under 0.25% of domains. Penalising
# their absence penalises the NORM — it charges a vendor for behaving like almost every other
# vendor, which is noise, and it falls hardest on small suppliers. Certification and reporting
# absence is the same shape with a different cause: a tax on audit budget.
#
# These bands become `informational` rather than being deleted. An informational finding still
# produces a NormalizedFinding, so the signal still counts toward coverage and the confidence
# denominator does not move. Positive credit for HAVING them is E9b, once Assurity exists.


def test_reclassified_bands_no_longer_penalise():
    cfg = load_scoring_config()
    for signal, band in [
        ("dnssec", "absent"), ("caa", "absent"), ("security_txt", "absent"),
        ("program_disclosure", "none"), ("program_disclosure", "marketing_only"),
        ("cert_posture", "none_claimed"),
        ("reporting_posture", "none"), ("reporting_posture", "partial"),
    ]:
        cat = next(c for c in cfg.category_names() if signal in cfg.signals_of(c))
        assert cfg.penalty_for(cfg.signal_severity(cat, signal, band)) == 0.0, \
            f"{signal}.{band} still penalises"


def test_disclosure_is_never_punished_more_than_silence():
    """The inversion E2 had to avoid.

    Reclassifying only the ABSENCE band would leave `program_disclosure.marketing_only` at 3 while
    `none` sat at 0 — so a vendor could DELETE their trust page and gain three points. Same for
    `reporting_posture.partial` against `none`. Publishing something imperfect must never cost more
    than publishing nothing, or the model pays vendors to go dark.
    """
    cfg = load_scoring_config()
    for signal, more, less in [
        ("program_disclosure", "marketing_only", "none"),
        ("reporting_posture", "partial", "none"),
    ]:
        cat = next(c for c in cfg.category_names() if signal in cfg.signals_of(c))
        pen = lambda b: cfg.penalty_for(cfg.signal_severity(cat, signal, b))  # noqa: E731
        assert pen(more) <= pen(less), (
            f"{signal}: '{more}' costs {pen(more)} but '{less}' costs {pen(less)} — the model is "
            f"paying this vendor to disclose less"
        )


def test_claim_reliability_bands_deliberately_still_penalise():
    """`cert_posture` keeps `claimed_unverified` and `claimed_expired`, and that is NOT an
    audit-budget tax. Those bands do not charge for lacking a certification — `none_claimed` is
    free now. They charge for ASSERTING one that does not check out, which is a statement about
    the reliability of the vendor's own claims. That is exactly the Compliance Gap's territory
    (E9c), and it is the reason dropping a claim must stay visible rather than simply cheap."""
    cfg = load_scoring_config()
    cat = next(c for c in cfg.category_names() if "cert_posture" in cfg.signals_of(c))
    pen = lambda b: cfg.penalty_for(cfg.signal_severity(cat, "cert_posture", b))  # noqa: E731
    assert pen("none_claimed") == 0.0
    assert pen("claimed_unverified") > 0
    assert pen("claimed_expired") > 0


def test_confidence_denominator_is_unmoved_by_reclassification():
    """The whole reason these bands became `informational` instead of being deleted. A bonus signal
    is still PLANNED AND CHECKED — if the denominator shrank, every vendor's confidence would jump
    for no evidential reason whatsoever."""
    assert load_scoring_config().planned_signal_count() == 27


# --------------------------------------------------------------------- E3: one fact, one charge


def test_the_contact_disclosure_fact_is_charged_exactly_once():
    """RFC 9116's `Contact:` field, a published security address and a VDP path are usually the
    same observation seen three ways — headers_collector emits `security_txt` AND `vd_program`
    from a single fetch, and trust_collector reads the same contact off the trust page.

    Charging all three made governance heavier than any deliberate weighting decision would have.
    Exactly one of the trio may carry a penalty.
    """
    cfg = load_scoring_config()
    charging = []
    for signal in ("security_txt", "contactability", "vd_program"):
        cat = next(c for c in cfg.category_names() if signal in cfg.signals_of(c))
        bands = cfg.signals_of(cat)[signal]
        if any(cfg.penalty_for(sev) > 0 for sev in bands.values()):
            charging.append(signal)
    assert charging == ["vd_program"], (
        f"expected only vd_program to charge for the contact/disclosure fact, got {charging}. "
        f"vd_program is the one the report credits with a causal mechanism: a vendor with no "
        f"disclosure path cannot be TOLD about a vulnerability."
    )


def test_merged_signals_are_still_collected_and_still_count_toward_coverage():
    """`contactability` and `security_txt` keep their place in the model. Deleting them would drop
    planned_signal_count and lift every vendor's confidence for no evidential reason — the check
    still runs, it simply no longer charges twice for what another signal already charged."""
    cfg = load_scoring_config()
    names = {s for c in cfg.category_names() for s in cfg.signals_of(c)}
    assert {"security_txt", "contactability", "vd_program"} <= names
    assert cfg.planned_signal_count() == 27


# --------------------------------------------------------------------- E5: categories + divisor


def _scoring_categories(cfg):
    """Categories that can actually contribute penalty. Context categories cannot, by design."""
    return [c for c in cfg.category_names()
            if any(cfg.penalty_for(sev) > 0
                   for bands in cfg.signals_of(c).values() for sev in bands.values())]


def test_no_signal_appears_in_two_categories():
    """The engine keys penalties on (category, signal). A signal in two categories is charged
    TWICE — silently, with no error and no clue in the receipt."""
    cfg = load_scoring_config()
    seen: dict[str, str] = {}
    for category in cfg.category_names():
        for signal in cfg.signals_of(category):
            assert signal not in seen, f"{signal} in both {seen[signal]} and {category}"
            seen[signal] = category


def test_divisor_preserves_maximum_damage():
    """The half of E5 that silently re-scores everyone if forgotten.

    Maximum damage is (scoring categories x 100) / divisor. Change the category count without the
    divisor and nothing breaks — every score just drifts, because a larger FRACTION of the model
    now has to fail before a vendor bottoms out. Nothing fails loudly; the model simply becomes
    more forgiving than anyone decided it should be.
    """
    cfg = load_scoring_config()
    n = len(_scoring_categories(cfg))
    damage = (n * 100) / cfg.penalty_divisor()
    assert abs(damage - 175) < 1.0, (
        f"{n} scoring categories at divisor {cfg.penalty_divisor()} gives {damage:.1f} points of "
        f"maximum damage, not 175. Re-derive: divisor(n) = n x (4/7)."
    )


def test_every_scoring_category_has_at_least_one_penalising_band():
    """A scoring category with nothing left to charge is a constant, not a category — and it makes
    the divisor wrong, because maximum damage is counted per scoring category."""
    cfg = load_scoring_config()
    for category in _scoring_categories(cfg):
        penalising = [b for bands in cfg.signals_of(category).values()
                      for b, sev in bands.items() if cfg.penalty_for(sev) > 0]
        assert penalising, f"{category} has no penalising band"


def test_context_categories_never_penalise():
    """Context categories exist so the confidence denominator does not move when a signal stops
    charging. If one ever gains a penalising band it has become a SCORING category, and the divisor
    must be re-derived — which this test forces someone to notice."""
    cfg = load_scoring_config()
    for category in ("continuity_context", "assurance_context"):
        for signal, bands in cfg.signals_of(category).items():
            for band, sev in bands.items():
                assert cfg.penalty_for(sev) == 0.0, (
                    f"{category}.{signal}.{band} penalises. Either move it to a scoring category "
                    f"and re-derive the divisor, or make it informational."
                )


def test_the_confidence_denominator_survived_the_restructure():
    """Nine signals stopped charging across E2-E5 and none of them left the model. Deleting them
    would have raised every vendor's confidence for no evidential reason."""
    assert load_scoring_config().planned_signal_count() == 27


def test_regulator_action_cyber_relevance_is_a_recorded_open_item():
    """E5 forced a decision on `regulator_action` and it was made explicitly, not by omission.

    KNOWN DEFECT, ACCEPTED FOR NOW: the collector cannot distinguish cyber enforcement from any
    other kind, so a DOJ antitrust settlement scores identically to an ICO data-protection fine.
    Accepted because it fires on 0 of 5 corpus vendors and the fix is a COLLECTOR change that does
    not belong in the largest re-score in the plan.

    BLOCKING PREREQUISITE FOR E9c. When that lands, this test should fail and be rewritten to
    assert the tagging — which is the point of pinning it here.
    """
    cfg = load_scoring_config()
    cat = next(c for c in cfg.category_names() if "regulator_action" in cfg.signals_of(c))
    assert cat == "compliance_regulatory", (
        "regulator_action belongs with compliance, not adverse media — it is a claim-reliability "
        "fact heading for the Compliance Gap at E9c"
    )
    bands = cfg.signals_of(cat)["regulator_action"]
    assert set(bands) == {"no_action_found", "formal_investigation", "enforcement_action"}, (
        "bands changed — if cyber-relevance tagging has landed, rewrite this test to assert it"
    )
