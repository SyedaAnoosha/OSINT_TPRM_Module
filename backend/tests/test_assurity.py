"""E9 — Assurity (the third axis) and the Compliance Gap.

TWO QUESTIONS A BUYER ASKS THAT POSTURE CANNOT ANSWER:

    "How much independent assurance does this vendor actually have?"   -> Assurity (E9a)
    "Do their claims match reality?"                                    -> Compliance Gap (E9c)

The corpus makes the case for separating them better than any argument. `synthetic_smallco`
publishes **posture 97 / assurity 13**: excellent hygiene, every free control in place, and no
externally verifiable evidence of an audited security programme. Before E9 the model expressed
that by SUBTRACTING — `cert_posture.none_claimed` cost 8 points and fired on five of five real
vendors, which is a tax on audit budget rather than a measure of risk. E2 stopped the charging.
This is the half that was always missing.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from app.assurity import assurity_report, sigmoid
from app.compliance_gap import compliance_gaps
from app.scoring_config import ScoringConfig, ScoringConfigError, get_scoring_config
from tests.test_corpus import AS_AT, load_fixture

_YAML = Path(__file__).resolve().parents[2] / "scoring.yaml"


def _raw() -> dict:
    return copy.deepcopy(yaml.safe_load(_YAML.read_text(encoding="utf-8")))


class _F:
    """Minimal stand-in for a NormalizedFinding — the modules read five attributes.

    `observed` defaults to the band, which is right for most signals. For `cert_posture` it is the
    list of certifications the trust page actually named, and that distinction is the whole of the
    E9c claim-attribution fix: the band says a certification was claimed, never which one.
    """

    def __init__(self, signal: str, band_key: str, evidence_id: str | None = "ev-1",
                 observed: str | None = None, value: object = None):
        self.signal, self.band_key, self.evidence_id = signal, band_key, evidence_id
        self.observed = band_key if observed is None else observed
        self.value_snapshot = value


def _claims(*certs: str) -> _F:
    """A `cert_posture` finding shaped the way the trust collector emits it."""
    return _F("cert_posture", "claimed_unverified", observed=", ".join(certs),
              value={"certs": list(certs)})


def _normalized(ref: str):  # noqa: ANN201
    from app.scoring import ScoringEngine

    vendor, results = load_fixture(ref)
    return ScoringEngine().score(vendor, results, now=AS_AT)


# --------------------------------------------------------------------- E9a: absence never subtracts


def test_absence_never_subtracts_and_the_loader_enforces_it():
    """The whole argument for a separate axis. A vendor without certifications has UNEVIDENCED
    security, not bad security — and a negative credit would reintroduce E2's audit-budget tax one
    axis over, where nobody is watching for it."""
    cfg = get_scoring_config()
    for signal, table in cfg.data["assurity"]["credit"].items():
        for band, value in table.items():
            assert value >= 0, f"assurity.credit.{signal}.{band} is negative"

    data = _raw()
    data["assurity"]["credit"]["cert_posture"]["none_claimed"] = -0.5
    with pytest.raises(ScoringConfigError, match="Absence never subtracts"):
        ScoringConfig(data, _YAML)


def test_a_vendor_with_nothing_observable_sits_at_the_floor_not_at_zero():
    """Unevidenced is not disproved. A 0 would read as "audited and failed", which is a different
    and much stronger claim than anything we observed."""
    nothing = [_F(s, b) for s, b in [
        ("cert_posture", "none_claimed"), ("reporting_posture", "none"),
        ("program_disclosure", "none"), ("vd_program", "none"),
        ("contactability", "none_published"), ("security_txt", "absent"),
    ]]
    report = assurity_report("acme", nothing)
    assert report.score is not None
    assert 0 < report.score < 35, f"floor landed at {report.score}"
    assert report.inputs == [], "nothing observable should credit nothing"
    assert any("unevidenced, not because they were examined and failed" in c
               for c in report.caveats)


def test_more_assurance_scores_higher_and_the_curve_flattens():
    """Bounded without a cliff: the twentieth certification cannot buy what the second did, and no
    vendor is ever pinned at 0 or 100 — which is the compression defect E13 is being written to fix
    for Posture, avoided here by construction."""
    def score(*pairs: tuple[str, str]) -> int:
        base = [_F(s, b) for s, b in pairs]
        base += [_F("program_disclosure", "none"), _F("security_txt", "absent")]
        return assurity_report("acme", base).score

    none = score(("cert_posture", "none_claimed"), ("reporting_posture", "none"))
    some = score(("cert_posture", "claimed_unverified"), ("reporting_posture", "partial"))
    full = score(("cert_posture", "registry_corroborated"), ("reporting_posture", "substantive"))
    assert none < some < full
    assert full < 100 and none > 0, "the sigmoid must not pin either end"


def test_a_corroborated_certification_outweighs_an_unverified_claim():
    """The distinction the axis exists to make. A claim we could not corroborate is worth
    something — a vendor who publishes it has at least committed to it — but it is not the same
    evidence as a registry-verifiable certification."""
    credit = get_scoring_config().data["assurity"]["credit"]["cert_posture"]
    assert credit["registry_corroborated"] > credit["claimed_unverified"] * 3


def test_too_few_observations_publish_nothing():
    """`2 of 3` assembled from whichever checks happened to return is the same false precision as
    a median over three peers — the discipline targets.py already applies."""
    report = assurity_report("acme", [_F("cert_posture", "registry_corroborated")])
    assert report.score is None
    assert report.published is False
    assert any("false precision" in c for c in report.caveats)


def test_assurity_is_never_confused_with_posture():
    """The caveat is not decoration. A low Assurity next to a high Posture is the most misreadable
    pair on the card, and `synthetic_smallco` is exactly that vendor."""
    out = _normalized("synthetic_smallco")
    report = assurity_report("synthetic_smallco", out.normalized)
    assert out.score.posture >= 95 and report.score <= 25, (
        "smallco should be the split case: excellent free hygiene, no independent assurance"
    )
    assert any("must never be read as a posture score" in c for c in report.caveats)


def test_assurity_cannot_move_a_posture_score():
    """Structural, not behavioural: the engine never imports it. Credit for publishing a trust page
    must not buy back points lost to an expired certificate."""
    import inspect

    from app.scoring import engine

    source = inspect.getsource(engine)
    assert "assurity" not in source.lower(), (
        "the posture engine references assurity — the axes must stay separate"
    )


def test_sigmoid_is_stable_at_the_extremes():
    """Written to avoid exp() overflow on large negative input, which is reachable if a deployment
    sets a very low intercept."""
    assert sigmoid(-1000) == pytest.approx(0.0, abs=1e-9)
    assert sigmoid(1000) == pytest.approx(1.0, abs=1e-9)
    assert sigmoid(0) == pytest.approx(0.5)


def test_every_signal_e2_parked_at_informational_gained_positive_credit():
    """E9b's exit criterion, and the boundary that goes with it.

    E2 stopped charging for the norm; E9b is the half that was always missing — those signals now
    EARN on the assurance axis instead of costing on the security one. But not every informational
    band belongs here, and the ones that do not are informative about where the axes sit:

      * `subdomain_estate` is a DENOMINATOR (E6), not an assurance claim. A large estate is not
        evidence of an audit.
      * `entity_status`, `entity_existence`, `entity_maturity`, `domain_registration` are
        CONTINUITY (E4). Whether a company will still exist next year is a going-concern question,
        and crediting it here would make Assurity a second, quieter solvency score.

    Asserted rather than left to inspection so that "add credits for the remaining informational
    bands" reads as the mistake it would be.
    """
    cfg = get_scoring_config()
    credit = cfg.data["assurity"]["credit"]
    informational = {
        signal
        for cat in cfg.categories
        for signal, bands in cfg.signals_of(cat).items()
        if any(sev == "informational" for sev in bands.values())
    }
    assurance = {s for s in informational if cfg.category_of(s) in ("assurance_context",
                                                                   "compliance_regulatory",
                                                                   "transparency",
                                                                   "attack_surface_hygiene")}
    # Every assurance-shaped informational signal earns, except the footprint denominator.
    for signal in assurance - {"subdomain_estate"}:
        assert signal in credit, f"{signal} was parked at informational and earns nothing"

    for signal in ("entity_status", "entity_existence", "entity_maturity", "domain_registration"):
        assert signal not in credit, (
            f"{signal} is CONTINUITY (E4). Crediting going-concern here would make Assurity a "
            f"second, quieter solvency score"
        )
    assert "subdomain_estate" not in credit, "a large estate is not evidence of an audit"


# --------------------------------------------------------------------- E9c: the Compliance Gap


def test_the_sector_expectation_returns_as_a_finding_not_as_a_penalty():
    """E1 deleted `industry_profiles` because it promoted a SEVERITY — the same evidence scoring
    differently because of a label we assigned. The obligation was never the problem.

        "This DMARC finding is worth more points."      <- an opinion wearing a number
        "Vendor is APRA-regulated and publishes no      <- disputable, citable, actionable
         DMARC record; CPS 234 requires ..."
    """
    findings = [_F("dmarc", "absent"), _F("spf", "absent")]
    report = compliance_gaps("acme", findings, sector="financial_services")

    assert report.gap_count == 2
    gap = next(g for g in report.gaps if g.signal == "dmarc")
    assert gap.applies_because == "bound_by_sector"
    assert "CPS 234" in gap.basis
    assert "business email compromise" in gap.expectation.lower()
    assert "dmarc = absent" in gap.cited().lower()
    assert any("does not change the posture score" in c for c in report.caveats)


def test_the_same_finding_in_another_sector_produces_no_gap():
    """The correction E1 made, from the other side. A farm supplier without DMARC has a hygiene
    gap; a bank without DMARC has a hygiene gap AND a regulatory one. The FINDING is identical and
    scores identically — only the obligation differs."""
    findings = [_F("dmarc", "absent")]
    assert compliance_gaps("acme", findings, sector="financial_services").gap_count == 1
    assert compliance_gaps("acme", findings, sector="agriculture").gap_count == 0


def test_a_vendor_who_asserts_a_standard_is_measured_against_it():
    """The claim-reliability case, and the strongest form of this finding: the vendor chose the
    standard. It is high-signal precisely because the way to game it is to drop the claim, which
    is itself informative."""
    findings = [_claims("ISO 27001"), _F("tls_version", "tls_10_or_11")]
    report = compliance_gaps("acme", findings)          # no sector — asserted only

    assert report.gap_count == 1
    gap = report.gaps[0]
    assert gap.framework == "iso_27001_asserted"
    assert gap.applies_because == "asserted_by_vendor"
    assert "A.8.24" in gap.expectation


def test_a_vendor_who_claims_nothing_is_not_measured_against_a_standard_they_never_cited():
    """Asserting nothing is not a gap. Holding a vendor to ISO 27001 because we think they ought
    to be certified would be exactly the opinion E1 removed."""
    findings = [_F("cert_posture", "none_claimed"), _F("tls_version", "tls_10_or_11")]
    assert compliance_gaps("acme", findings).gap_count == 0


def test_a_vendor_is_never_measured_against_a_standard_they_did_not_name():
    """THE DEFECT E9c SHIPPED WITH, asserted so it cannot come back.

    `cert_posture` bands say `claimed_unverified` — they do not say WHICH standard was claimed. So
    matching an asserted framework on the band alone fired every asserted framework for any vendor
    claiming any certification: a vendor whose trust page says SOC 2 and nothing else was published
    as "asserts ISO/IEC 27001:2022, observed failing A.8.24". That is us putting a claim in the
    vendor's mouth and then finding them short against it — the same failure as `industry_profiles`
    one layer over, and the more damaging half, because a false compliance assertion about a named
    third party is the sort of thing that ends up in front of their lawyer.
    """
    findings = [_claims("SOC 2"), _F("tls_version", "tls_10_or_11")]
    report = compliance_gaps("acme", findings)

    assert {g.framework for g in report.gaps} == {"soc2_asserted"}
    assert "iso_27001_asserted" not in report.frameworks_considered
    assert "pci_dss_asserted" not in report.frameworks_considered
    assert report.gaps[0].applies_detail == "vendor asserts: SOC 2"


def test_every_asserted_framework_must_name_the_claim_it_matches():
    """Enforced at LOAD, because the failure is invisible at serve time: the report reads as a
    confident finding either way, and only the vendor knows they never made the claim."""
    data = _raw()
    data["compliance_frameworks"]["iso_27001_asserted"]["asserted_by"].pop("claim_contains")
    with pytest.raises(ScoringConfigError, match="claim_contains"):
        ScoringConfig(data, _YAML)


def test_a_vendor_asserting_several_standards_is_measured_against_each():
    """Three frameworks, one weakness, three genuinely separate claim-reliability problems. All
    three are REPORTED — a buyer should see each — and the deduplication happens where the
    arithmetic is, not by hiding findings."""
    findings = [_claims("ISO 27001", "SOC 2", "PCI DSS"), _F("tls_version", "tls_10_or_11")]
    report = compliance_gaps("acme", findings)

    assert {g.framework for g in report.gaps} == {
        "iso_27001_asserted", "soc2_asserted", "pci_dss_asserted"}
    assert report.gap_count == 3
    assert report.distinct_observations == 1


def test_every_gap_carries_a_citation_and_names_why_the_framework_applies():
    """The two grounds are kept apart because they carry different weight in a conversation: one
    is a legal obligation the vendor cannot decline, the other is their own marketing."""
    report = compliance_gaps("acme", [_F("dmarc", "absent")], sector="healthcare")
    for gap in report.gaps:
        assert gap.basis and len(gap.basis) > 40
        assert gap.applies_because in ("bound_by_sector", "asserted_by_vendor")
        assert gap.applies_detail
        assert gap.evidence_id, "a gap with no receipt cannot be reconstructed"


def test_no_sector_is_disclosed_rather_than_assumed():
    """Regulatory obligations are a property of the buyer's relationship with the vendor. Inferring
    one from public data would be re-inventing `industry_profiles` with extra steps."""
    report = compliance_gaps("acme", [_F("dmarc", "absent")])
    assert any("No sector was supplied" in c for c in report.caveats)


def test_a_framework_without_a_named_instrument_fails_the_loader():
    """The guard that keeps this from becoming what industry_profiles was: a plausible expectation
    with an official-looking citation, asserted by us."""
    data = _raw()
    data["compliance_frameworks"]["apra_cps_234"]["basis"] = "regulated"
    with pytest.raises(ScoringConfigError, match="substantive `basis`"):
        ScoringConfig(data, _YAML)


def test_a_control_naming_a_band_that_does_not_exist_fails_the_loader():
    data = _raw()
    data["compliance_frameworks"]["apra_cps_234"]["controls"]["dmarc"]["failing_bands"] = ["invented"]
    with pytest.raises(ScoringConfigError, match="bands that do not exist"):
        ScoringConfig(data, _YAML)


def test_a_framework_that_can_never_apply_fails_the_loader():
    data = _raw()
    data["compliance_frameworks"]["iso_27001_asserted"].pop("asserted_by")
    with pytest.raises(ScoringConfigError, match="can never apply"):
        ScoringConfig(data, _YAML)


# ------------------------------------------------- E9c: one sector vocabulary, not two


def test_a_framework_bound_to_a_sector_nobody_can_be_is_refused_at_load():
    """`banking` shipped in `applies_to_sectors` while cohorts key on `financial_services`, so the
    same vendor got the APRA framework or a peer group depending on which word the intake form
    captured — and the compliance half failed SILENTLY IN THE UNSAFE DIRECTION: no gaps found,
    which a reader takes as no obligations breached."""
    data = _raw()
    data["compliance_frameworks"]["apra_cps_234"]["applies_to_sectors"] = ["banking"]
    with pytest.raises(ScoringConfigError, match="controlled vocabulary"):
        ScoringConfig(data, _YAML)


def test_client_spellings_resolve_to_the_canonical_sector():
    """Aliases are INPUT HANDLING, not vocabulary. Rejecting `banking` outright would just move the
    failure to the intake form, where nobody is watching."""
    for spelling in ("banking", "Banking", "superannuation", "financial services", "FinTech"):
        report = compliance_gaps("acme", [_F("dmarc", "absent")], sector=spelling)
        assert report.gap_count == 1, f"{spelling!r} did not resolve to financial_services"
        assert report.gaps[0].applies_detail == "sector: financial_services"


def test_an_unrecognised_sector_says_so_instead_of_reporting_a_clean_bill():
    """The unsafe-direction failure, stated. "We do not model your industry" and "your vendor
    breaches nothing" look identical on a page, and only one of them is true."""
    report = compliance_gaps("acme", [_F("dmarc", "absent")], sector="widget_manufacturing")
    assert report.gap_count == 0
    assert any("not one this system recognises" in c for c in report.caveats)
    assert any("do not read the absence" in c for c in report.caveats)


