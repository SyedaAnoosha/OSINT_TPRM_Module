"""Cohort assignment — who this supplier may lawfully be compared against.

TWO JOBS, AND THEY ARE SEPARATE ON PURPOSE:

  1. `derive_size_band` collapses headcount and revenue into ONE band, by a published versioned
     rule, retaining both inputs so the derivation is what a supplier disputes.
  2. `assign_cohort` walks the deepen-then-widen ladder and returns exactly one cohort, plus the
     rationale for every rung it tried.

WHY THE LADDER RUNS THIS WAY. The superseded module started at a four-dimension cohort and WIDENED
by dropping dimensions. That inverts the density problem: the most specific rung is the one least
likely to hold anybody, so the common path was "try the thing that never works, then try the next
thing that never works". Here the FLOOR is `sector + size_band` — the comparison that should almost
always be available — and the ladder only DEEPENS past it when density genuinely allows, then widens
below it when it does not. Same rungs, opposite default, and the default is what ships.

ASSIGNMENT IS NOT PLACEMENT. Every supplier gets exactly one cohort even when that cohort is far too
thin to compare them against; `placeable` records which case it is. A supplier in a sparse sector
with no cohort at all has nothing to show, nothing to dispute and nothing to fill — so they get the
widest rung attempted and an honest refusal, rather than no assignment.
"""

from __future__ import annotations

from collections.abc import Callable

from .config import BenchmarkingConfig, SizeBandRule, get_benchmarking_config
from .models import (
    CohortAssignment,
    LadderRungResult,
    PeerRecord,
    SizeBand,
    SizeBandDerivation,
    SupplierFirmographics,
)

#: A lookup takes a resolved set of cohort dimensions and returns every peer matching ALL of them.
#: A callable rather than a store keeps this module free of persistence concerns and makes every rung
#: testable without a database — the one piece of the superseded module's shape worth keeping
#: verbatim.
PeerLookup = Callable[[dict[str, str]], list[PeerRecord]]

_RUNG_LABELS = {
    ("sector", "size_band", "delivery_model"): "sector + size + delivery model",
    ("sector", "size_band"): "sector + size",
    ("sector",): "sector (all sizes)",
    ("sector_group",): "sector group (related industries)",
}


def rung_label(rung: tuple[str, ...]) -> str:
    return _RUNG_LABELS.get(rung, " + ".join(rung))


# --------------------------------------------------------------------------- size band


def _band_of(value: float | None, bounds: dict[str, int], order: tuple[str, ...]) -> SizeBand | None:
    """Value -> band by exclusive upper bounds. None stays None; a supplier is never guessed into a
    band, because a guessed band is a guessed peer group and every statistic downstream inherits it."""
    if value is None or value < 0:
        return None
    for band in order[:-1]:
        limit = bounds.get(band)
        if limit is not None and value < limit:
            return band  # type: ignore[return-value]
    return order[-1]  # type: ignore[return-value]


def _to_aud(amount: float | None, currency: str | None, cfg: BenchmarkingConfig) -> float | None:
    """Convert for BANDING ONLY.

    The reported revenue always keeps its own currency on the supplier record. Band edges are
    order-of-magnitude boundaries, so a stale rate cannot move a supplier except at the very margin —
    but a converted figure SHOWN to a user would be a number we invented. An unconvertible currency
    yields no band rather than being silently treated as AUD.
    """
    if amount is None:
        return None
    if not currency:
        return float(amount)
    rate = cfg.fx_to_aud().get(str(currency).upper())
    return float(amount) * rate if rate else None


def derive_size_band(
    firmographics: SupplierFirmographics, cfg: BenchmarkingConfig | None = None
) -> SizeBandDerivation:
    """Two raw inputs -> one band, by the published rule, with the working shown.

    `resolve: max` is the shipped rule because leverage (revenue) and attack surface (headcount) EACH
    independently raise what a competent operator is expected to run — so where they disagree, the
    higher expectation is the defensible one. The alternative rules exist because that is a
    risk-appetite judgement and those belong to the deployment, not to this function.

    The DISAGREEMENT is retained rather than resolved away. A 240-person firm turning over A$310M
    bands `small` on headcount and `large` on revenue, and that tension is exactly what the
    superseded model kept two dimensions to express. One band is what n>=30 can afford; recording
    the disagreement is what keeps it honest.
    """
    cfg = cfg or get_benchmarking_config()
    rule: SizeBandRule = cfg.size_band_rule()

    revenue_aud = _to_aud(firmographics.revenue, firmographics.revenue_currency, cfg)
    emp_band = _band_of(firmographics.employees, rule.employees, rule.order)
    rev_band = _band_of(revenue_aud, rule.revenue_aud, rule.order)

    band, resolved_by = _resolve(emp_band, rev_band, rule)

    return SizeBandDerivation(
        band=band,
        rule_version=rule.rule_version,
        resolve=rule.resolve,
        employees=firmographics.employees,
        employee_band=emp_band,
        revenue_aud=revenue_aud,
        revenue_band=rev_band,
        resolved_by=resolved_by,
        disagreed=bool(emp_band and rev_band and emp_band != rev_band),
    )


