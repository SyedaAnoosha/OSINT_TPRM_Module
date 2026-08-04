"""P1 — fourth-party concentration across the book. The half `fourth_party.py` could not do alone.

    "Nine of your twenty-three vendors authenticate through Okta. Four are Tier-1. A single Okta
     outage removes 17% of your supplier book simultaneously."

WHY THIS IS THE MOST DIFFERENTIATED OUTPUT IN THE SYSTEM. No per-vendor score can express it — each
of those nine vendors may score an A — and **no commercial rating publishes it from free data**. It
is also the one finding that is strictly a property of the BUYER'S BOOK rather than of any supplier,
which is why it lives here and not on a scorecard.

WHY IT WAS DAYS OF WORK RATHER THAN WEEKS. Both halves were already built and nothing joined them.
`fourth_party.extract` has enumerated providers per vendor since Phase 2 and says so in its own
docstring — *"the finding that actually matters is a PORTFOLIO statement, and that half needs the
platform"*. Meanwhile `/api/portfolio` shipped a field called `concentration` that was only
*high-criticality vendors below 60* and never called the extractor once. Two correct halves, one
misleading label, no join.

RANK BY CRITICAL SHARE, NEVER BY RAW COUNT. A provider sitting under 90% of a book's stationery
suppliers is not a finding; one sitting under 50% of its Tier-1 suppliers is a board paper. Sorting
by count puts the first at the top of the page, and a report whose first row is noise trains the
reader to skip the section.

DISCLOSED, NEVER SCORED — inherited from `fourth_party.py` and re-asserted here because the
aggregate is where the temptation returns. Penalising every Okta customer for an Okta CVE would
punish thousands of vendors for a dependency they share with their competitors, AND double-count the
same risk across every vendor in one book. This module emits no findings and imports nothing from
the scoring path.

TIER-2 VISIBILITY ONLY, and the caveat travels with every figure. We see who the VENDOR depends on;
we do not see who THEY depend on. A book with no visible concentration may still funnel through one
provider two hops down, and this analysis cannot see it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .fourth_party import Dependency

#: The share of a book's CRITICAL suppliers on one provider, in one category, at which a single
#: outage stops being a risk and starts being a continuity event. Not a scoring threshold — nothing
#: here scores — it selects the wording and the ranking flag.
_SPOF_CRITICAL_SHARE = 0.50


@dataclass
class ProviderConcentration:
    """One fourth party, and how much of this book rides on it."""

    provider: str
    category: str
    dependent_vendors: list[str] = field(default_factory=list)
    dependent_critical: list[str] = field(default_factory=list)
    total_scored: int = 0
    total_critical: int = 0
    detected_via: list[str] = field(default_factory=list)

    @property
    def dependent_count(self) -> int:
        return len(self.dependent_vendors)

    @property
    def book_share(self) -> float:
        return (self.dependent_count / self.total_scored) if self.total_scored else 0.0

    @property
    def critical_share(self) -> float | None:
        """THE BOARD NUMBER. None when the buyer has declared no critical vendors at all —
        a share with no denominator is not a small share, it is no share, and rendering 0%
        would read as *"none of your critical vendors depend on this"* when the truth is
        *"you have not told us which vendors are critical"*."""
        if not self.total_critical:
            return None
        return len(self.dependent_critical) / self.total_critical

    @property
    def single_point_of_failure(self) -> bool:
        share = self.critical_share
        return share is not None and share >= _SPOF_CRITICAL_SHARE

    def cited(self) -> str:
        """The published sentence, built to be read aloud in a meeting."""
        lead = (f"{self.dependent_count} of {self.total_scored} scored vendors "
                f"({self.book_share:.0%} of the book) depend on {self.provider} for "
                f"{self.category.replace('_', ' ')}")
        share = self.critical_share
        if share is None:
            return lead + ". No vendor in this book has been marked business-critical, so the " \
                          "critical-supplier share cannot be computed."
        return (f"{lead}. {len(self.dependent_critical)} of {self.total_critical} "
                f"business-critical vendors ({share:.0%}) are among them"
                + (" — a single point of failure." if self.single_point_of_failure else "."))


@dataclass
class ConcentrationReport:
    providers: list[ProviderConcentration] = field(default_factory=list)
    total_scored: int = 0
    total_critical: int = 0
    without_criticality: int = 0
    caveats: list[str] = field(default_factory=list)

    @property
    def single_points_of_failure(self) -> list[ProviderConcentration]:
        return [p for p in self.providers if p.single_point_of_failure]


def concentration(
    dependencies_by_vendor: dict[str, list[Dependency]],
    criticality_by_vendor: dict[str, str | None],
    *,
    min_dependents: int = 2,
) -> ConcentrationReport:
    """Roll per-vendor fourth parties up into a book-level view, ranked by critical share.

    `dependencies_by_vendor` is `fourth_party.extract` run per vendor; `criticality_by_vendor` is
    the buyer's own declaration, never inferred.

    A provider with ONE dependent is not concentration, it is a dependency — reporting it would
    bury the four rows that matter under two hundred that do not. `min_dependents` is the line, and
    it is a parameter rather than a constant so a small book can lower it and see anything at all.
    """
    scored = sorted(dependencies_by_vendor)
    critical = {ref for ref in scored if criticality_by_vendor.get(ref) == "high"}
    # COUNTED IN THE BOOK, EXCLUDED FROM THE CRITICAL SHARE — and the exclusion is stated below
    # rather than left for a reader to infer from two numbers that do not reconcile.
    undeclared = [ref for ref in scored if not criticality_by_vendor.get(ref)]

    buckets: dict[tuple[str, str], ProviderConcentration] = {}
    for ref in scored:
        for dep in dependencies_by_vendor[ref]:
            key = (dep.provider, dep.category)
            entry = buckets.get(key) or ProviderConcentration(
                provider=dep.provider, category=dep.category,
                total_scored=len(scored), total_critical=len(critical))
            if ref not in entry.dependent_vendors:
                entry.dependent_vendors.append(ref)
            if ref in critical and ref not in entry.dependent_critical:
                entry.dependent_critical.append(ref)
            for via in dep.detected_via:
                if via not in entry.detected_via:
                    entry.detected_via.append(via)
            buckets[key] = entry

    providers = [p for p in buckets.values() if p.dependent_count >= min_dependents]
    # Critical share FIRST, count only as a tiebreak. A provider under 90% of a book's stationery
    # suppliers is not a finding; one under 50% of its Tier-1 suppliers is a board paper.
    providers.sort(key=lambda p: (-(p.critical_share or 0.0), -p.dependent_count, p.provider))

    caveats = [
        "TIER-2 VISIBILITY ONLY. This shows who your VENDORS depend on. It does not show who THEY "
        "depend on — a book with no visible concentration may still funnel through one provider "
        "two hops down, and this analysis cannot see it.",
        "Concentration is DISCLOSED, NEVER SCORED. No vendor's posture is affected by who they "
        "depend on: penalising every customer of a provider would punish them for a dependency "
        "they share with their competitors, and would count the same risk once per vendor in your "
        "book.",
        "Dependencies are enumerated from public evidence already collected (MX, SPF includes, "
        "certificate transparency, response headers). A provider that leaves no public trace — a "
        "payroll processor, an offshore development partner — will not appear here.",
    ]
    if undeclared:
        caveats.append(
            f"{len(undeclared)} of {len(scored)} vendors have no criticality declared. They are "
            f"COUNTED in the book share and EXCLUDED from the critical share, so the two "
            f"percentages are drawn from different populations by design. Declaring criticality "
            f"for them is what makes the critical share the number a board can act on."
        )
    if not critical:
        caveats.insert(0, (
            "No vendor in this book is marked business-critical, so the critical share — the "
            "figure this analysis exists to produce — cannot be computed for any provider. The "
            "book share below is real but is not the board number."
        ))

    return ConcentrationReport(
        providers=providers, total_scored=len(scored), total_critical=len(critical),
        without_criticality=len(undeclared), caveats=caveats,
    )


def as_dict(report: ConcentrationReport, *, limit: int = 20) -> dict[str, Any]:
    """The published shape. Member refs are included deliberately: unlike a peer cohort, these are
    the buyer's OWN vendors, and *"which nine?"* is the first question anyone asks."""
    return {
        "total_scored": report.total_scored,
        "total_critical": report.total_critical,
        "without_criticality": report.without_criticality,
        "single_points_of_failure": [p.provider for p in report.single_points_of_failure],
        "providers": [
            {
                "provider": p.provider,
                "category": p.category,
                "dependent_count": p.dependent_count,
                "book_share": round(p.book_share, 3),
                "critical_share": None if p.critical_share is None else round(p.critical_share, 3),
                "dependent_critical_count": len(p.dependent_critical),
                "single_point_of_failure": p.single_point_of_failure,
                "dependent_vendors": p.dependent_vendors,
                "detected_via": p.detected_via,
                "cited": p.cited(),
            }
            for p in report.providers[:limit]
        ],
        "caveats": report.caveats,
    }
