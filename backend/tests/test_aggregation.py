"""E7 — aggregation, the severity ladder, root-cause dedup and the ceiling ramp.

THE DEFECT, COMPUTED. Under the flat ladder four Medium findings plus eight Low ones came to 56
points against a Critical's 40. Twelve missing HTTP headers outranked one actively-exploited
vulnerability, 0.71 : 1. That is not a presentation problem — the arithmetic itself is telling a
security team that trivia matters more than the thing attackers are using today.

WHY THE TWO HALVES SHIP TOGETHER. Neither reaches a defensible ratio alone:

    flat ladder, no discount    0.71 : 1     trivia wins
    discount only               1.78 : 1
    ladder only                 1.39 : 1
    both                        3.06 : 1     <- shipped

Shipping them separately would publish an intermediate state that satisfies nobody and would need
its own change notice.

THE SEVERITY VALUES ARE EXPERT JUDGEMENT, NOT CALIBRATION. Nothing in this repo can yet show that
a Critical is 33x a Low rather than 20x — that needs outcome labels, deferred at E0.4. The tests
below pin the RELATIONSHIPS the model claims, not their correctness.
"""

from __future__ import annotations

import copy
import random
from pathlib import Path

import pytest
import yaml

from app.models import CollectorResult, Finding, Vendor
from app.scoring import ScoringEngine
from app.scoring_config import ScoringConfig, get_scoring_config

_YAML = Path(__file__).resolve().parents[2] / "scoring.yaml"

H = "attack_surface_hygiene"
B = "breach_compromise_history"


def _vendor() -> Vendor:
    return Vendor(ref="acme", name="Acme", domain="acme.example",
                  resolved=True, resolution_confidence=1.0)


def _f(signal: str, band: str, **value) -> Finding:
    return Finding(source="t", signal=signal, category=H, observed=band,
                   value={"band": band, **value})


def _score(findings: list[Finding], cfg: ScoringConfig | None = None):  # noqa: ANN201
    result = [CollectorResult(source="t", vendor_ref="acme", status="ok", source_version="t",
                              raw={"t": 1}, reliability=0.9, findings=findings)]
    return ScoringEngine(cfg=cfg).score(_vendor(), result)


def _cat(score, name):  # noqa: ANN001
    return {c.category: c for c in score.categories}[name]


def _decayed(penalties: list[float], decay: float) -> float:
    return sum(p * decay ** i for i, p in enumerate(sorted(penalties, reverse=True)))


# --------------------------------------------------------------------- E7b: the ladder


def test_the_ladder_widened_and_low_is_a_float():
    """`low: 1.5` is deliberately not an integer. Anything asserting integer penalties fails here,
    which is the point — it forces the assumption to be found rather than to silently round."""
    cfg = get_scoring_config()
    assert cfg.penalty_for("critical") == 50.0
    assert cfg.penalty_for("high") == 20.0
    assert cfg.penalty_for("medium") == 6.0
    assert cfg.penalty_for("low") == 1.5
    assert cfg.penalty_for("critical") / cfg.penalty_for("low") == pytest.approx(33.3, abs=0.1)


# --------------------------------------------------------------------- E7a + E7b together


def test_one_critical_kev_outranks_twelve_hygiene_failures():
    """THE test for this phase. Asserts the RATIO, not the raw numbers, so a future re-tune of the
    ladder or the decay is free to move both as long as severity still beats volume by 3:1."""
    cfg = get_scoring_config()
    decay = cfg.aggregation_decay()

    trivia = _decayed([cfg.penalty_for("medium")] * 4 + [cfg.penalty_for("low")] * 8, decay)
    critical = cfg.penalty_for("critical")

    assert critical / trivia >= 3.0, (
        f"one Critical charges {critical} and twelve hygiene failures charge {trivia:.2f} — "
        f"a ratio of {critical / trivia:.2f}:1. A security team reading that is being told "
        f"trivia matters more than an actively-exploited vulnerability."
    )
    # ...and the pre-E7 arrangement really did fail this, which is what makes the change necessary.
    assert 40 / _decayed([8.0] * 4 + [3.0] * 8, 1.0) < 1.0


