"""Regression guard: Business Stability must not have moved cybersecurity scoring.

WHAT THIS FILE IS FOR. Phase 2 added a whole second axis — insolvency collectors, financial
metrics, an age-derived stability score. The claim that came with it is that none of it touches
Posture: *"a bankrupt company can have excellent cybersecurity controls, and a secure startup can
run out of cash"*. This file is where that claim is CHECKED rather than asserted in a docstring.

WHY IT WAS REWRITTEN. The first version tested a `ScoringConfig` that does not exist —
`config.overall.penalty_divisor`, `config.grades.A.min`, `config.confidence.refuse_below`, dotted
attribute access on what are plain dicts behind accessor METHODS — plus category names
(`digital_footprint_assets`, `adverse_media`), signal names (`dmarc_policy`, `spf_record`) and
collector ids (`edgar`, `gazette`) the model has never used. Each raised AttributeError or
KeyError, so ten tests failed for reasons that said nothing about whether cybersecurity scoring
had changed. A guard that cannot fail for the right reason is worse than no guard: it reports a
breach that is not there, and it would not report the one that is.

The other half of the old file asserted `hasattr(SomeModel, '__annotations__')`, which is true of
every class in Python, and `len(existing_endpoints) == 5` against a list literal defined two lines
above. Those passed, and checked nothing. They are replaced with assertions that can fail.

Values below are what the model really holds, read from `scoring.yaml` v5.4.0.
"""

from __future__ import annotations

import pytest

from app.collectors import all_collectors
from app.models import (
    CollectorResult,
    Evidence,
    Finding,
    FinancialProfile,
    InsolvencyRecord,
    Score,
    Vendor,
    VendorProfile,
)
from app.scoring.engine import ScoringEngine
from app.scoring_config import get_scoring_config

from .test_corpus import AS_AT, VENDOR_REFS, load_fixture


class TestCybersecurityScoringUnchanged:
    """The model's headline constants. A published score is built out of these, so a silent change
    to any one of them re-bases every score in the book without a version bump."""

    def test_scoring_categories_unchanged(self):
        config = get_scoring_config()
        assert config.category_names() == [
            "breach_compromise_history",
            "attack_surface_hygiene",
            "identity_email",
            "transparency",
            "compliance_regulatory",
            # The two CONTEXT categories — they carry signals and coverage but no posture weight.
            # E5's "five scoring plus two context" split, which the divisor below depends on.
            "continuity_context",
            "assurance_context",
        ]

    def test_business_stability_is_a_separate_section_not_a_category(self):
        """Business Stability is its own axis with its own coverage figure, NOT a scored category.

        The distinction is the whole design. Its signals are declared in `scoring.yaml` and do
        reach the engine (at `informational`, so they cost nothing), but they are excluded from
        BOTH sides of the posture coverage ratio. If they ever appeared inside a scoring category,
        a financially distressed vendor would start losing posture points for being distressed.
        """
        config = get_scoring_config()
        assert "business_stability" in config.data, "the separate axis section is gone from the model"

        bs = config.business_stability_signals()
        assert bs, "no Business Stability signals declared — the exclusion list is doing nothing"

        scoring_categories = config.category_names()[:5]
        for cat in scoring_categories:
            overlap = bs & set(config.signals_of(cat))
            assert not overlap, f"Business Stability signal(s) {sorted(overlap)} scored in {cat}"

    def test_severity_penalties_unchanged(self):
        config = get_scoring_config()
        assert config.penalty_for("critical") == 50
        assert config.penalty_for("high") == 20
        assert config.penalty_for("medium") == 6
        assert config.penalty_for("low") == 1.5
        assert config.penalty_for("informational") == 0

    def test_divisor_unchanged(self):
        """2.86, FIXED BY THE MODEL — never the number of categories that happened to answer.

        This constant is what makes "missing data never changes posture" arithmetic rather than a
        promise: a silent source contributes no penalty and cannot move the denominator.
        """
        assert get_scoring_config().penalty_divisor() == 2.86

    def test_grades_unchanged(self):
        grades = get_scoring_config().grades()
        assert {k: v["min"] for k, v in grades.items()} == {
            "A": 85, "B": 70, "C": 50, "D": 30, "F": 0,
        }

    def test_confidence_floor_and_bands_unchanged(self):
        config = get_scoring_config()
        assert config.refuse_below() == 0.4, "the Ghost refusal threshold moved"
        assert config._bands() == {"high": 0.9, "medium": 0.7}


class TestSignalSeparation:
    """Signals must not have migrated between the two axes."""

    def test_cybersecurity_signals_unchanged(self):
        config = get_scoring_config()
        all_signals = set(config.all_signal_names())
        # Real signal keys as declared in scoring.yaml — note `dmarc`/`spf`, not the
        # `dmarc_policy`/`spf_record` the previous version of this test looked for.
        for signal in ("kev_listed_cve", "nvd_cve", "breach_by_data_class",
                       "tls_version", "cert_validity", "hsts", "csp", "x_frame_opts",
                       "dnssec", "caa", "dmarc", "spf", "dkim"):
            assert signal in all_signals, f"cybersecurity signal {signal!r} missing from the model"

    def test_no_signal_belongs_to_two_categories(self):
        """A signal scored in two categories is charged twice. Cheap to check, expensive to miss."""
        config = get_scoring_config()
        seen: dict[str, str] = {}
        for cat in config.category_names():
            for signal in config.signals_of(cat):
                assert signal not in seen, (
                    f"{signal!r} appears in both {seen[signal]!r} and {cat!r}"
                )
                seen[signal] = cat


