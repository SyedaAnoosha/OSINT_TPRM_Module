"""E8 — hard gates. A gate is not a low score.

THE FAILURE IT PREVENTS IS ARITHMETIC. A vendor with a disqualifying finding publishes 60, clears
a ">= 50" procurement threshold written into somebody's policy two years ago, and is onboarded by
a rule nobody re-read. A gated record has no number to clear a threshold with: it emits no posture
and no grade and routes to a human.

E8's contribution is the MECHANISM plus the discipline around it — every gate carries a named
basis, enforced at load, and a gate that is declared but switched off has to say why. Two of the
four gates the plan proposed are shipped disabled, and the reason is about the strength of OUR
evidence rather than about whether the rule is right. That reason lives next to the rule.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from app.models import CollectorResult, Finding, Vendor
from app.scoring import ScoringEngine
from app.scoring_config import ScoringConfig, ScoringConfigError, get_scoring_config

_YAML = Path(__file__).resolve().parents[2] / "scoring.yaml"


def _raw() -> dict:
    return copy.deepcopy(yaml.safe_load(_YAML.read_text(encoding="utf-8")))


def _vendor(conf: float = 1.0) -> Vendor:
    return Vendor(ref="acme", name="Acme", domain="acme.example",
                  resolved=True, resolution_confidence=conf)


def _results(*findings: Finding) -> list[CollectorResult]:
    return [CollectorResult(source="t", vendor_ref="acme", status="ok", source_version="t",
                            raw={"t": 1}, reliability=0.9, findings=list(findings))]


def _f(signal: str, band: str, category: str = "continuity_context", **value) -> Finding:
    return Finding(source="t", signal=signal, category=category, observed=band,
                   value={"band": band, **value})


# --------------------------------------------------------------------- the live gate


def test_a_dissolved_entity_is_gated_not_scored():
    """The only one of E8's four proposed gates whose evidence can carry a block today.

    A dissolved or struck-off company has no legal personality: it cannot hold a contract, carry
    insurance, or be sued. That is a registry FACT with a retrieval date, not an inference from a
    keyword match — which is what separates it from the two gates shipped disabled.
    """
    out = ScoringEngine().score(_vendor(), _results(
        _f("entity_existence", "entity_dissolved"),
        _f("tls_version", "tls_13", "attack_surface_hygiene"),
    ))
    assert out.score.blocked is True
    assert out.score.posture is None and out.score.grade is None, "a gate emits NO number"
    assert "entity_dissolved" in (out.score.blocked_reason or "")


def test_the_block_reason_carries_the_basis_a_human_will_be_shown():
    """A blocked record goes to a person who has to decide something. It must arrive saying why,
    in words, with the ground named — not as a status code."""
    out = ScoringEngine().score(_vendor(), _results(_f("entity_existence", "entity_dissolved")))
    reason = (out.score.blocked_reason or "").lower()
    assert "legal personality" in reason, "the ground must be stated, not just the trigger"
    assert "companies house" in reason, "the register behind the fact must be nameable"
    assert "entity_existence=entity_dissolved" in reason, "and the observation that tripped it"


def test_e4s_split_is_honoured_administration_does_not_gate():
    """The collision E4 flagged and resolved. `entity_dissolved` gates; `registration_lapsed`,
    administration, liquidation and receivership do NOT — they are going-concern facts a buyer may
    legitimately proceed on with conditions, and they surface as cited Continuity flags.

    Gating on administration would block companies that trade through it every day.
    """
    for band in ("registration_lapsed", "registration_retired", "entity_inactive"):
        out = ScoringEngine().score(_vendor(), _results(
            _f("entity_status", band),
            _f("tls_version", "tls_13", "attack_surface_hygiene"),
        ))
        assert out.score.blocked is False, f"{band} must not gate — it is a Continuity flag"


def test_a_healthy_entity_is_not_gated():
    out = ScoringEngine().score(_vendor(), _results(
        _f("entity_existence", "entity_active_confirmed"),
        _f("tls_version", "tls_13", "attack_surface_hygiene"),
    ))
    assert out.score.blocked is False


# --------------------------------------------------------------------- the declared-but-off gates


def test_the_kev_gate_is_declared_and_deliberately_not_live():
    """`kev_listed_cve` is a keyword match against a PRODUCT LINE — the band's own published reason
    says so. Blocking a company from being onboarded on a name match would be the most damaging
    false positive this system could produce.

    It is declared rather than backlogged because the trigger is READY: the CISA due date is
    already collected. Only the evidence linking the product to this vendor's estate is missing,
    and that is E12.
    """
    spec = get_scoring_config().data["gates"]["kev_overdue"]
    assert spec["enabled"] is False
    assert "keyword match" in spec["disabled_because"].lower() or \
           "product line" in spec["disabled_because"].lower()
    assert "E12" in spec["disabled_because"]
    assert "kev_overdue" not in [n for n, _ in get_scoring_config().finding_gates()]


def test_an_overdue_kev_does_not_block_while_the_gate_is_off():
    """The safety property of `enabled: false`: a live KEV with a due date two years past still
    scores rather than blocks, and the ceiling remains the proportionate response."""
    out = ScoringEngine().score(_vendor(), _results(
        Finding(source="kev", signal="kev_listed_cve", category="breach_compromise_history",
                observed="listed", value={"band": "listed", "due": "2024-01-01"}),
        _f("tls_version", "tls_13", "attack_surface_hygiene"),
    ))
    assert out.score.blocked is False


def test_the_tls_gate_is_declared_and_deliberately_not_live():
    """"Data-bearing" is not observable from outside. We handshake the apex, once — so this gate
    would block on a marketing site as readily as on a customer portal. The critical CEILING is
    already the proportionate response to evidence that coarse."""
    spec = get_scoring_config().data["gates"]["no_valid_tls"]
    assert spec["enabled"] is False
    assert "not observable" in spec["disabled_because"].lower()
    # ...and the ceiling still fires, so the finding is not being ignored.
    out = ScoringEngine().score(_vendor(), _results(
        _f("cert_validity", "expired_serving_prod", "attack_surface_hygiene")))
    assert out.score.blocked is False
    assert out.score.critical_ceiling_applied is True


def test_enabling_a_declared_gate_is_a_config_edit_and_nothing_else():
    """The point of the mechanism. If turning a gate on required code, the decision would arrive
    as a pull request rather than as the policy change it actually is."""
    data = _raw()
    data["gates"]["kev_overdue"]["enabled"] = True
    cfg = ScoringConfig(data, _YAML)
    assert "kev_overdue" in [n for n, _ in cfg.finding_gates()]

    overdue = Finding(source="kev", signal="kev_listed_cve", category="breach_compromise_history",
                      observed="listed", value={"band": "listed", "due": "2024-01-01"})
    out = ScoringEngine(cfg=cfg).score(_vendor(), _results(overdue))
    assert out.score.blocked is True and out.score.posture is None


def test_the_due_date_trigger_only_fires_once_the_date_has_PASSED():
    """`value_date_before_now` is a real predicate, not decoration. A KEV inside its remediation
    window is not yet a compliance failure, and gating on it would punish a vendor for a clock
    that has not run out."""
    data = _raw()
    data["gates"]["kev_overdue"]["enabled"] = True
    cfg = ScoringConfig(data, _YAML)

    future = (datetime.now(UTC) + timedelta(days=30)).date().isoformat()
    not_yet = Finding(source="kev", signal="kev_listed_cve", category="breach_compromise_history",
                      observed="listed", value={"band": "listed", "due": future})
    out = ScoringEngine(cfg=cfg).score(_vendor(), _results(not_yet))
    assert out.score.blocked is False, "a KEV inside its remediation window must not gate"


def test_a_missing_due_date_does_not_fire_the_gate():
    """Absence of a date is not a date in the past. A KEV entry with no due date must not block by
    accident — the failure mode of a predicate that treats None as zero."""
    data = _raw()
    data["gates"]["kev_overdue"]["enabled"] = True
    cfg = ScoringConfig(data, _YAML)
    out = ScoringEngine(cfg=cfg).score(_vendor(), _results(
        Finding(source="kev", signal="kev_listed_cve", category="breach_compromise_history",
                observed="listed", value={"band": "listed"})))
    assert out.score.blocked is False


# --------------------------------------------------------------------- the loader discipline


def test_a_gate_without_a_basis_fails_the_loader():
    """A gate stops a company being onboarded. It must never be possible to add one without a
    reason someone can be shown."""
    data = _raw()
    data["gates"]["entity_dissolved"]["basis"] = "because"
    with pytest.raises(ScoringConfigError, match="basis"):
        ScoringConfig(data, _YAML)


def test_a_disabled_gate_must_say_why_it_is_disabled():
    """A declared-but-off gate is a DECISION. Recorded, or deleted — an unexplained one reads as
    an oversight and will be switched on by someone who assumes it was."""
    data = _raw()
    del data["gates"]["kev_overdue"]["disabled_because"]
    with pytest.raises(ScoringConfigError, match="disabled_because"):
        ScoringConfig(data, _YAML)


def test_a_gate_on_a_signal_the_model_does_not_band_fails_the_loader():
    """Dead config, same as an orphaned `reasons` entry: a gate that can never fire reads as
    protection and provides none."""
    data = _raw()
    data["gates"]["entity_dissolved"]["when"]["signal"] = "not_a_signal"
    with pytest.raises(ScoringConfigError, match="could never fire"):
        ScoringConfig(data, _YAML)


def test_the_sanctions_invariant_still_holds():
    """`gates.sanctions.behaviour == "block"` is a LEGAL POSITION — Autonomous Sanctions Act 2011
    (Cth) s16(7) — not a tunable default. E8 generalised the gate machinery around it and must not
    have loosened it."""
    data = _raw()
    data["gates"]["sanctions"]["behaviour"] = "penalise"
    with pytest.raises(ScoringConfigError, match="s16\\(7\\)"):
        ScoringConfig(data, _YAML)


def test_every_gate_states_a_basis_on_the_shipped_config():
    cfg = get_scoring_config()
    for name in cfg.data["gates"]:
        assert len(cfg.gate_basis(name)) >= 40, f"gates.{name} has no substantive basis"


def test_ownership_unresolvable_is_not_a_second_gate_for_one_fact():
    """The E8 plan lists it as a fourth gate. It is `entity_ambiguous`, which already blocks when
    the registry match is too weak to carry an assessment. Adding a second gate for the same
    condition would double-count one fact — the mistake E3 fixed in the scoring arithmetic,
    repeated one layer up."""
    gates = get_scoring_config().data["gates"]
    assert "ownership_unresolvable" not in gates
    assert gates["entity_ambiguous"]["behaviour"] == "block"

    out = ScoringEngine().score(_vendor(conf=0.3), _results(
        _f("tls_version", "tls_13", "attack_surface_hygiene")))
    assert out.score.blocked is True and "entity" in (out.score.blocked_reason or "").lower()


# --------------------------------------------------------------------- gated != zero


def test_a_gated_vendor_is_distinguishable_from_a_zero_scoring_one():
    """`posture=None` must not render as `posture=0`. A zero is a measurement; a gate is a refusal
    to measure. Conflating them puts a blocked vendor at the bottom of a sorted list instead of in
    front of a human."""
    gated = ScoringEngine().score(_vendor(), _results(
        _f("entity_existence", "entity_dissolved"))).score
    assert gated.posture is None
    assert gated.grade is None
    assert gated.blocked is True
    assert gated.blocked_reason
    # A renderer keying on `blocked` gets the right answer before it ever reads `posture`.
    assert gated.model_dump()["blocked"] is True


# --------------------------------------------------------------------- the UI exit criteria

_SCORECARD = Path(__file__).resolve().parents[2] / "frontend" / "src" / "Scorecard.jsx"


def test_the_three_no_number_states_render_as_three_different_things():
    """E8 exit criterion 3, and the half of it a backend test can actually hold.

    Three states publish no posture, and they mean three different things:

        blocked   -> we WILL NOT score this vendor (sanctions, dissolved entity) — adjudicate
        refused   -> we CANNOT score this vendor (coverage below the floor) — an adverse result
        (scored)  -> we scored it, and the number happens to be low — a measurement

    Collapsing any two puts a vendor in the wrong queue. The card branches on `blocked` and
    `refused` before it reads `posture`, so the discrimination is structural: three components,
    not one component with three colours.
    """
    src = _SCORECARD.read_text(encoding="utf-8")
    assert "if (score.blocked)" in src and "<BlockedCard" in src
    assert "if (score.refused)" in src and "<RefusedCard" in src
    assert "function BlockedCard" in src and "function RefusedCard" in src


def test_insufficient_evidence_is_rendered_as_adverse_and_not_as_grey():
    """E7d's exit criterion, stated in the phase text as "grey is not adverse".

    The refusal card previously used `bg-secondary` — the same neutral chrome the UI uses for "not
    applicable" and "no data yet". Grey is the visual language of NOTHING HAPPENED, and a reader
    skimming a portfolio reads it as an incomplete row rather than a result. That is the exact
    misreading the Ghost mechanic exists to prevent, and it is what makes hiding better than being
    average.
    """
    src = _SCORECARD.read_text(encoding="utf-8")
    card = src[src.index("function RefusedCard"):]
    card = card[:card.index("\n}\n") + 3]
    assert "bg-secondary" not in card, "the refusal is drawn in neutral chrome again"
    assert "risk-high" in card, "the refusal must be drawn in the adverse palette"
    assert "adverse" in card.lower()


def test_a_posture_withheld_by_coverage_is_shown_as_withheld():
    """E7d. A vendor whose arithmetic earned 94 and who publishes 80 must not look like a vendor
    that earned 80: the second is a finding about their controls, the first is a limit on our
    evidence, and only one of them is remediable by patching something.

    The two ceilings are also drawn in different palettes on purpose. The critical ceiling is
    adverse to the VENDOR; this one is a limit on US, and putting it in the risk palette would let
    a reader blame the vendor for our coverage.
    """
    src = _SCORECARD.read_text(encoding="utf-8")
    assert "score.confidence_ceiling_applied" in src, (
        "the confidence ceiling withholds posture silently — the reader cannot see it bound"
    )
    assert "score.critical_ceiling_applied" in src
    block = src[src.index("score.confidence_ceiling_applied"):]
    block = block[:block.index(")}")]
    assert "risk-high" not in block, "the two ceilings must not share a palette"


# --------------------------------------------------------------------- E12 interaction


def test_the_critical_ceiling_arms_on_the_apex_and_not_on_any_host():
    """E12's ceiling interaction, decided and enforced BEFORE the fan-out exists.

    `cert_validity` is simultaneously the only `auto_signals` entry and the only `never_decays`
    signal. Today it is one handshake against the apex, so "expired" is unambiguous. The moment the
    estate fans out it becomes a rate, and the ceiling has to arm off something — at which point
    there are two wrong answers available and both look reasonable in a diff:

      ANY host expired -> a 400-host estate almost certainly has one abandoned staging box with a
                          dead certificate. Every large vendor is capped at 49 permanently, and a
                          non-compensatory knockout that fires constantly is one nobody reads.
                          That is strictly worse than not having the knockout.
      A rate threshold -> makes the most severe response in the model a tunable percentage, and
                          invites the argument that 3% of hosts is acceptable.

    Decided: the APEX. It preserves today's semantics exactly through the fan-out and leaves
    estate-wide certificate decay to `stale_hosts`, which is a rate signal and is where a rate
    belongs. Enforced now because the failure is silent and arrives as a one-line diff.
    """
    cfg = get_scoring_config()

    # Today's shape: no `host_role`, single-target probe, apex by construction. Arms.
    assert cfg.ceiling_scope_satisfied("cert_validity", {"band": "expired_serving_prod"}) is True
    # A fanned-out collector that names the apex. Arms.
    assert cfg.ceiling_scope_satisfied("cert_validity", {"host_role": "apex"}) is True
    # A fanned-out collector reporting an abandoned staging box. Does NOT arm.
    assert cfg.ceiling_scope_satisfied("cert_validity", {"host_role": "subdomain"}) is False
    # A signal with no declared scope is unaffected.
    assert cfg.ceiling_scope_satisfied("breach_by_data_class", {"host_role": "subdomain"}) is True


def test_the_ceiling_scope_states_its_basis():
    """Same discipline as a gate. The ceiling is the second most consequential thing this system
    does, and narrowing what arms it must never be possible without a reason someone can be shown."""
    scope = get_scoring_config().data["critical_ceiling"]["auto_signal_scope"]["cert_validity"]
    assert scope["host_role"] == "apex"
    assert len(scope["basis"]) > 40


def test_a_subdomain_expired_cert_does_not_cap_the_grade():
    """The behaviour, end to end, rather than the config read. This is the scenario that would
    otherwise cap every large vendor at 49 the day the fan-out lands."""
    out = ScoringEngine().score(_vendor(), _results(
        _f("cert_validity", "expired_serving_prod", "attack_surface_hygiene",
           host_role="subdomain")))
    assert out.score.critical_ceiling_applied is False, (
        "one abandoned staging certificate capped the whole vendor at the top of Grade D"
    )

    apex = ScoringEngine().score(_vendor(), _results(
        _f("cert_validity", "expired_serving_prod", "attack_surface_hygiene",
           host_role="apex")))
    assert apex.score.critical_ceiling_applied is True, "the apex must still arm the knockout"