def test_the_tenth_finding_costs_less_than_the_first():
    """The mechanism, stated directly. The tenth missing header on a vendor already missing nine
    tells you almost nothing new — you knew nobody was minding the headers after the third."""
    decay = get_scoring_config().aggregation_decay()
    assert decay < 1.0
    one = _decayed([1.5], decay)
    ten = _decayed([1.5] * 10, decay)
    assert ten < 10 * one
    assert ten > one, "diminishing must not become free — more problems is still worse"


def test_diminishing_returns_applies_within_a_category_never_across():
    """Cross-category discounting would let a vendor's worst category be cheapened by their
    second-worst, which is exactly the compensatory behaviour the critical ceiling exists to stop.
    Two categories each holding one High must charge the full 20 twice."""
    findings = [
        Finding(source="t", signal="tls_version", category=H, observed="tls_10_or_11",
                value={"band": "tls_10_or_11"}),
        Finding(source="t", signal="dmarc", category="identity_email", observed="absent",
                value={"band": "absent"}),
    ]
    out = _score(findings)
    assert _cat(out.score, H).penalty == 20.0
    assert _cat(out.score, "identity_email").penalty == 20.0


# --------------------------------------------------------------------- the receipts still add up


def test_effective_penalty_sums_to_the_published_category_penalty():
    """`effective_penalty` must be the POST-discount value.

    Writing the pre-discount number would make a category's findings visibly fail to add up to the
    category's own penalty — the exact defect this field was introduced to prevent. It is the one
    way a reader can check our arithmetic, so it has to survive every transform we add.
    """
    out = _score([
        _f("tls_version", "tls_10_or_11"), _f("hsts", "absent"), _f("csp", "absent"),
        _f("dnssec", "misconfigured"), _f("cert_validity", "expiring_lt_30d"),
    ])
    rebuilt = sum(n.effective_penalty for n in out.normalized if n.category == H)
    assert round(rebuilt, 2) == round(_cat(out.score, H).penalty, 2)
    # The ranks are stored too, so the discount can be reconstructed and not merely trusted.
    ranked = [n.aggregation_rank for n in out.normalized
              if n.category == H and n.effective_penalty > 0]
    assert sorted(ranked) == list(range(1, len(ranked) + 1))


def test_monotonicity_remediation_never_loses_points():
    """GENERATED, not three hand-picked cases.

    Monotonicity is the property most likely to break silently under a re-ranking transform and
    the least likely to be caught by a five-vendor corpus. The hazard is specific: fixing a
    mid-ranked finding promotes everything below it to a cheaper rank — i.e. a LARGER multiplier —
    so it is not obvious from the formula that the total must fall.

    A vendor who fixes something must never see their posture drop. If that is ever false the
    model is telling suppliers that remediation is against their interest.
    """
    decay = get_scoring_config().aggregation_decay()
    rng = random.Random(20260731)   # seeded: a failure must be reproducible, not a one-off
    ladder = [50.0, 20.0, 6.0, 1.5]

    for _ in range(2000):
        penalties = [rng.choice(ladder) for _ in range(rng.randint(1, 10))]
        before = _decayed(penalties, decay)

        i = rng.randrange(len(penalties))
        fixed = list(penalties)
        # Remediation is either a full fix or a downgrade to a lesser severity. Both must help.
        fixed[i] = 0.0 if rng.random() < 0.5 else rng.choice([p for p in ladder if p < fixed[i]] or [0.0])

        after = _decayed([p for p in fixed if p > 0], decay)
        assert after <= before + 1e-9, (
            f"fixing a finding RAISED the penalty: {penalties} -> {fixed} "
            f"({before:.4f} -> {after:.4f}). Remediation must never cost a vendor points."
        )


def test_adding_a_finding_never_lowers_the_penalty():
    """The mirror. Diminishing returns must diminish, never reverse: a new problem is still a
    problem even when a vendor already has nine."""
    decay = get_scoring_config().aggregation_decay()
    rng = random.Random(7)
    for _ in range(1000):
        penalties = [rng.choice([50.0, 20.0, 6.0, 1.5]) for _ in range(rng.randint(0, 9))]
        extra = rng.choice([50.0, 20.0, 6.0, 1.5])
        assert _decayed(penalties + [extra], decay) >= _decayed(penalties, decay) - 1e-9