def _resolve(
    emp: SizeBand | None, rev: SizeBand | None, rule: SizeBandRule
) -> tuple[SizeBand | None, str]:
    if emp is None and rev is None:
        return None, "none"
    if emp is not None and rev is None:
        return emp, "headcount"
    if rev is not None and emp is None:
        return rev, "revenue"
    # Both present.
    if emp == rev:
        return emp, "agreement"
    if rule.resolve == "headcount":
        return emp, "headcount"
    if rule.resolve == "revenue":
        return rev, "revenue"
    # `max`: the higher band, and name which input carried it.
    order = list(rule.order)
    winner = emp if order.index(emp or order[0]) > order.index(rev or order[0]) else rev
    return winner, "headcount" if winner == emp else "revenue"


# --------------------------------------------------------------------------- assignment


def cohort_key(dimensions: dict[str, str]) -> str:
    """Canonical key. Sorted so the same cohort always writes the same string, whatever order the
    dimensions were resolved in — the key is what a snapshot is filed under, so instability here
    would silently fork one cohort into two."""
    return "|".join(f"{k}={dimensions[k]}" for k in sorted(dimensions))


def assign_cohort(
    firmographics: SupplierFirmographics,
    lookup: PeerLookup,
    cfg: BenchmarkingConfig | None = None,
) -> CohortAssignment:
    """Walk the ladder; return exactly one cohort plus the rationale for every rung tried.

    `lookup` MUST exclude the subject. A cohort of one is not a peer group, and letting a supplier
    into its own comparison guarantees a flattering rank at small n — and at the boundary it is worse
    than flattering, because "n=30" that includes the subject is 29 peers and the threshold rule is
    then wrong by one.
    """
    cfg = cfg or get_benchmarking_config()
    minimum = cfg.min_quartile_n()
    size = derive_size_band(firmographics, cfg)

    available = _available_dimensions(firmographics, size, cfg)
    floor = cfg.floor()
    rationale: list[LadderRungResult] = []
    best: tuple[tuple[str, ...], dict[str, str], list[PeerRecord]] | None = None

    for rung in cfg.ladder():
        missing = [d for d in rung if not available.get(d)]
        if missing:
            # A rung needing a dimension this supplier does not have cannot be EVALUATED — skip it
            # rather than matching on a null, which would pool every unsized supplier together into
            # a cohort whose only shared property is that we could not size them.
            rationale.append(LadderRungResult(
                rung=rung, label=rung_label(rung), n=0, satisfied=False,
                skipped_reason=f"supplier has no {', '.join(missing)}",
            ))
            continue

        dims = {d: available[d] for d in rung}
        peers = lookup(dims)
        satisfied = len(peers) >= minimum
        rationale.append(LadderRungResult(
            rung=rung, label=rung_label(rung), n=len(peers), satisfied=satisfied,
        ))
        if satisfied:
            return _assignment(rung, dims, peers, size, firmographics, floor, minimum, rationale, cfg)

        # No rung has satisfied yet. Keep the FULLEST one seen rather than simply the latest: widening
        # does not always add peers — a sector_group rung can hold fewer suppliers than the sector
        # rung above it when the rollup's other sectors are unpopulated. Taking the last evaluable
        # rung would then report n=0 while a rung with four peers had already been found, throwing
        # away the best cohort available and understating what we know. Ties keep the more specific
        # rung, because it is the better comparison at equal population.
        if best is None or len(peers) > len(best[2]):
            best = (rung, dims, peers)

    if best is None:
        # No rung was even evaluable — the supplier has no sector. Assign an empty cohort so the
        # record exists, is disputable, and can be filled once the profile improves.
        return _assignment((), {}, [], size, firmographics, floor, minimum, rationale, cfg)

    rung, dims, peers = best
    return _assignment(rung, dims, peers, size, firmographics, floor, minimum, rationale, cfg)


def _available_dimensions(
    firmographics: SupplierFirmographics, size: SizeBandDerivation, cfg: BenchmarkingConfig
) -> dict[str, str | None]:
    sector = firmographics.sector
    return {
        "sector": sector,
        "sector_group": cfg.sector_group_of(sector) if sector else None,
        "size_band": size.band,
        "delivery_model": firmographics.delivery_model,
    }


def _assignment(
    rung: tuple[str, ...],
    dims: dict[str, str],
    peers: list[PeerRecord],
    size: SizeBandDerivation,
    firmographics: SupplierFirmographics,
    floor: tuple[str, ...],
    minimum: int,
    rationale: list[LadderRungResult],
    cfg: BenchmarkingConfig,
) -> CohortAssignment:
    n = len(peers)
    # "Widened" means the ladder walked BELOW the configured floor — a looser comparison than the one
    # a reader assumes they are getting, so it is disclosed rather than inferred from the rung label.
    widened = bool(rung) and len(rung) < len(floor)
    return CohortAssignment(
        cohort_key=cohort_key(dims) if dims else f"unassigned={firmographics.supplier_ref}",
        rung=rung,
        rung_label=rung_label(rung) if rung else "no cohort (supplier has no sector)",
        dimensions=dims,
        n=n,
        placeable=n >= minimum,
        widened=widened,
        size_band=size,
        sector_group=cfg.sector_group_of(firmographics.sector) if firmographics.sector else None,
        rationale=rationale,
    )
