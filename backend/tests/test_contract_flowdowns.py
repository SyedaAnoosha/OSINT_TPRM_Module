"""P4 — contract flow-downs: findings become drafting points procurement can act on.

Seven fixed observation families, each mapped to one suggested protection: no published
incident-response route, unverifiable audit claims, a portfolio-level fourth-party single point of
failure, a going-concern flag, thin evidence coverage, a KEV product-line match, and P8's
client-declared substitutability. Argued over
once in `contract_flowdowns.py` and held constant — the same discipline `recommend.py` and
`residual_risk.py` apply for the same reason.
"""

from __future__ import annotations

import pytest

from app.continuity import ContinuityFlag
from app.contract_flowdowns import TABLE_VERSION, as_dict, flow_downs


class _F:
    def __init__(self, signal: str, band_key: str, observed: str | None = None,
                 evidence_id: str | None = "ev-1") -> None:
        self.signal, self.band_key = signal, band_key
        self.observed = observed or band_key
        self.evidence_id = evidence_id


def _flag(standing: str = "ceased") -> ContinuityFlag:
    return ContinuityFlag(
        signal="entity_status", band="entity_inactive", standing=standing,
        statement="The register records this entity as inactive.",
        source="companies_house", observed="dissolved", evidence_id="ev-cont",
        retrieved_at="2026-07-30T00:00:00+00:00",
    )


# ============================================================ nothing fires


def test_a_clean_run_suggests_nothing_and_says_so():
    """"Nothing to suggest" is a real result, not an empty template — the same discipline P3
    applies when a vendor's evidence pack asks no questions."""
    result = flow_downs("acme", [])
    assert result == []
    payload = as_dict("acme", result)
    assert payload["count"] == 0
    assert "suggests nothing" in payload["summary"]
    assert "not an empty template" in payload["summary"]


def test_findings_that_do_not_match_a_family_raise_nothing():
    findings = [_F("dmarc", "absent"), _F("tls_version", "tls_13")]
    assert flow_downs("acme", findings) == []


# ============================================================ each family, one at a time


def test_no_published_incident_response_path():
    findings = [_F("vd_program", "none", observed="no disclosure route")]
    fd = flow_downs("acme", findings)
    assert len(fd) == 1
    assert fd[0].family == "no_incident_response_path"
    assert "breach/incident notification" in fd[0].protection
    assert "vd_program = no disclosure route (evidence ev-1)" in fd[0].citations


def test_security_txt_only_also_counts_as_thin_incident_response():
    findings = [_F("vd_program", "security_txt_only")]
    fd = flow_downs("acme", findings)
    assert [f.family for f in fd] == ["no_incident_response_path"]


def test_no_independent_audit_evidence():
    findings = [_F("cert_posture", "claimed_expired", observed="ISO 27001 (expired)")]
    fd = flow_downs("acme", findings)
    assert len(fd) == 1
    assert fd[0].family == "no_independent_audit_evidence"
    assert "Right-to-audit" in fd[0].protection
    assert "SOC 2" in fd[0].protection
    assert "cert_posture = ISO 27001 (expired) (evidence ev-1)" in fd[0].citations


def test_claimed_unverified_also_triggers_the_audit_family():
    findings = [_F("cert_posture", "claimed_unverified")]
    fd = flow_downs("acme", findings)
    assert [f.family for f in fd] == ["no_independent_audit_evidence"]


def test_kev_listed_suggests_a_remediation_sla_but_never_claims_overdue():
    """THE HONESTY CONSTRAINT. `kev_listed_cve` is a product-line name match — the CISA due date
    is not carried into the stored finding, the same limitation that keeps `gates.kev_overdue`
    declared and disabled in scoring.yaml. This must suggest the clause without asserting evidence
    the system does not have."""
    findings = [_F("kev_listed_cve", "listed", observed="CVE-2024-0001 in Widget (KEV)")]
    fd = flow_downs("acme", findings)
    assert len(fd) == 1
    assert fd[0].family == "kev_listed"
    assert "Remediation SLA" in fd[0].protection
    assert "NOT the same claim as" in fd[0].basis
    assert "overdue" in fd[0].basis.lower()


def test_a_clean_kev_receipt_does_not_fire():
    findings = [_F("kev_listed_cve", "no_kev_match")]
    assert flow_downs("acme", findings) == []


def test_going_concern_flag():
    fd = flow_downs("acme", [], continuity_flags=[_flag("ceased")])
    assert len(fd) == 1
    assert fd[0].family == "going_concern_flag"
    assert "Termination for convenience" in fd[0].protection
    assert "escrow" in fd[0].protection.lower()
    assert fd[0].citations == [_flag("ceased").cited()]


def test_a_sound_continuity_flag_is_good_news_and_raises_nothing():
    sound = ContinuityFlag(
        signal="entity_status", band="active_good_standing", standing="sound",
        statement="Active and in good standing.", source="companies_house",
        observed="active", evidence_id="ev-2", retrieved_at=None,
    )
    assert flow_downs("acme", [], continuity_flags=[sound]) == []


def test_concentrated_fourth_party_dependency():
    fd = flow_downs("acme", [], spof_providers=["Okta"])
    assert len(fd) == 1
    assert fd[0].family == "concentrated_fourth_party_dependency"
    assert "Subprocessor change" in fd[0].protection
    assert "Okta" in fd[0].observed
    assert "single point of failure at Okta" in fd[0].citations[0]