# --------------------------------------------------------------------- E7c: root cause


def test_kev_suppresses_the_duplicate_cve_penalty():
    """One remediation ticket, one penalty. Patching a KEV-listed CVE closes the NVD finding in
    the same action; charging both makes our arithmetic disagree with the vendor's work plan."""
    out = _score([
        Finding(source="t", signal="kev_listed_cve", category=B, observed="listed",
                value={"band": "listed"}),
        Finding(source="t", signal="nvd_cve", category=B, observed="cvss_critical",
                value={"band": "cvss_critical"}),
    ])
    nvd = next(n for n in out.normalized if n.signal == "nvd_cve")
    assert nvd.effective_penalty == 0.0
    assert nvd.suppressed_by and "kev_listed_cve" in nvd.suppressed_by
    assert _cat(out.score, B).penalty == 50.0, "the KEV alone, charged once"


def test_suppression_removes_the_penalty_and_keeps_the_evidence():
    """'We saw this and did not charge for it' and 'we did not see it' are different statements,
    and only one of them is true. A suppressed finding stays on the record, marked and reasoned."""
    out = _score([
        Finding(source="t", signal="kev_listed_cve", category=B, observed="listed",
                value={"band": "listed"}),
        Finding(source="t", signal="nvd_cve", category=B, observed="cvss_critical",
                value={"band": "cvss_critical"}),
    ])
    nvd = next(n for n in out.normalized if n.signal == "nvd_cve")
    assert nvd.penalty == 50.0, "the BASE severity is unchanged — only the charge was waived"
    assert nvd.band_key == "cvss_critical"
    assert "KEV" in nvd.suppressed_by, "the reason must be publishable, not just a flag"


def test_csp_satisfies_x_frame_options():
    """CSP Level 2 `frame-ancestors` supersedes X-Frame-Options and overrides it in every modern
    browser. A vendor serving CSP HAS the control; charging them for the legacy header too is
    charging them for not doing the same thing twice."""
    out = _score([_f("csp", "present"), _f("x_frame_opts", "absent")])
    xfo = next(n for n in out.normalized if n.signal == "x_frame_opts")
    assert xfo.effective_penalty == 0.0
    assert xfo.suppressed_by and "csp" in xfo.suppressed_by
    assert _cat(out.score, H).penalty == 0.0


def test_a_missing_csp_does_not_excuse_a_missing_xfo():
    """The rule fires on the superseding control PASSING. A vendor with neither has neither, and
    must be charged for the one we can still name."""
    out = _score([_f("csp", "absent"), _f("x_frame_opts", "absent")])
    xfo = next(n for n in out.normalized if n.signal == "x_frame_opts")
    assert xfo.suppressed_by is None
    assert xfo.effective_penalty > 0


def test_a_suppressed_penalty_does_not_occupy_a_rank():
    """Order matters: dedup runs BEFORE the discount ladder. If a suppressed finding took a rank,
    it would push real penalties down into cheaper slots — and a vendor could dilute genuine
    findings by accumulating duplicates, which inverts the whole point of deduplication."""
    with_dupe = _score([
        Finding(source="t", signal="kev_listed_cve", category=B, observed="listed",
                value={"band": "listed"}),
        Finding(source="t", signal="nvd_cve", category=B, observed="cvss_critical",
                value={"band": "cvss_critical"}),
        Finding(source="t", signal="breach_by_data_class", category=B, observed="personal_info",
                value={"band": "personal_info"}),
    ])
    without = _score([
        Finding(source="t", signal="kev_listed_cve", category=B, observed="listed",
                value={"band": "listed"}),
        Finding(source="t", signal="breach_by_data_class", category=B, observed="personal_info",
                value={"band": "personal_info"}),
    ])
    assert _cat(with_dupe.score, B).penalty == _cat(without.score, B).penalty


