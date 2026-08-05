"""Tests for the lifecycle context module.

The classifier thresholds are the only thing worth testing here. One test per threshold
edge, not per stage. Also covers the key-person risk derivation and the obsolescence
re-framing.
"""

from __future__ import annotations

import pytest

from app.lifecycle import LifecycleReport, lifecycle_report, lifecycle_stage_from_years
from app.models import PersistedFinding


class TestLifecycleStageClassifier:
    """Boundary tests — one per threshold edge."""

    def test_none_input_is_unknown(self):
        assert lifecycle_stage_from_years(None) == "unknown"

    def test_exactly_at_one_year_is_go_go(self):
        assert lifecycle_stage_from_years(1.0) == "go_go"

    def test_just_below_one_year_is_infancy(self):
        assert lifecycle_stage_from_years(0.99) == "infancy"

    def test_exactly_at_two_years_is_adolescence(self):
        assert lifecycle_stage_from_years(2.0) == "adolescence"

    def test_exactly_at_five_years_is_prime(self):
        assert lifecycle_stage_from_years(5.0) == "prime"

    def test_exactly_at_fifteen_years_is_aging(self):
        assert lifecycle_stage_from_years(15.0) == "aging"

    def test_very_old_vendor_is_still_aging(self):
        assert lifecycle_stage_from_years(200.0) == "aging"


class TestKeyPersonRisk:
    """Key-person flag fires only on micro headcount + high criticality."""

    def _make(self, headcount, criticality):
        return lifecycle_report(
            vendor_ref="test",
            operating_years=5.0,
            headcount=headcount,
            criticality=criticality,
            findings=[],
        )

    def test_fires_on_micro_headcount_high_criticality(self):
        r = self._make(headcount=10, criticality="high")
        assert r.key_person_risk is True
        assert r.key_person_basis is not None

    def test_does_not_fire_on_micro_headcount_medium_criticality(self):
        r = self._make(headcount=10, criticality="medium")
        assert r.key_person_risk is False

    def test_does_not_fire_on_headcount_above_threshold(self):
        r = self._make(headcount=11, criticality="high")
        assert r.key_person_risk is False

    def test_does_not_fire_on_none_headcount(self):
        r = self._make(headcount=None, criticality="high")
        assert r.key_person_risk is False


class TestObsolescenceSignals:
    """Obsolescence signals are only populated from findings in _OBSOLESCENCE_SIGNALS."""

    def test_populated_from_known_signal(self):
        finding = PersistedFinding(
            id="f1", vendor_ref="test", evidence_id="e1", source="tls",
            category="attack_surface_hygiene", signal="tls_version",
            band_key="tls_10_or_11", severity="high", penalty=20.0,
            effective_penalty=20.0, observed="TLS 1.0/1.1 offered",
            content_hash="abc",
        )
        r = lifecycle_report("test", 10.0, None, None, [finding])
        assert len(r.obsolescence_signals) == 1
        assert r.obsolescence_signals[0].signal == "tls_version"

    def test_not_populated_from_unknown_signal(self):
        finding = PersistedFinding(
            id="f2", vendor_ref="test", evidence_id="e2", source="dns",
            category="identity_email", signal="dmarc",
            band_key="p_none", severity="medium", penalty=8.0,
            effective_penalty=8.0, observed="DMARC p=none",
            content_hash="def",
        )
        r = lifecycle_report("test", 10.0, None, None, [finding])
        assert len(r.obsolescence_signals) == 0


class TestLifecycleReportNeverScores:
    """The report carries no penalty, no score, no posture-affecting field."""

    def test_report_has_no_posture_field(self):
        r = lifecycle_report("test", 5.0, 5, "high", [])
        assert not hasattr(r, "posture")
        assert not hasattr(r, "penalty")
        assert not hasattr(r, "score")