def test_thin_coverage_or_ghost_by_ghost():
    fd = flow_downs("acme", [], ghost=True)
    assert len(fd) == 1
    assert fd[0].family == "thin_coverage_or_ghost"
    assert "questionnaire" in fd[0].protection.lower()
    assert "Ghost" in fd[0].citations[0]


def test_thin_coverage_or_ghost_by_low_confidence_band_without_being_a_ghost():
    fd = flow_downs("acme", [], thin_coverage=True)
    assert len(fd) == 1
    assert fd[0].family == "thin_coverage_or_ghost"
    assert "Low confidence band" in fd[0].citations[0]


def test_neither_ghost_nor_thin_raises_nothing():
    assert flow_downs("acme", [], ghost=False, thin_coverage=False) == []


# ============================================================ several families at once, ordering


def test_multiple_families_fire_in_the_plans_published_order():
    findings = [
        _F("kev_listed_cve", "listed"),
        _F("cert_posture", "claimed_expired"),
        _F("vd_program", "none"),
    ]
    fd = flow_downs(
        "acme", findings,
        continuity_flags=[_flag("watch")],
        spof_providers=["Okta"],
        ghost=True,
    )
    assert [f.family for f in fd] == [
        "no_incident_response_path",
        "no_independent_audit_evidence",
        "concentrated_fourth_party_dependency",
        "going_concern_flag",
        "thin_coverage_or_ghost",
        "kev_listed",
    ]


# ============================================================ the published shape


def test_as_dict_carries_the_table_version_and_the_not_legal_advice_caveat():
    fd = flow_downs("acme", [_F("vd_program", "none")])
    payload = as_dict("acme", fd)
    assert payload["vendor_ref"] == "acme"
    assert payload["table_version"] == TABLE_VERSION
    assert payload["count"] == 1
    row = payload["flow_downs"][0]
    assert row["family"] == "no_incident_response_path"
    assert row["suggested_protection"] and row["basis"] and row["citations"]
    assert row["cited"].startswith("Observed:")
    assert "Suggested:" in row["cited"]
    assert any("NOT LEGAL ADVICE" in c for c in payload["caveats"])
    assert any("cited to the finding" in c for c in payload["caveats"])


def test_every_row_is_cited_never_asserted_bare():
    """A suggestion with nothing behind it would be our opinion of the vendor. Every family this
    module can raise must carry at least one citation the reader can check."""
    findings = [_F("vd_program", "none"), _F("cert_posture", "claimed_expired"),
                _F("kev_listed_cve", "listed")]
    fd = flow_downs("acme", findings, continuity_flags=[_flag()], spof_providers=["Okta"],
                    ghost=True)
    assert fd, "expected every family to fire in this fixture"
    for row in fd:
        assert row.citations, f"{row.family} has no citation"


# ------------------------------------------------- P8 · the seventh family, client-declared


def test_sole_source_mandates_exit_rights():
    """The plan says `sole_source` "mandates exit-clause flow-downs". That sentence names this
    module, and until this row existed P8 published an alert with nowhere for it to land."""
    fd = flow_downs("acme", [], substitutability="sole_source")
    assert len(fd) == 1
    assert fd[0].family == "sole_source_exit_rights"
    assert "escrow" in fd[0].protection
    assert "exit-assistance" in fd[0].protection.lower()
    assert fd[0].citations == ["client-declared substitutability: sole_source"]


def test_low_substitutability_asks_for_exit_assistance_and_not_escrow():
    """The plan's table distinguishes them, so the output must too. Escrow on a merely-difficult
    migration is a demand that costs negotiating capital and buys little."""
    fd = flow_downs("acme", [], substitutability="low")
    assert len(fd) == 1
    assert fd[0].family == "low_substitutability_exit_assistance"
    assert "escrow" not in fd[0].protection.lower()


@pytest.mark.parametrize("value", ["medium", "high", None])
def test_medium_and_high_produce_no_clause_at_all(value):
    """"Standard terms" and "no exit conditions needed" are the ABSENCE of a clause, not a clause
    saying nothing is needed. A row that said so would be a template filled in seven times."""
    assert flow_downs("acme", [], substitutability=value) == []


def test_the_declared_row_cites_the_declaration_not_an_observation():
    """Substitutability is client-declared, so there is no finding and no evidence id to cite —
    the same shape as the concentration and thin-coverage rows, which cite the module that
    produced them rather than pretending to an observation they do not have."""
    fd = flow_downs("acme", [], substitutability="sole_source")[0]
    assert "client-declared" in fd.citations[0]
    assert "evidence" not in fd.citations[0]


def test_the_exit_row_composes_with_the_observed_ones():
    """A sole-source vendor with a going-concern flag gets both, and the exit row sorts last —
    the plan's published order, which puts observed findings before declared exposure."""
    fd = flow_downs("acme", [_F("vd_program", "none")],
                    continuity_flags=[_flag()], substitutability="sole_source")
    assert [f.family for f in fd] == [
        "no_incident_response_path", "going_concern_flag", "sole_source_exit_rights",
    ]