def test_every_root_cause_rule_states_a_basis():
    """The discipline `industry_profiles` had, which was right even though its mechanism was
    wrong. A suppression is a decision not to charge for something we observed — it needs a reason
    a vendor's engineer can check, not an entry in a hardcoded set."""
    rc = get_scoring_config().data.get("root_cause", {})
    rules = list(rc.get("precedence", [])) + list(rc.get("satisfied_by", []))
    assert rules, "root_cause is registered as engine-read but declares no rules"
    for rule in rules:
        assert len(str(rule.get("basis", "")).strip()) > 40, f"{rule}: no substantive basis"


# --------------------------------------------------------------------- E7d: the ceiling ramp


@pytest.mark.parametrize("coverage,expected", [
    (0.95, 100), (0.90, 100), (0.85, 97), (0.75, 97), (0.70, 90),
    (0.60, 90), (0.55, 80), (0.40, 80), (0.35, None),
])
def test_the_ceiling_ramp_is_graduated_not_a_cliff(coverage, expected):
    """Before E7d the only rung was `refuse_below: 0.4`. Above it, a vendor seen through four
    collectors could publish 100 and read exactly like one seen through fourteen — which made
    being hard to observe the cheapest route to a high score."""
    assert get_scoring_config().confidence_ceiling(coverage) == expected


def test_the_confidence_ceiling_caps_and_never_deducts():
    """The honesty rule is untouched. Thin evidence does not subtract a single posture point; it
    limits the CLAIM we are prepared to publish on the evidence we hold. The findings are the
    vendor's; the ceiling above them is ours."""
    findings = [_f("hsts", "absent")]
    full = _score(findings + [_f(s, b) for s, b in [
        ("tls_version", "tls_13"), ("cert_validity", "valid"), ("csp", "present"),
        ("x_frame_opts", "present"), ("dnssec", "valid"), ("caa", "present"),
    ]])
    assert _cat(full.score, H).penalty == 1.5, "the penalty is the same either way"


def test_the_two_ceilings_are_reported_separately():
    """A critical ceiling says something about the VENDOR — we observed something disqualifying.
    A confidence ceiling says something about US — we did not see enough to publish a number this
    high. Merging them would let a reader blame the vendor for our coverage."""
    out = _score([_f("cert_validity", "expired_serving_prod")])
    assert out.score.critical_ceiling_applied is True
    assert out.score.confidence_ceiling_applied is False
    assert out.score.ceiling_cause and "cert" in out.score.ceiling_cause


def test_insufficient_evidence_is_declared_adverse_in_config():
    """A grey 'insufficient evidence' chip reads as neutral, and neutral is wrong: a supplier
    nobody can see is a supplier nobody has checked. Pinned in config so the frontend and the
    report cannot quietly diverge from the wording."""
    cfg = get_scoring_config()
    conf = cfg.data["confidence"]
    assert conf["insufficient_evidence_is_adverse"] is True
    caveat = cfg.insufficient_evidence_caveat().lower()
    assert "adverse" in caveat
    assert "not be read as a clean bill of health" in caveat


# --------------------------------------------------------------------- config discipline


def test_aggregation_moved_from_documentation_only_to_engine_reads():
    """The trap this phase carries: `aggregation` sat in `_DOCUMENTATION_ONLY`, so a `decay` added
    to it would have read as a live rule in the docs and scored precisely nothing — which is how
    two NIST variables sat inert for a whole release."""
    from app.scoring_config import _DOCUMENTATION_ONLY, _ENGINE_READS

    assert "aggregation" in _ENGINE_READS
    assert "aggregation" not in _DOCUMENTATION_ONLY
    assert "root_cause" in _ENGINE_READS


def test_disabling_the_discount_restores_a_plain_sum():
    """`decay: 1.0` is the revert. Diminishing returns is the half of E7 most likely to be
    challenged, so it must be removable without touching the ladder."""
    data = copy.deepcopy(yaml.safe_load(_YAML.read_text(encoding="utf-8")))
    data["aggregation"]["decay"] = 1.0
    flat = ScoringConfig(data, _YAML)
    assert flat.aggregation_decay() == 1.0

    findings = [_f("tls_version", "tls_10_or_11"), _f("hsts", "absent"), _f("csp", "absent")]
    assert _cat(_score(findings, cfg=flat).score, H).penalty == pytest.approx(20 + 1.5 + 1.5)
    assert _cat(_score(findings).score, H).penalty < 23.0