def test_every_report_states_that_no_gaps_found_is_not_no_obligations():
    """Coverage is partial by construction and the absence of a gap is weak evidence. The
    disclosure is emitted mechanically, never left to whoever writes the report."""
    for sector in (None, "financial_services", "retail"):
        report = compliance_gaps("acme", [_F("dmarc", "p_reject")], sector=sector)
        assert any("NO GAPS FOUND DOES NOT MEAN NO OBLIGATIONS EXIST" in c for c in report.caveats)


def test_a_gap_against_an_asserted_framework_discloses_that_scope_is_unmodelled():
    """E9c open question 4, answered by disclosure rather than by modelling. A certificate covers a
    defined scope that may exclude the product being bought, and trust pages rarely publish it."""
    report = compliance_gaps("acme", [_claims("ISO 27001"), _F("tls_version", "tls_10_or_11")])
    assert any("defined scope" in c for c in report.caveats)


# ------------------------------------------------- E9c: the shipped framework library


def test_every_asserted_framework_can_actually_be_claimed_by_a_collector():
    """A framework whose claim string no collector can ever produce fires for nobody while reading
    as coverage — the same dead-config failure `_validate_no_dead_config` catches for penalties,
    which is why this asserts against the collector's table rather than against a list here."""
    from app.collectors.trust_collector import _CERTS

    detectable = {c.lower() for c in _CERTS}
    for key, spec in get_scoring_config().data["compliance_frameworks"].items():
        asserted = spec.get("asserted_by")
        if not asserted:
            continue
        claims = {c.lower() for c in asserted["claim_contains"]}
        assert claims & detectable, (
            f"{key} matches on {sorted(claims)}, none of which any collector emits — it can "
            f"never fire, and a framework that cannot fire reads as coverage and provides none"
        )


