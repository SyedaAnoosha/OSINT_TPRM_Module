"""Test procurement_rules.py — deterministic advisory text from Business Stability standing."""

import pytest

from app.procurement_rules import ProcurementRule, get_procurement_advice, all_rules


class TestProcurementRules:
    """Tests for the procurement rules lookup mechanism."""

    def test_all_standings_have_rules(self):
        """Every Continuity.standing value has a corresponding procurement rule."""
        standings = {"ceased", "impaired", "watch", "sound", "unknown"}
        rules = all_rules()
        covered = {r.standing for r in rules}
        assert standings == covered, f"Missing rules for: {standings - covered}"

    def test_ceased_is_blocking(self):
        """ceased standing produces a blocking rule (do not proceed)."""
        rule = get_procurement_advice("ceased")
        assert rule.blocking is True
        assert "Do not proceed" in rule.headline or "contract" in rule.headline.lower()
        assert "successor" in rule.detail.lower() or "novation" in rule.detail.lower()

    def test_impaired_is_blocking(self):
        """impaired standing produces a blocking rule (escalate before renewal)."""
        rule = get_procurement_advice("impaired")
        assert rule.blocking is True
        assert "escalate" in rule.headline.lower() or "risk" in rule.headline.lower()
        assert "legal" in rule.detail.lower() or "security" in rule.detail.lower()

    def test_watch_is_not_blocking_but_advisory(self):
        """watch standing is advisory (request updated extract) but not blocking."""
        rule = get_procurement_advice("watch")
        assert rule.blocking is False
        assert "updated" in rule.headline.lower() or "extract" in rule.headline.lower()
        assert "renewal" in rule.detail.lower() or "signing" in rule.detail.lower()

    def test_sound_is_clean(self):
        """sound standing indicates no concerns identified."""
        rule = get_procurement_advice("sound")
        assert rule.blocking is False
        assert "no continuity concerns" in rule.headline.lower() or "no adverse" in rule.detail.lower()

    def test_unknown_treats_absence_as_unknown_not_clean(self):
        """unknown standing explicitly warns that absence of data is not health."""
        rule = get_procurement_advice("unknown")
        assert rule.blocking is False
        assert "unknown" in rule.headline.lower() or "evidenced" in rule.headline.lower()
        # The key principle: absence of data is NOT presented as health
        assert "not as clean" in rule.detail.lower() or "absence" in rule.detail.lower()

    def test_invalid_standing_raises(self):
        """Requesting a rule for an unknown standing raises ValueError."""
        with pytest.raises(ValueError, match="Unknown standing"):
            get_procurement_advice("invalid_standing")

    def test_rule_structure(self):
        """Each ProcurementRule has the expected fields."""
        rule = get_procurement_advice("watch")
        assert isinstance(rule, ProcurementRule)
        assert hasattr(rule, "standing")
        assert hasattr(rule, "headline")
        assert hasattr(rule, "detail")
        assert hasattr(rule, "blocking")
        assert isinstance(rule.blocking, bool)
        assert isinstance(rule.headline, str)
        assert isinstance(rule.detail, str)
        assert len(rule.headline) > 0
        assert len(rule.detail) > 0

    def test_all_rules_returns_complete_list(self):
        """all_rules() returns exactly one rule per standing."""
        rules = all_rules()
        assert len(rules) == 5
        standings = {r.standing for r in rules}
        assert standings == {"ceased", "impaired", "watch", "sound", "unknown"}

    def test_rule_detail_mentions_legal_review(self):
        """The module documents that legal review is required (checked via docstring inspection)."""
        import app.procurement_rules as mod
        # This is a meta-check ensuring the legal review flag is present in the code
        assert "LEGAL REVIEW" in mod.__doc__ or "legal" in mod.__doc__.lower()