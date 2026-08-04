"""NIST SP 1326 finding-level modifiers — the decay-and-context model.

The single hardest thing to defend in any risk score is *why a 2013 breach counts less
than last month's*. NIST SP 1326 hands us the four variables — age, frequency, severity,
mitigation — so the answer is "a US federal publication says so", not "we invented a
curve" (methodology §5.3). Decay lives HERE, in risk, per finding — not only in
confidence. These are pure functions so the curve is inspectable and tested directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

# Defaults mirror scoring.yaml.modifiers; the engine passes the config values in.
DEFAULT_HALF_LIFE_MONTHS = 36.0
DEFAULT_AGE_FLOOR = 0.15
DEFAULT_FREQ_INCREMENT = 0.25
DEFAULT_FREQ_CAP = 2.0
DEFAULT_MITIGATION_FACTOR = 0.6

_DAYS_PER_MONTH = 30.436875


def age_factor(
    event_date: datetime | None,
    *,
    now: datetime | None = None,
    half_life_months: float = DEFAULT_HALF_LIFE_MONTHS,
    floor: float = DEFAULT_AGE_FLOOR,
) -> float:
    """Exponential decay with a floor: 0.5 ** (months / half_life), never below `floor`.

    A missing/undated finding (most hygiene signals — a missing DMARC record is *current*)
    does not decay: factor 1.0. A dated finding decays toward — but never reaches — `floor`,
    because a breach never becomes truly irrelevant.
    """
    if event_date is None:
        return 1.0
    now = now or datetime.now(UTC)
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=UTC)
    months = max(0.0, (now - event_date).total_seconds() / 86400.0 / _DAYS_PER_MONTH)
    return max(floor, 0.5 ** (months / half_life_months))


def frequency_factor(
    n_events: int,
    *,
    increment: float = DEFAULT_FREQ_INCREMENT,
    cap: float = DEFAULT_FREQ_CAP,
) -> float:
    """1 + increment*(n-1), capped. Three breaches are a *pattern*, not one breach ×3."""
    if n_events <= 1:
        return 1.0
    return min(cap, 1.0 + increment * (n_events - 1))


def mitigation_factor(evidenced: bool, *, factor: float = DEFAULT_MITIGATION_FACTOR) -> float:
    """×factor only where remediation is EVIDENCED (not merely claimed). Else 1.0.

    Most remediation is already baked into the band (KEV patch_evidenced=30 vs
    unpatched=95), so this multiplies only on an explicit, corroborated remediation flag
    — it must not double-count what the band already reflects.
    """
    return factor if evidenced else 1.0


def apply(
    base: float,
    *,
    event_date: datetime | None,
    n_events: int,
    mitigated: bool,
    now: datetime | None = None,
    config: dict | None = None,
) -> float:
    """Compose the modifiers onto a base severity, clamped to [0, 100]."""
    cfg = config or {}
    hl = float(cfg.get("age", {}).get("half_life_months", DEFAULT_HALF_LIFE_MONTHS))
    fl = float(cfg.get("age", {}).get("floor", DEFAULT_AGE_FLOOR))
    inc = float(cfg.get("frequency", {}).get("increment", DEFAULT_FREQ_INCREMENT))
    cap = float(cfg.get("frequency", {}).get("cap", DEFAULT_FREQ_CAP))
    mit = float(cfg.get("mitigation", {}).get("evidenced_factor", DEFAULT_MITIGATION_FACTOR))

    score = (
        base
        * age_factor(event_date, now=now, half_life_months=hl, floor=fl)
        * frequency_factor(n_events, increment=inc, cap=cap)
        * mitigation_factor(mitigated, factor=mit)
    )
    return max(0.0, min(100.0, score))