def test_no_framework_rests_a_control_on_a_product_line_keyword_match():
    """One evidence standard, applied uniformly.

    E8 refused to gate on `kev_listed_cve` because it is a keyword match against a PRODUCT LINE,
    not against this vendor's deployed version. A published compliance finding is very nearly as
    consequential as a gate — it tells a named third party they are short against a named legal
    instrument — so the same evidence bar applies. PCI DSS Req 6.3.3 and Essential Eight ML1 both
    genuinely cover patching and both are excluded here for this reason. If that bar is ever
    lowered it must be lowered deliberately, for every framework at once, not for whichever one
    needed the coverage.
    """
    for key, spec in get_scoring_config().data["compliance_frameworks"].items():
        controls = set(spec.get("controls") or {})
        assert not (controls & {"kev_listed_cve", "nvd_cve"}), (
            f"{key} rests a compliance expectation on a product-line keyword match"
        )


def test_a_disabled_framework_states_why_and_says_so_on_the_report():
    """Declared and off is a POSITION, and it beats silence: the reason is reviewable, the research
    is not repeated, and switching it on is a one-line change once the evidence exists. It is the
    same pattern `gates:` uses for `kev_overdue`."""
    spec = get_scoring_config().data["compliance_frameworks"]["acsc_essential_eight"]
    assert spec["enabled"] is False
    assert len(spec["disabled_because"]) > 40

    report = compliance_gaps("acme", [_F("cert_posture", "none_claimed")], sector="government")
    assert report.gap_count == 0
    assert any("modelled but NOT ASSESSED" in c for c in report.caveats)


