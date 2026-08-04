"""E10b — Inherent Risk Tier and the Residual Risk view procurement actually decides from.

THREE THINGS, KEPT APART, AND THE SEPARATION IS THE DESIGN:

    Posture   — how strong the vendor looks. Ours to measure. Changes when their TLS changes.
    Inherent  — how much this buyer stands to lose. THEIRS to declare. Changes when the
                RELATIONSHIP changes, and not otherwise.
    Residual  — the published combination. A DETERMINISTIC LOOKUP, not a third measurement.

WHY INHERENT RUNS ON A DIFFERENT CLOCK. A vendor's posture can move twice in a quarter; whether
they hold your production data moves when you sign a different contract. Storing them in one record
would make a re-scan look like a change in exposure, and a contract change look like a security
event. They are computed here, together, and stored nowhere — which is the second rule.

RESIDUAL IS A RENDERING, NOT A SCORE. Nothing in this module is persisted and nothing feeds back
into Posture. There is no `residual` column, because the moment there is one it can drift from the
posture and inherent tier it was derived from, and a reader has no way to tell which is stale.
Recomputed on read, always, from two inputs that are each independently disputable.

WHY A TABLE AND NOT A FORMULA. The same reason `recommend.py` is a table: what we publish must be
reconstructible and nameable in a sentence. `residual = f(posture, inherent)` as arithmetic invites
interpolation, and an interpolated risk tier is a number nobody can be walked through in a room.
Sixteen cells, argued over once, then fixed.

THE CELL THAT MATTERS MOST. High inherent + strong posture lands at **Medium**, never Low.
Inherent exposure does not vanish because controls look good — a vendor holding your production
data with an A grade is still a vendor holding your production data, and the day their posture
moves you find out how much you had riding on it. Every "strong posture" row is floored above the
bottom for exactly this reason, and it is asserted by test rather than left to the table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .models import Criticality

InherentTier = Literal["low", "medium", "high", "critical"]
ResidualTier = Literal["low", "low_medium", "medium", "medium_high", "high", "critical"]
PostureBand = Literal["strong", "moderate", "weak", "poor"]

#: `data_access_scope` already carries these four levels in `benchmarks.yaml`, where EB
#: deliberately kept it OUT of cohort keying — it is a property of the RELATIONSHIP, not of the
#: supplier, so keying on it would put one supplier in different cohorts for different buyers. EB
#: routed it to "interpretation" instead. **This is the interpretation it routes to.** Reusing it
#: rather than inventing a second relationship dimension means a client answers the question once.
_SCOPE_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_CRITICALITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
_TIERS: tuple[InherentTier, ...] = ("low", "medium", "high", "critical")

#: The published matrix, verbatim from the phase plan. Rows are posture bands worst-to-best down
#: the page in the plan; here they are keyed so a reader can find a cell without counting.
_RESIDUAL: dict[PostureBand, dict[InherentTier, ResidualTier]] = {
    "strong":   {"low": "low",         "medium": "low_medium", "high": "medium",   "critical": "medium_high"},
    "moderate": {"low": "low_medium",  "medium": "medium",     "high": "high",     "critical": "high"},
    "weak":     {"low": "medium",      "medium": "high",       "high": "high",     "critical": "critical"},
    "poor":     {"low": "medium_high", "medium": "high",       "high": "critical", "critical": "critical"},
}

_RESIDUAL_LABELS: dict[ResidualTier, str] = {
    "low": "Low", "low_medium": "Low-Medium", "medium": "Medium",
    "medium_high": "Medium-High", "high": "High", "critical": "Critical",
}

#: P8's escalation ladder. Ordered weakest to strongest, so "one band" is a well-defined step
#: rather than an opinion about which cell is adjacent to which.
_LADDER: tuple[ResidualTier, ...] = (
    "low", "low_medium", "medium", "medium_high", "high", "critical",
)

_POSTURE_BANDS: tuple[tuple[int, PostureBand], ...] = (
    (80, "strong"), (60, "moderate"), (40, "weak"), (0, "poor"),
)


def posture_band(posture: int) -> PostureBand:
    """Which row of the matrix a posture falls in. Boundaries inclusive at the bottom, per the plan."""
    for floor, band in _POSTURE_BANDS:
        if posture >= floor:
            return band
    return "poor"


@dataclass
class InherentRisk:
    """How much this buyer stands to lose, before any control is considered.

    Both inputs are CLIENT-SUPPLIED and neither is ever inferred. We do not know what a vendor
    holds for a buyer, and guessing would be `industry_profiles` in a third costume: our label,
    published as their exposure.
    """

    tier: InherentTier | None
    criticality: Criticality | None
    data_access_scope: str | None
    basis: str
    published: bool
    #: True when the declaration came from `app/inherent_register.py` and no relationship owner has
    #: confirmed it. It does NOT change the tier — a provisional declaration is the buyer's best
    #: current statement of exposure and is used as one — it changes what the page says about it.
    provisional: bool = False

    @property
    def label(self) -> str:
        if not self.tier:
            return "Not declared"
        base = self.tier.replace("_", "-").title()
        return f"{base} (provisional)" if self.provisional else base


@dataclass
class ResidualRisk:
    """The published combination. Recomputed on read, stored nowhere."""

    residual: ResidualTier | None
    residual_label: str | None
    posture: int | None
    posture_band: PostureBand | None
    inherent: InherentRisk
    published: bool
    reason: str | None = None
    caveats: list[str] = field(default_factory=list)
    #: P8. `None` unless a declared `sole_source` moved the cell. The PRE-escalation tier is kept
    #: so the published figure can always be traced back to the matrix cell it came from — an
    #: escalation nobody can undo in their head is an adjustment, not a lookup.
    substitutability: str | None = None
    escalated_from: ResidualTier | None = None

    @property
    def escalated(self) -> bool:
        return self.escalated_from is not None

    def headline(self) -> str | None:
        if not self.published:
            return None
        return (f"Residual risk: {self.residual_label}. Posture {self.posture} "
                f"({self.posture_band}) against {self.inherent.label.lower()} inherent exposure.")


def inherent_tier(criticality: Criticality | None,
                  data_access_scope: str | None,
                  *, provisional: bool = False) -> InherentRisk:
    """The worse of *how much we depend on them* and *what they hold*. Non-compensatory, on purpose.

    THE MAXIMUM, NOT AN AVERAGE. A vendor holding production customer data is a critical exposure
    even if the service itself is replaceable, and a vendor running a business-critical process is
    a high exposure even if they hold nothing sensitive. Averaging the two would let each excuse
    the other, which is the compensatory move this system refuses everywhere else — the weakest
    link in continuity, the non-compensatory critical ceiling in posture.

    NEITHER INPUT SUPPLIED MEANS NOT DECLARED, NEVER `low`. Defaulting an undeclared exposure to
    low is the failure in the dangerous direction: every vendor nobody has classified would present
    as low-residual, and the ones nobody has classified are disproportionately the ones nobody has
    looked at.
    """
    ranks: list[int] = []
    parts: list[str] = []
    if criticality in _CRITICALITY_RANK:
        ranks.append(_CRITICALITY_RANK[criticality])
        parts.append(f"business criticality: {criticality}")
    if data_access_scope in _SCOPE_RANK:
        ranks.append(_SCOPE_RANK[data_access_scope])
        parts.append(f"data access scope: {data_access_scope}")

    if not ranks:
        # `provisional` is deliberately NOT carried onto this refusal: there is nothing provisional
        # about an absence, and a flag saying "this missing declaration is unconfirmed" would read
        # as though something had been declared.
        return InherentRisk(
            tier=None, criticality=criticality, data_access_scope=data_access_scope,
            published=False,
            basis=("Neither business criticality nor data access scope has been declared for this "
                   "relationship. Inherent exposure is NOT DECLARED, which is not the same as low "
                   "— it is the question nobody has answered yet."),
        )

    tier = _TIERS[max(ranks)]
    basis = (f"{' · '.join(parts)} — inherent tier is the HIGHER of the two, because a vendor "
             f"holding sensitive data and a vendor running a critical process are each exposures "
             f"in their own right and neither offsets the other.")
    if len(ranks) == 1:
        basis += (" Only one of the two inputs was declared, so this tier may understate the "
                  "exposure; supply the other to firm it up.")
    if provisional:
        basis += (" PROVISIONAL — declared on the inherent register and not yet confirmed by the "
                  "accountable relationship owner. It is used as the buyer's current statement of "
                  "exposure, because a provisional answer routes better than no answer; it is "
                  "labelled because an unconfirmed answer read as a confirmed one is worse than "
                  "either.")
    return InherentRisk(tier=tier, criticality=criticality, data_access_scope=data_access_scope,
                        basis=basis, published=True, provisional=provisional)


def residual_risk(posture: int | None,
                  criticality: Criticality | None = None,
                  data_access_scope: str | None = None,
                  *,
                  blocked: bool = False,
                  refused: bool = False,
                  substitutability: str | None = None,
                  provisional: bool = False) -> ResidualRisk:
    """The sixteen-cell lookup, plus P8's one declared escalation. Deterministic and never stored.

    P8 — `sole_source` ESCALATES THE PUBLISHED TIER BY ONE BAND, and this is the plan's own rule
    rather than an invention here. The argument: the matrix answers *"how exposed are we to this
    vendor's controls failing"*, and a vendor you cannot replace changes what a failure COSTS
    without changing anything about the vendor. That is a third dimension, and it is client-declared
    exactly like the other two — never inferred, because switching cost and lock-in are not
    observable from outside.

    THE ESCALATION IS DISCLOSED, NOT ABSORBED. `escalated_from` keeps the cell the matrix actually
    produced, so a reader can always reconstruct the lookup and see the one step applied on top.
    An escalation that silently rewrites the cell would make the published tier untraceable to the
    table it claims to come from — which is the whole reason this is a table and not a formula.

    IT ONLY ESCALATES. There is no `high` value that de-escalates: an easily replaced vendor is not
    *less* exposed to a control failure while you are still using them, and a rule that could lower
    a residual tier on a client's own declaration is a rule that will be used to lower it.
    """
    inherent = inherent_tier(criticality, data_access_scope, provisional=provisional)

    def refuse(reason: str) -> ResidualRisk:
        return ResidualRisk(residual=None, residual_label=None, posture=posture,
                            posture_band=None, inherent=inherent, published=False, reason=reason,
                            substitutability=substitutability)

    if blocked:
        return refuse(
            "This vendor is blocked pending human adjudication and has no published posture. A "
            "residual tier computed against a missing posture would be an inherent tier wearing a "
            "residual label."
        )
    if refused or posture is None:
        return refuse(
            "Evidence coverage is below the floor, so no posture is published and no residual tier "
            "can be derived. That is an ADVERSE result, not a neutral one: treat the inherent tier "
            "as the current exposure until evidence is obtained."
        )
    if not inherent.published:
        return refuse(inherent.basis)

    band = posture_band(posture)
    assert inherent.tier is not None
    tier = _RESIDUAL[band][inherent.tier]

    escalated_from: ResidualTier | None = None
    if substitutability == "sole_source":
        idx = _LADDER.index(tier)
        if idx < len(_LADDER) - 1:
            escalated_from, tier = tier, _LADDER[idx + 1]
        # Already `critical`: nothing above it, and inventing a band above the top to express
        # "worse than critical" would break the published vocabulary to say something the word
        # critical already says.

    caveats = [
        "Residual risk is a DETERMINISTIC LOOKUP over the published posture and the declared "
        "inherent tier. It is recomputed on every read and stored nowhere, so it can never drift "
        "from the two inputs it is derived from. Dispute an input, not the cell.",
        "Inherent exposure is client-declared and never inferred. We do not know what a vendor "
        "holds for a given buyer, and guessing would put our label on their exposure.",
        "Posture and inherent risk run on different clocks: posture moves when the vendor's "
        "controls move, inherent risk moves when the relationship changes.",
    ]
    if inherent.provisional:
        caveats.append(
            "THE INHERENT TIER IS PROVISIONAL. It was declared on the inherent register and has "
            "not been confirmed by the accountable relationship owner, so this residual tier is "
            "the right shape and may be the wrong cell. Confirming the two inputs is a "
            "five-minute question to one person, and it is the cheapest accuracy available on "
            "this page."
        )
    if inherent.tier in ("high", "critical") and band == "strong":
        caveats.append(
            "A strong posture against high inherent exposure does not resolve to low residual "
            "risk. The controls look good today; the exposure is what you carry if that changes."
        )
    if escalated_from is not None:
        caveats.append(
            f"ESCALATED ONE BAND FOR SOLE SOURCE. The matrix cell for this posture and inherent "
            f"tier is {_RESIDUAL_LABELS[escalated_from]}; the published tier is "
            f"{_RESIDUAL_LABELS[tier]} because this relationship is declared irreplaceable. "
            f"Substitutability does not change the vendor's controls — it changes what a failure "
            f"costs you, which is why it moves the residual tier and never the posture."
        )
    elif substitutability == "sole_source":
        caveats.append(
            "This relationship is declared sole source and the residual tier is already Critical, "
            "so there is no band to escalate into. That is the ceiling of the published "
            "vocabulary, not an absence of the escalation."
        )
    return ResidualRisk(residual=tier, residual_label=_RESIDUAL_LABELS[tier], posture=posture,
                        posture_band=band, inherent=inherent, published=True, caveats=caveats,
                        substitutability=substitutability, escalated_from=escalated_from)


def matrix() -> list[dict[str, object]]:
    """The published table, for a UI that wants to show a reader where their cell sits."""
    return [
        {"posture_band": band,
         "cells": {tier: _RESIDUAL_LABELS[_RESIDUAL[band][tier]] for tier in _TIERS}}
        for band in ("strong", "moderate", "weak", "poor")
    ]
