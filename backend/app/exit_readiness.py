"""P8 — exit readiness and substitutability: what happens if this vendor has to go.

WHY THIS IS THE LAST HOP FROM "HOW SAFE IS THIS VENDOR" TO "WHAT DO WE DO ABOUT IT". Posture,
residual risk and concentration all answer questions about the relationship as it stands. This one
answers the question a buyer only asks once things go wrong: if we had to leave, could we, and how
fast. `sole_source × poor Posture` is the single most useful procurement alert this system can
raise — a critical dependency, no fallback, and weak observable controls, all three at once.

CLIENT-SUPPLIED, NEVER INFERRED — same discipline `criticality` and `data_access_scope` follow, and
for the same reason: switching cost, contractual lock-in and data portability are not observable
from outside, and guessing would be our opinion dressed as the buyer's exposure. `substitutability`
rides on `VendorProfile` exactly like `criticality` does (same code path, same client-declared rule).

THREE THINGS THIS MODULE CAN DERIVE FROM PUBLIC EVIDENCE, AND NO MORE:

  * FOURTH-PARTY DEPENDENCY -> WHAT TRAVELS WITH AN EXIT. This vendor's own fourth-party providers
    (P1's enumeration). A replacement that shares none of them is a genuinely clean break; one that
    shares several means part of the technical dependency does not actually change hands.
  * SECTOR + COHORT -> WHETHER SUBSTITUTES EXIST IN THE MARKET. The size of this vendor's peer
    cohort is evidence that vendors of a similar profile exist — never evidence that any one of
    them is a functional replacement. Sector and size similarity is not equivalence.
  * GOING-CONCERN -> URGENCY. A Continuity flag on a sole-source vendor turns "replaceable in
    principle" into "replace on a deadline" — the two facts compound and neither module states so
    on its own.

WHAT IS DELIBERATELY NOT HERE: switching cost, contractual lock-in, data portability / export
terms, notice periods, transition assistance. None of it is observable from outside, and every
report says so and points at the Evidence Request Pack (P3) — the mechanism for obtaining it from
the vendor rather than guessing at it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .residual_risk import PostureBand, posture_band

AlertLevel = Literal["critical", "elevated", "none"]

#: What an exit plan cannot get from public evidence, and where it must come from instead. Every
#: one of these is a question a vendor can be asked; none of them can be observed.
_NOT_DERIVABLE = [
    "switching cost", "contractual lock-in", "data portability / export terms",
    "minimum notice period", "transition assistance obligations",
]

_CAVEATS = [
    "Substitutability is CLIENT-DECLARED, never inferred — switching cost, lock-in and data "
    "portability are not observable from outside. See the Evidence Request Pack for how to obtain "
    "them from the vendor directly.",
    "Posture measures observed CONTROLS, not replaceability. A strong posture on a sole-source "
    "vendor does not reduce exit exposure — it only means the vendor you cannot replace is "
    "currently well-run.",
    "Fourth-party dependencies here are this vendor's OWN reliance on other providers (P1), not the "
    "buyer's. They describe what a replacement would also have to account for, not what the buyer "
    "loses by exiting.",
]


@dataclass(frozen=True)
class ExitReadiness:
    vendor_ref: str
    substitutability: str | None
    posture: int | None
    posture_band: PostureBand | None
    alert_level: AlertLevel
    dependency_providers: list[str]
    cohort_peer_count: int | None
    going_concern_standing: str | None
    caveats: list[str] = field(default_factory=list)

    def headline(self) -> str:
        if self.alert_level == "critical":
            return (
                f"SOLE SOURCE, POOR POSTURE. This relationship is declared irreplaceable and its "
                f"observed posture ({self.posture}) is in the weakest band. This is the single most "
                f"useful procurement alert this system can raise — plan the exit conversation now, "
                f"not after an incident forces it."
            )
        if self.alert_level == "elevated":
            return (
                f"Sole source, weak posture ({self.posture}). Not yet the floor, but a declared "
                f"irreplaceable vendor with a weakening observed posture is worth an early "
                f"conversation about the exit path before it becomes urgent."
            )
        if self.substitutability is None:
            return (
                "Substitutability is not declared for this relationship. The alert this module "
                "exists to raise — sole source against a poor posture — cannot be raised until the "
                "buyer says how replaceable this vendor is."
            )
        return ("No exit alert. Either this relationship is not sole-source, or its posture is not "
               "in the weakest band.")


def exit_readiness(
    vendor_ref: str,
    *,
    substitutability: str | None,
    posture: int | None,
    dependency_providers: list[str] = (),
    cohort_peer_count: int | None = None,
    going_concern_standing: str | None = None,
) -> ExitReadiness:
    """Combine the client-declared exposure with what public evidence can add. Nothing here is
    stored or scored — recomputed on every read, the same discipline `residual_risk` follows."""
    band = posture_band(posture) if posture is not None else None
    if substitutability == "sole_source" and band == "poor":
        level: AlertLevel = "critical"
    elif substitutability == "sole_source" and band == "weak":
        level = "elevated"
    else:
        level = "none"

    caveats = list(_CAVEATS)
    if going_concern_standing and going_concern_standing != "sound":
        caveats.append(
            f"A going-concern flag is recorded against this entity (standing: "
            f"{going_concern_standing}). Paired with declared substitutability, that is what turns "
            f"'replaceable in principle' into 'replace on a deadline' — see the Continuity report."
        )
    if cohort_peer_count is not None:
        caveats.append(
            f"{cohort_peer_count} vendor(s) share this vendor's peer cohort (sector, size, "
            f"region). That is evidence substitutes EXIST in the market, not evidence any one of "
            f"them is a viable replacement — sector and size similarity is not functional "
            f"equivalence."
        )
    else:
        caveats.append(
            "No peer cohort is available for this vendor, so market substitute availability cannot "
            "be estimated from public data."
        )

    return ExitReadiness(
        vendor_ref=vendor_ref, substitutability=substitutability, posture=posture,
        posture_band=band, alert_level=level, dependency_providers=list(dependency_providers),
        cohort_peer_count=cohort_peer_count, going_concern_standing=going_concern_standing,
        caveats=caveats,
    )


def as_dict(report: ExitReadiness) -> dict[str, Any]:
    return {
        "vendor_ref": report.vendor_ref,
        "substitutability": report.substitutability,
        "posture": report.posture,
        "posture_band": report.posture_band,
        "alert_level": report.alert_level,
        "headline": report.headline(),
        "what_travels_with_an_exit": {
            "dependency_providers": report.dependency_providers,
            "note": (
                "This vendor's own fourth-party dependencies. A replacement that shares several of "
                "these lowers the practical switching cost; sharing none of them means the exit is "
                "a genuinely clean break."
                if report.dependency_providers else
                "No fourth-party dependencies were detected for this vendor from public evidence."
            ),
        },
        "market_substitutes": {
            "cohort_peer_count": report.cohort_peer_count,
            "note": (
                f"{report.cohort_peer_count} vendor(s) in the same peer cohort (sector, size, "
                f"region) — evidence substitutes exist in the market, not that any one is a "
                f"functional replacement."
                if report.cohort_peer_count else
                "No peer cohort available — sector or size could not be established."
            ),
        },
        "going_concern_standing": report.going_concern_standing,
        "not_derivable_from_osint": {
            "items": list(_NOT_DERIVABLE),
            "next_step": (
                "None of this is observable from outside. Ask for it via the Evidence Request Pack "
                "(P3) — GET /api/vendors/{ref}/evidence-request-pack."
            ),
        },
        "caveats": report.caveats,
    }