def test_a_disabled_framework_that_states_no_reason_fails_the_loader():
    data = _raw()
    data["compliance_frameworks"]["acsc_essential_eight"].pop("disabled_because")
    with pytest.raises(ScoringConfigError, match="disabled_because"):
        ScoringConfig(data, _YAML)


def test_cps_234_and_cps_230_are_separate_obligations():
    """Two prudential standards, different subject matter and different commencement dates. Rolled
    into one row a reader could not tell which obligation a gap sat under, and the vendor could not
    dispute one without arguing about the other. CPS 230 is also the one that speaks directly about
    MATERIAL SERVICE PROVIDERS — which is what every vendor assessed here is."""
    findings = [_F("dmarc", "absent"), _F("contactability", "none_published")]
    report = compliance_gaps("acme", findings, sector="financial_services")

    by_fw = {g.framework: g for g in report.gaps}
    assert by_fw["apra_cps_234"].signal == "dmarc"
    assert by_fw["apra_cps_230"].signal == "contactability"
    assert "1 July 2019" in by_fw["apra_cps_234"].basis
    assert "1 July 2026" in by_fw["apra_cps_230"].basis
    assert "material service provider" in by_fw["apra_cps_230"].basis.lower()


def test_soci_applies_only_where_the_sector_really_is_the_asset_class():
    """The Act binds RESPONSIBLE ENTITIES FOR DECLARED ASSETS, which is an entity-level fact, not
    an industry. For electricity, gas, water and telecommunications the mapping is close to total.
    For "data storage or processing" it is a narrow subset of `technology`, and applying CIRMP to
    every technology vendor because some are critical infrastructure is the industry_profiles error
    exactly — our label, published as their legal obligation."""
    failing = [_F("cert_posture", "none_claimed"), _F("reporting_posture", "none")]
    for sector in ("utilities", "telecommunications"):
        assert compliance_gaps("acme", failing, sector=sector).gap_count == 2
    for sector in ("technology", "retail", "logistics"):
        gaps = compliance_gaps("acme", failing, sector=sector).gaps
        assert not any(g.framework == "soci_critical_infrastructure" for g in gaps), (
            f"SOCI applied to {sector} on a sector proxy that does not hold"
        )


