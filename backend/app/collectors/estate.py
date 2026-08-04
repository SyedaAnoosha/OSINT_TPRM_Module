"""E12 — the estate: which hosts get probed, and the published rule that decides.

    "TLS 1.0 on 8 of 340 checked hosts"   instead of   "TLS 1.0 on the homepage"

THE SAMPLING RULE **IS** THE DENOMINATOR. `8 of 340` means nothing unless a reader knows how the
340 were chosen, and a vendor disputing the figure is disputing the RULE, not the count.
Attribution disagreements (*"you counted 340, we operate 40"*) are already a top-two dispute
category at N=1; fan-out multiplies both their value and their frequency. So every decision this
module makes is recorded on the sample, published on the finding, and quotable in one sentence.

ORDER OF OPERATIONS, AND IT IS NOT NEGOTIABLE:

    classify tenants  ->  drop them  ->  resolve liveness  ->  drop the dead  ->  THEN sample

Each step is in that position for a reason, and getting the order wrong produces a denominator that
is wrong in a direction nobody notices:

  1. TENANTS FIRST. A vendor hosting `customer1.vendor.com … customer9000.vendor.com` has a CT
     footprint that is an artefact of their BUSINESS MODEL, not their attack surface. Counting
     those means the best-architected SaaS vendors bottom out on estate size — the exact inversion
     E6 was built to fix, reintroduced one layer up and much harder to see.
  2. LIVENESS SECOND. CT shows certificates ISSUED, never hosts LIVE. A name certified in 2019 that
     has not resolved since is not part of an attack surface, and including it INFLATES `D_s` and
     therefore FLATTERS the vendor — `8 of 340` reads better than `8 of 60`. That is the failure in
     the comfortable direction, which is why it needs stating: nobody reviewing a report that looks
     fine will catch it.
  3. SAMPLE LAST, and DETERMINISTICALLY, seeded on the vendor ref. The same estate yields the same
     sample next month, so a change in the rate is a change in the ESTATE rather than a change in
     the dice. A random sample makes every re-scan produce a different number and no trend means
     anything.

WHAT THIS MODULE DOES NOT DO. It performs no I/O. Liveness arrives as a caller-supplied predicate
because resolving names is a collector's job and this file's whole value is that the rule can be
argued about in a test rather than against the network. The `apex` is always in the sample and
always first, because the critical ceiling arms on it specifically (see
`critical_ceiling.auto_signal_scope`).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

#: Names whose leftmost label is a bare number or a long hex/uuid-ish token are the signature of a
#: per-customer or per-build namespace rather than an operated host. Deliberately narrow: a false
#: positive here DROPS a host from the estate, and dropping real hosts flatters the vendor.
_MACHINE_LABEL = re.compile(r"^(?:\d+|[0-9a-f]{8,}|[a-z0-9]+-[0-9a-f]{8,})$")


@dataclass(frozen=True)
class EstateHost:
    """One name, and why it is or is not in the probed set."""

    name: str
    is_apex: bool = False
    excluded_as: str | None = None      # 'tenant' | 'not_live' | 'not_sampled'

    @property
    def probed(self) -> bool:
        return self.excluded_as is None


@dataclass
class EstateSample:
    """The probed host set, the denominator, and the full derivation of both."""

    vendor_ref: str
    apex: str
    hosts: list[EstateHost] = field(default_factory=list)
    discovered: int = 0
    tenants_excluded: int = 0
    not_live_excluded: int = 0
    cap: int = 1
    seed: str = ""
    rule_version: str = "1.0.0"

    @property
    def probed_names(self) -> list[str]:
        """What to actually connect to. The apex is always first."""
        return [h.name for h in self.hosts if h.probed]

    @property
    def denominator(self) -> int:
        """How many hosts a rate computed from this sample is out of.

        THE SAMPLE SIZE, NOT THE ESTATE SIZE. If 340 names survive classification and we probe 50,
        the honest denominator is 50 — we observed 50 hosts. Reporting `8 of 340` from 50 probes
        claims 290 observations we never made, which is a worse error than a small sample.
        """
        return len(self.probed_names)

    @property
    def eligible(self) -> int:
        """Live, non-tenant names — the population the sample was drawn FROM. Published beside the
        denominator so a reader can see the sampling fraction rather than infer it."""
        return self.discovered - self.tenants_excluded - self.not_live_excluded

    def rule(self) -> str:
        """The published sentence. A vendor disputing the count is disputing this."""
        return (
            f"Estate rule v{self.rule_version}: {self.discovered} names seen in certificate "
            f"transparency; {self.tenants_excluded} excluded as tenant/per-customer namespaces; "
            f"{self.not_live_excluded} excluded as not resolving; {self.eligible} eligible, of "
            f"which {self.denominator} were probed (cap {self.cap}, deterministic sample seeded on "
            f"the vendor reference so the same estate yields the same sample on every run). The "
            f"apex is always probed."
        )


def stem_of(label: str) -> str:
    """A hostname label with its enumerating tail stripped: `customer0042` -> `customer`.

    This is what makes tenant detection discriminating rather than merely aggressive. A generated
    namespace ENUMERATES a single stem (`customer1 … customer9000`); a real estate does not
    (`api`, `www`, `docs`, `status`, `mail` share nothing). Counting raw siblings cannot tell those
    apart, and a threshold low enough to catch the first classifies the second as tenants too.
    """
    return re.sub(r"[-_]?\d+$", "", label) or label


def is_tenant_namespace(name: str, apex: str, stem_counts: dict[tuple[str, str], int],
                        *, wildcard_seen: bool, sibling_threshold: int = 25) -> bool:
    """Whether this name looks like a per-customer slot rather than a host the vendor operates.

    TWO INDEPENDENT SIGNALS, and either alone is too weak:

      * A HIGH-CARDINALITY **ENUMERATED STEM** under one parent — twenty-five names that are the
        same word with different numbers on the end. That is a namespace. Twenty-five DIFFERENT
        words under one parent is a large company.
      * A MACHINE-SHAPED LEFTMOST LABEL — a bare number, a long hex token, a uuid-ish suffix.
        `acct-9f3c1e77.vendor.com` is a slot; `api.vendor.com` is not.

    THE BUG THIS SHAPE FIXES, because it is the one that matters. Counting raw siblings meant any
    vendor with more than twenty-five subdomains directly under their apex had their ENTIRE ESTATE
    classified as tenants and dropped — and a dropped estate is an empty denominator, which reads
    as "nothing to see" rather than as an error. Large companies legitimately run hundreds of
    distinct names off the apex; that is what a large company looks like.

    `wildcard_seen` widens the machine-label test but never substitutes for either. A `*.vendor.com`
    certificate says wildcards EXIST, not WHICH names are tenants — it is a signal of the pattern,
    not a solution to it, and treating it as one would drop every subdomain of every vendor that
    happens to use a wildcard certificate.

    The apex is never a tenant.
    """
    if name == apex:
        return False
    labels = name.split(".")
    if len(labels) < 2:
        return False
    leftmost, parent = labels[0], ".".join(labels[1:])

    if _MACHINE_LABEL.match(leftmost) and (wildcard_seen or
                                           stem_counts.get((parent, stem_of(leftmost)), 0) >= 2):
        return True
    return stem_counts.get((parent, stem_of(leftmost)), 0) >= sibling_threshold


def _rank(vendor_ref: str, name: str) -> str:
    """A stable pseudo-random ordering key. Seeded on the vendor so two vendors with overlapping
    name sets do not receive correlated samples, and stable across runs so a trend means something."""
    return hashlib.sha256(f"{vendor_ref}\x00{name}".encode()).hexdigest()


def build_estate(
    vendor_ref: str,
    apex: str,
    names: Iterable[str],
    *,
    cap: int = 1,
    wildcard_seen: bool = False,
    is_live: Callable[[str], bool] | None = None,
    sibling_threshold: int = 25,
) -> EstateSample:
    """Classify, filter, then sample. See the module docstring for why that order is fixed.

    `cap` is the probe budget and DEFAULTS TO 1 — apex only, which is exactly today's behaviour.
    Raising it is what switches the fan-out on, and it is a config change rather than a code change
    precisely so the runtime and politeness budget is visible to whoever raises it.

    `is_live` is supplied by the caller. None means liveness was not checked, and in that case
    NOTHING is excluded for it — an unchecked name is not a dead name, which is the same rule the
    engine applies to an unchecked signal.
    """
    apex = apex.strip().lower()
    unique = sorted({n.strip().lower() for n in names if n and n.strip()})
    if apex not in unique:
        unique.append(apex)

    # Keyed on (parent, STEM), not on parent alone. `customer1 … customer9000` collapses to one
    # stem and is caught; `api`, `www`, `docs`, `status` are four stems of one and are not.
    stem_counts: dict[tuple[str, str], int] = {}
    for name in unique:
        labels = name.split(".")
        if len(labels) >= 2:
            key = (".".join(labels[1:]), stem_of(labels[0]))
            stem_counts[key] = stem_counts.get(key, 0) + 1

    sample = EstateSample(vendor_ref=vendor_ref, apex=apex, discovered=len(unique), cap=max(1, cap),
                          seed=f"sha256({vendor_ref} + name)")

    survivors: list[str] = []
    excluded: list[EstateHost] = []
    for name in unique:
        if is_tenant_namespace(name, apex, stem_counts, wildcard_seen=wildcard_seen,
                               sibling_threshold=sibling_threshold):
            sample.tenants_excluded += 1
            excluded.append(EstateHost(name=name, excluded_as="tenant"))
            continue
        # An unchecked name is not a dead name. Only an explicit negative excludes.
        if is_live is not None and name != apex and not is_live(name):
            sample.not_live_excluded += 1
            excluded.append(EstateHost(name=name, excluded_as="not_live"))
            continue
        survivors.append(name)

    # The apex is always probed and always first: the critical ceiling arms on it specifically, and
    # a sample that could omit it would make the knockout depend on the dice.
    rest = sorted((n for n in survivors if n != apex), key=lambda n: _rank(vendor_ref, n))
    chosen = [apex] + rest[: max(0, sample.cap - 1)]
    not_sampled = rest[max(0, sample.cap - 1):]

    sample.hosts = (
        [EstateHost(name=apex, is_apex=True)]
        + [EstateHost(name=n) for n in chosen[1:]]
        + [EstateHost(name=n, excluded_as="not_sampled") for n in not_sampled]
        + excluded
    )
    return sample
