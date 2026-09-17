"""Typed access to the `benchmarking:` block of benchmarks.yaml, validated at LOAD time.

WHY VALIDATION HAPPENS AT IMPORT AND NOT AT SERVE TIME. The hard rules in this system are the
product: *never a percentile below n=30, never a quartile below n=8, never a rung that pools every
industry together*. A config that violates one of those does not produce a slightly-off card, it
produces a confidently-worded lie. So a bad file stops the process at startup — the same discipline
`scoring_config.py` applies when a penalising band has no plain-English reason, and the same one
`BenchmarkConfigError` already applies to an uncited `expected_posture`.

The thresholds are readable and arguable in YAML on purpose (a client can be walked through them in
a room without a deploy), but three of them are floored in code below. `min_quartile_n` and
`min_percentile_n` have a lower bound because "make it 3 for the demo" is exactly how the superseded
module ended up shipping `min_cohort_n: 1`, and a demo setting that survives into production is
indistinguishable from a decision nobody made.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "benchmarks.yaml"

# The floors. A YAML edit may raise these; it may not lower them past here.
#
# 8 is where a quartile stops being arithmetic theatre: below it a single peer is more than an eighth
# of the population, so "bottom quartile" can flip on one supplier joining.
# 30 is the conventional floor for treating a sample percentile as a point estimate at all; below it
# the sampling error is wider than the gap between adjacent percentile labels.
_ABSOLUTE_MIN_QUARTILE_N = 8
_ABSOLUTE_MIN_PERCENTILE_N = 30

# Every ladder rung must be anchored on one of these. There is deliberately no rung meaning "every
# supplier ever assessed" — see `_validate_ladder`.
_SECTOR_ANCHORS = frozenset({"sector", "sector_group"})

_KNOWN_DIMENSIONS = frozenset({"sector", "sector_group", "size_band", "delivery_model"})

_PLACEMENT_BUCKETS = ("bottom_quartile", "lower_mid", "upper_mid", "top_quartile",
                      "insufficient_peers")
_SCOPES = ("low", "medium", "high", "critical")


class BenchmarkingConfigError(ValueError):
    """Raised at load time. Loud at startup, never quiet at serve time."""


@dataclass(frozen=True)
class SizeBandRule:
    """The published, versioned derivation of a single `size_band` from two raw inputs.

    Carried as its own object because the RULE is what a supplier disputes, not the band. A dispute
    reads *"headcount 240 -> small, revenue A$310M -> large, resolved `large` by rule v1 (`max`)"*
    and can argue with any of the four parts.
    """

    rule_version: int
    resolve: str                      # max | headcount | revenue
    order: tuple[str, ...]
    employees: dict[str, int]
    revenue_aud: dict[str, int]


class BenchmarkingConfig:
    def __init__(self, data: dict[str, Any], path: Path) -> None:
        self._d = data.get("benchmarking") or {}
        # `fx_to_aud` lives in the v1 top-level block; revenue banding needs it and there is no
        # reason for two deployments' worth of exchange rates in one file.
        self._fx = {k.upper(): float(v) for k, v in (data.get("fx_to_aud") or {}).items()}
        self.path = path
        if not self._d:
            raise BenchmarkingConfigError(
                f"{path} has no `benchmarking:` block. The peer-comparison layer cannot infer its "
                f"own thresholds — see docs/design_decisions.md Part 1"
            )
        self._validate()

    # --- identity ---

    def version(self) -> str:
        return str(self._d.get("version", "0"))

    # --- cohort ---

    def _cohort(self) -> dict[str, Any]:
        return self._d.get("cohort") or {}

    def dimensions(self) -> tuple[str, ...]:
        return tuple(self._cohort().get("dimensions") or ())

    def ladder(self) -> list[tuple[str, ...]]:
        """The rungs, most specific first. Assignment walks this in order."""
        return [tuple(rung) for rung in (self._cohort().get("ladder") or [])]

    def floor(self) -> tuple[str, ...]:
        """The rung at which a comparison stops being 'exact'. Rungs below it report as widened."""
        return tuple(self._cohort().get("floor") or ())

    def min_quartile_n(self) -> int:
        return int(self._cohort().get("min_quartile_n", _ABSOLUTE_MIN_QUARTILE_N))

    def min_percentile_n(self) -> int:
        return int(self._cohort().get("min_percentile_n", _ABSOLUTE_MIN_PERCENTILE_N))

    def min_domain_n(self) -> int:
        return int(self._cohort().get("min_domain_n", _ABSOLUTE_MIN_QUARTILE_N))

    # --- size band ---

    def size_band_rule(self) -> SizeBandRule:
        raw = self._d.get("size_band") or {}
        return SizeBandRule(
            rule_version=int(raw.get("rule_version", 1)),
            resolve=str(raw.get("resolve", "max")),
            order=tuple(raw.get("order") or ()),
            employees=dict(raw.get("employees") or {}),
            revenue_aud=dict(raw.get("revenue_aud") or {}),
        )

    def fx_to_aud(self) -> dict[str, float]:
        return dict(self._fx)

    # --- sector groups ---

    def sector_groups(self) -> dict[str, tuple[str, ...]]:
        return {k: tuple(v) for k, v in (self._d.get("sector_groups") or {}).items()}

    def sector_group_of(self, sector: str) -> str | None:
        """The published rollup a sector belongs to, or None.

        None is a real answer, not a failure: an unmapped sector simply has no `sector_group` rung,
        so its ladder ends at `sector` and it refuses below that. Inventing a group for it would
        pool it with whichever sectors happened to be listed first.
        """
        for group, members in self.sector_groups().items():
            if sector in members:
                return group
        return None

    # --- discrimination ---

    def _discrimination(self) -> dict[str, Any]:
        return self._d.get("discrimination") or {}

    def discrimination_min_observations(self) -> int:
        return int(self._discrimination().get("min_observations", 8))

    def min_coefficient_of_variation(self) -> float:
        return float(self._discrimination().get("min_coefficient_of_variation", 0.02))

    def max_modal_share(self) -> float:
        return float(self._discrimination().get("max_modal_share", 0.95))

    def zero_iqr_is_flat(self) -> bool:
        return bool(self._discrimination().get("zero_iqr_is_flat", True))

    # --- reliability ---

    def _reliability(self) -> dict[str, Any]:
        return self._d.get("reliability") or {}

    def rung_exactness(self, rung: tuple[str, ...]) -> float:
        """How much the comparison is worth given how far the ladder had to walk.

        Defaults to 0.5 for an unlisted rung rather than 1.0: an unknown rung is more likely a
        widened one somebody forgot to price than a perfect match.
        """
        table = self._reliability().get("rung_exactness") or {}
        return float(table.get("+".join(rung), 0.5))

    def stale_peer_days(self) -> int:
        return int(self._reliability().get("stale_peer_days", 365))

    def sample_saturation_n(self) -> int:
        return max(1, int(self._reliability().get("sample_saturation_n", 30)))

    def flag_supplier_confidence_below(self) -> float:
        return float(self._reliability().get("flag_supplier_confidence_below", 0.6))

    # --- narrative ---

    def _narrative(self) -> dict[str, Any]:
        return self._d.get("narrative") or {}

    def narrative_version(self) -> int:
        return int(self._narrative().get("version", 1))

    def template(self, audience: str, key: str) -> str | None:
        return (self._narrative().get(audience) or {}).get(key)

    def template_requires(self, audience: str, key: str) -> tuple[str, ...]:
        return tuple((self._narrative().get(audience) or {}).get(key) or ())

    def action_for(self, bucket: str, scope: str) -> str | None:
        """The deterministic (placement x data_access_scope) lookup.

        THE ONLY PLACE `data_access_scope` ENTERS THE SYSTEM, and it enters interpretation rather
        than the cohort key — decision 1. A scope with no entry returns None and the narrative omits
        the recommendation rather than inventing one.
        """
        return ((self._narrative().get("actions") or {}).get(bucket) or {}).get(scope)

    def action_disclaimer(self) -> str:
        return str(self._narrative().get("disclaimer", "")).strip()

    # --- disclosure ---

    def _disclosure(self) -> dict[str, Any]:
        return self._d.get("disclosure") or {}

    def never_publish_member_refs(self) -> bool:
        return bool(self._disclosure().get("never_publish_member_refs", True))

    def notate_open_disputes(self) -> bool:
        return bool(self._disclosure().get("notate_open_disputes", True))

    def synthetic_caveat(self) -> str:
        return str(self._disclosure().get("synthetic_caveat", "")).strip()

    def reference_line_caveat(self) -> str:
        return str(self._disclosure().get("reference_line_caveat", "")).strip()

    def self_selection_caveat(self) -> str:
        """Reused from the v1 disclosure block — the limitation that never goes away."""
        return str(
            ((self._d.get("disclosure") or {}).get("self_selection_caveat"))
            or "Peers are suppliers assessed in this deployment, not a random sample of the industry."
        ).strip()

    # ------------------------------------------------------------------ validation

    def _validate(self) -> None:
        self._validate_thresholds()
        self._validate_ladder()
        self._validate_size_band()
        self._validate_sector_groups()
        self._validate_narrative()

    def _validate_thresholds(self) -> None:
        q, p = self.min_quartile_n(), self.min_percentile_n()
        if q < _ABSOLUTE_MIN_QUARTILE_N:
            raise BenchmarkingConfigError(
                f"cohort.min_quartile_n is {q}, below the floor of {_ABSOLUTE_MIN_QUARTILE_N}. "
                f"Below eight peers a single supplier is more than an eighth of the population and "
                f"a quartile flips on one of them joining. This floor is the product, not a knob."
            )
        if p < _ABSOLUTE_MIN_PERCENTILE_N:
            raise BenchmarkingConfigError(
                f"cohort.min_percentile_n is {p}, below the floor of {_ABSOLUTE_MIN_PERCENTILE_N}. "
                f"A sample percentile below thirty has sampling error wider than the gap between "
                f"adjacent percentile labels — publish the quartile instead."
            )
        if p < q:
            raise BenchmarkingConfigError(
                f"cohort.min_percentile_n ({p}) is below min_quartile_n ({q}): the coarser "
                f"statistic would need MORE peers than the finer one"
            )
        if self.min_domain_n() < _ABSOLUTE_MIN_QUARTILE_N:
            raise BenchmarkingConfigError(
                f"cohort.min_domain_n is {self.min_domain_n()}, below the floor of "
                f"{_ABSOLUTE_MIN_QUARTILE_N}. A per-domain median needs the same population a "
                f"per-supplier one does."
            )

    def _validate_ladder(self) -> None:
        ladder = self.ladder()
        if not ladder:
            raise BenchmarkingConfigError("cohort.ladder is empty: no rung means no comparison")

        for rung in ladder:
            unknown = set(rung) - _KNOWN_DIMENSIONS
            if unknown:
                raise BenchmarkingConfigError(
                    f"cohort.ladder rung {rung} uses unknown dimension(s) {sorted(unknown)}; "
                    f"known: {sorted(_KNOWN_DIMENSIONS)}"
                )
            if not (set(rung) & _SECTOR_ANCHORS):
                # THE FLOOR OF THE LADDER, AND IT IS NOT NEGOTIABLE. A rung anchored on neither
                # `sector` nor `sector_group` compares a bank against every supplier ever assessed —
                # the exact meaningless comparison this feature exists to refuse.
                raise BenchmarkingConfigError(
                    f"cohort.ladder rung {rung} is anchored on neither `sector` nor "
                    f"`sector_group`: a peer group that spans every industry is not a peer group"
                )
            if "sector" in rung and "sector_group" in rung:
                raise BenchmarkingConfigError(
                    f"cohort.ladder rung {rung} names both `sector` and `sector_group`; the group "
                    f"is the ROLLUP of the sector, so pairing them is a rung that means `sector`"
                )

        # Most specific first, so `assign_cohort` can take the first rung that satisfies and stop.
        # A mis-ordered ladder would silently assign the WIDEST satisfying cohort — which still
        # produces a plausible-looking card, and is the failure this check exists to catch.
        widths = [len(r) for r in ladder]
        if widths != sorted(widths, reverse=True):
            raise BenchmarkingConfigError(
                f"cohort.ladder must run most-specific first; got widths {widths}. Assignment "
                f"takes the FIRST satisfying rung, so a mis-ordered ladder quietly assigns the "
                f"loosest cohort that clears the threshold"
            )

        if self.floor() and tuple(self.floor()) not in {tuple(r) for r in ladder}:
            raise BenchmarkingConfigError(
                f"cohort.floor {self.floor()} is not one of the ladder rungs"
            )

    def _validate_size_band(self) -> None:
        rule = self.size_band_rule()
        if rule.resolve not in ("max", "headcount", "revenue"):
            raise BenchmarkingConfigError(
                f"size_band.resolve must be max | headcount | revenue, got {rule.resolve!r}"
            )
        if len(rule.order) < 2:
            raise BenchmarkingConfigError("size_band.order needs at least two bands")

        # Every named bound must BE a band, and the bounds must ascend with the order. A descending
        # bound silently files large suppliers as micro, which no test of the output would catch
        # because the output stays well-formed.
        for field, bounds in (("employees", rule.employees), ("revenue_aud", rule.revenue_aud)):
            unknown = set(bounds) - set(rule.order)
            if unknown:
                raise BenchmarkingConfigError(
                    f"size_band.{field} names band(s) {sorted(unknown)} absent from size_band.order"
                )
            ordered = [bounds[b] for b in rule.order if b in bounds]
            if ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
                raise BenchmarkingConfigError(
                    f"size_band.{field} bounds must strictly ascend in size_band.order; got "
                    f"{ordered}"
                )
            # The top band is unbounded by construction, so it must NOT carry a bound.
            if rule.order[-1] in bounds:
                raise BenchmarkingConfigError(
                    f"size_band.{field} gives a bound for the top band {rule.order[-1]!r}, which "
                    f"is open-ended by definition — remove it"
                )

    def _validate_sector_groups(self) -> None:
        seen: dict[str, str] = {}
        for group, members in self.sector_groups().items():
            for sector in members:
                if sector in seen:
                    # A sector in two groups makes `sector_group_of` order-dependent, so the same
                    # supplier could land in a different rollup after an unrelated YAML re-order.
                    raise BenchmarkingConfigError(
                        f"sector {sector!r} appears in both {seen[sector]!r} and {group!r}: "
                        f"sector_group must be a partition, or the rollup is order-dependent"
                    )
                seen[sector] = group

    def _validate_narrative(self) -> None:
        for audience in ("security", "procurement"):
            for key in ("placed", "insufficient"):
                if not self.template(audience, key):
                    raise BenchmarkingConfigError(
                        f"narrative.{audience}.{key} is missing: a placement with no sentence is "
                        f"a number nobody can act on"
                    )
        # The action table must be total over (bucket x scope). A missing cell would silently drop
        # the recommendation from a procurement card, which reads as "no action needed".
        missing = [
            f"{bucket}.{scope}"
            for bucket in _PLACEMENT_BUCKETS
            for scope in _SCOPES
            if not self.action_for(bucket, scope)
        ]
        if missing:
            raise BenchmarkingConfigError(
                f"narrative.actions is incomplete — no entry for {missing}. The table must be "
                f"total over placement x data_access_scope, or a card silently omits its "
                f"recommendation and reads as 'no action required'"
            )
        if not self.action_disclaimer():
            raise BenchmarkingConfigError(
                "narrative.disclaimer is required: suggested contractual actions must be marked as "
                "drafting guidance rather than advice"
            )


def load_benchmarking_config(path: Path | None = None) -> BenchmarkingConfig:
    from ..config import get_settings

    p = path or get_settings().benchmarks_yaml_path or _DEFAULT_PATH
    if not p.exists():
        raise BenchmarkingConfigError(f"benchmarks.yaml not found at {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return BenchmarkingConfig(data, p)


@lru_cache
def get_benchmarking_config() -> BenchmarkingConfig:
    return load_benchmarking_config()