class TestCollectorSeparation:
    """The collector registry — what a run will actually reach."""

    def test_financial_collectors_are_registered(self):
        registered = {c.source for c in all_collectors()}
        for source in ("eu_insolvency", "german_insolvency", "canada_bankruptcy",
                       "asic_insolvency", "sec_xbrl"):
            assert source in registered, f"financial collector {source!r} not registered"

    def test_the_key_gated_registry_collectors_stay_unregistered(self):
        """`open_corporates` and `registry_lookup` are written but deliberately NOT registered —
        see the commented-out `register(...)` lines in `app/collectors/__init__.py`.

        Asserted rather than ignored because the previous version of this test REQUIRED them to be
        registered and failed, reporting a regression where there had been a deliberate decision.
        If somebody switches them on, this is the test that makes them say so out loud.
        """
        registered = {c.source for c in all_collectors()}
        assert "open_corporates" not in registered
        assert "registry_lookup" not in registered

    def test_cybersecurity_collectors_unchanged(self):
        registered = {c.source for c in all_collectors()}
        # Real source ids: the SEC collector registers as `sec_edgar`, the UK gazette as
        # `the_gazette`. `edgar`/`gazette` — the old test's guess — were never the ids.
        for source in ("dns", "tls", "headers", "ct", "hibp", "kev", "nvd", "ita",
                       "gleif", "rdap", "regulatory", "trust", "otx", "abn",
                       "companies_house", "sec_edgar", "courtlistener_bankruptcy",
                       "the_gazette"):
            assert source in registered, f"cybersecurity collector {source!r} missing"


class TestScoringIndependence:
    """THE ACTUAL INVARIANT, end-to-end rather than by inspecting constants.

    Everything above checks that the model still SAYS the right thing. This checks that the engine
    DOES it: score a real corpus vendor, then score it again with financial evidence appended, and
    require the published result to be identical.
    """

    @pytest.mark.parametrize("ref", VENDOR_REFS)
    def test_financial_findings_never_move_posture_or_confidence(self, ref):
        vendor, results = load_fixture(ref)
        engine = ScoringEngine()
        baseline = engine.score(vendor, results, now=AS_AT).score

        financial = CollectorResult(
            source="sec_xbrl", vendor_ref=vendor.ref, status="ok", reliability=0.9,
            findings=[
                Finding(source="sec_xbrl", signal="sec_going_concern",
                        observed="no adverse filings", value={"band": "no_adverse_filings"}),
                Finding(source="sec_xbrl", signal="insolvency_notice",
                        observed="none", value={"band": "no_adverse_filings"}),
            ],
        )
        withfin = engine.score(vendor, [*results, financial], now=AS_AT).score

        assert withfin.posture == baseline.posture, (
            "financial evidence moved the cybersecurity posture — the two axes have merged"
        )
        assert withfin.grade == baseline.grade
        # Confidence too: Business Stability signals are excluded from BOTH sides of the posture
        # coverage ratio, so adding them must not inflate coverage either.
        assert withfin.overall_confidence == baseline.overall_confidence


class TestModelSeparation:
    """The Pydantic contracts stay distinct — one shape cannot quietly absorb the other."""

    def test_financial_profile_is_not_vendor_profile(self):
        assert FinancialProfile is not VendorProfile
        # The rule the type exists to hold: no financial field on the cybersecurity profile.
        for field in ("insolvency_records", "financial_metrics", "debt_to_equity"):
            assert field in FinancialProfile.model_fields
            assert field not in VendorProfile.model_fields

    def test_insolvency_record_is_not_a_finding(self):
        """An InsolvencyRecord must not be a Finding, because a Finding is scoreable."""
        assert InsolvencyRecord is not Finding
        assert "severity_base" not in InsolvencyRecord.model_fields


class TestStoredContractsUnchanged:
    """The shapes the append-only store already holds. A field removed here does not just change
    future scores — it stops old rows deserialising, and the evidence store is the legal artefact.
    """

    def test_score_still_carries_both_axes(self):
        for field in ("vendor_ref", "posture", "grade", "overall_confidence",
                      "confidence_band", "blocked", "refused", "ghost", "categories"):
            assert field in Score.model_fields, f"Score lost the {field!r} field"

    def test_vendor_contract_unchanged(self):
        for field in ("ref", "name", "domain", "resolved", "resolution_confidence"):
            assert field in Vendor.model_fields, f"Vendor lost the {field!r} field"

    def test_finding_contract_unchanged(self):
        for field in ("source", "signal", "category", "observed", "value", "severity_base"):
            assert field in Finding.model_fields, f"Finding lost the {field!r} field"

    def test_collector_result_contract_unchanged(self):
        for field in ("source", "vendor_ref", "status", "fetched_at", "raw",
                      "findings", "reliability"):
            assert field in CollectorResult.model_fields, f"CollectorResult lost {field!r}"

    def test_evidence_keeps_its_hash(self):
        """`content_hash` is what proves a stored record was not altered. It is not optional."""
        assert "content_hash" in Evidence.model_fields