def test_the_cloud_extensions_are_one_framework_not_two():
    """27017 and 27018 are separate standards claimed as a pair, sharing every observable control.
    Two entries would emit two gaps for one observation and one conversation — the duplicate-gap
    problem, avoided by not creating it."""
    report = compliance_gaps("acme", [_claims("ISO 27017", "ISO 27018"),
                                      _F("tls_version", "tls_10_or_11")])
    assert [g.framework for g in report.gaps] == ["iso_27017_27018_asserted"]


# --------------------------------------------------------------------- the two axes together


def test_a_compliance_gap_reduces_assurity_and_nothing_else():
    """The ONLY thing that subtracts on this axis. A gap is not an absence: it is the vendor
    asserting a framework and being observed failing one of its controls."""
    findings = [_F(s, b) for s, b in [
        ("cert_posture", "registry_corroborated"), ("reporting_posture", "substantive"),
        ("program_disclosure", "detailed_policies"), ("vd_program", "bug_bounty"),
    ]]
    clean = assurity_report("acme", findings, compliance_gap_count=0)
    gapped = assurity_report("acme", findings, compliance_gap_count=3)

    assert gapped.score < clean.score
    assert gapped.gap_penalty > 0
    assert any("claim-reliability" in c for c in gapped.caveats)


def test_claiming_more_frameworks_never_costs_more_for_the_same_weakness():
    """E9c open question 3, answered where the arithmetic is.

    A vendor asserting ISO 27001, SOC 2 and PCI DSS while negotiating TLS 1.0 breaches three
    frameworks with ONE weakness. Charging the axis three times would mean a vendor who publishes
    more certifications scores lower than one who publishes fewer and has the identical estate —
    which inverts what this axis measures, since publishing is the transparency it rewards
    everywhere else. It is also E3's rule (one fact, charged once) applied one axis over.
    """
    tls = _F("tls_version", "tls_10_or_11")
    modest = compliance_gaps("acme", [_claims("ISO 27001"), tls])
    forthcoming = compliance_gaps("acme", [_claims("ISO 27001", "SOC 2", "PCI DSS"), tls])

    assert forthcoming.gap_count > modest.gap_count, "all three gaps must still be reported"
    assert forthcoming.distinct_observations == modest.distinct_observations == 1

    base = [_F("reporting_posture", "substantive"), _F("program_disclosure", "detailed_policies"),
            _F("vd_program", "bug_bounty")]
    a = assurity_report("acme", base, compliance_gap_count=modest.distinct_observations)
    b = assurity_report("acme", base, compliance_gap_count=forthcoming.distinct_observations)
    assert a.score == b.score


def test_the_corpus_shows_the_axes_genuinely_disagree():
    """If Assurity simply tracked Posture it would be a second name for one measurement. The
    interesting vendors are the ones where the two disagree, and the corpus contains them."""
    pairs = {}
    for ref in ("synthetic_smallco", "myob", "synthetic_floor"):
        out = _normalized(ref)
        gaps = compliance_gaps(ref, out.normalized, sector="financial_services")
        rep = assurity_report(ref, out.normalized, compliance_gap_count=gaps.gap_count)
        pairs[ref] = (out.score.posture, rep.score)

    posture_order = sorted(pairs, key=lambda r: -pairs[r][0])
    assurity_order = sorted(pairs, key=lambda r: -pairs[r][1])
    assert posture_order != assurity_order, (
        f"the two axes rank identically ({pairs}) — one of them is redundant"
    )
    # The specific disagreement worth naming: excellent hygiene, no independent assurance.
    p, a = pairs["synthetic_smallco"]
    assert p > 90 and a < 30
