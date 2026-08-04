"""Supplier peer benchmarking — the comparison and contextualisation layer.

THE ONE-SENTENCE CONTRACT. This package answers one customer question — *"is this supplier's risk
posture normal, good, or poor compared to similar suppliers?"* — and it answers it by READING
posture, confidence and domain scores that already exist. It is not a scoring engine. It holds no
finding, computes no penalty, and has no write path to a score. If every line here were deleted,
every published score would be byte-identical, and `test_benchmarking.py` asserts exactly that.

WHY IT IS A PACKAGE AND NOT AN EDIT TO `benchmark.py`. The superseded module keys cohorts on four
firmographic dimensions (sector x revenue x headcount x region = 1,500 cells) with `min_cohort_n: 1`,
and falls back to six hard-coded postures published as `n=6`. Each of those was deliberate for a
demo and each is wrong for an enterprise deployment: 1,500 cells cannot reach n>=30 from hundreds of
suppliers, a threshold of 1 publishes a "median" over a single company, and `n=6` beside "reference
baseline" reads to every human being as six real companies. The mechanism is replaced rather than
tuned. `benchmark.py` stays in the tree for one release so stored snapshots keep deserialising.

THE FIVE DECISIONS THIS PACKAGE IMPLEMENTS are recorded in `docs/benchmarking-design.md`. In short:
cohorts key on SUPPLIER properties only (`data_access_scope` is a relationship property and routes
to interpretation); synthetic reference points are a HARD GATE on any percentile or quartile; member
refs are stored for dispute and never published; and quartiles need n>=8, percentiles n>=30, with n
disclosed either way.

MODULE MAP, in dependency order:

    config.py         typed loader; validates the hard rules at LOAD time, not serve time
    models.py         the published shapes — assignment, snapshot, placement, dispute
    cohorts.py        size_band derivation + the deepen-then-widen ladder
    discrimination.py per-cohort "does this signal vary at all?"
    snapshot.py       the append-only cohort snapshot a placement is reproducible against
    placement.py      the thresholds, the estimators, the deltas, the reliability factors
    expectation_gap.py  E10a: the signed gap against the cohort, and what is driving it
    narrative.py      templated prose for the two audiences; refuses to render on a missing field
"""

from __future__ import annotations

from .cohorts import assign_cohort, derive_size_band
from .config import BenchmarkingConfig, BenchmarkingConfigError, get_benchmarking_config
from .discrimination import discrimination_report
from .expectation_gap import ExpectationGapReport, GapDriver, expectation_gap
from .models import (
    BenchmarkPlacement,
    CohortAssignment,
    CohortDispute,
    CohortSnapshot,
    DiscriminationVerdict,
    DomainPlacement,
    PeerRecord,
    SupplierFirmographics,
)
from .narrative import render_procurement, render_security
from .placement import build_placement
from .snapshot import build_snapshot

__all__ = [
    "BenchmarkPlacement",
    "BenchmarkingConfig",
    "BenchmarkingConfigError",
    "CohortAssignment",
    "CohortDispute",
    "CohortSnapshot",
    "DiscriminationVerdict",
    "DomainPlacement",
    "ExpectationGapReport",
    "GapDriver",
    "PeerRecord",
    "SupplierFirmographics",
    "assign_cohort",
    "build_placement",
    "build_snapshot",
    "derive_size_band",
    "discrimination_report",
    "expectation_gap",
    "get_benchmarking_config",
    "render_procurement",
    "render_security",
]
