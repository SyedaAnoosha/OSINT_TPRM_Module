"""Target maturity — measuring a vendor against a PUBLISHED baseline, not against its peers.

THE PROBLEM THIS SOLVES, WHICH BENCHMARKING CANNOT. `benchmark.py` compares a vendor against
vendors this deployment happened to score. That is a convenience sample, and `benchmarks.yaml`
says so in the caveat it forces onto every card. Two consequences follow, and neither is fixable
from inside the cohort: a portfolio skewed toward weak vendors produces a flattering median, so
"above average" can mean "above a bad average"; and a cohort below `min_cohort_n` publishes
nothing at all, which is precisely the situation a new deployment or a niche sector lives in.

A target model has neither failure. It is fixed, external and dated, so it cannot drift with the
portfolio, and it needs zero peers — the reading is identical on day one and on day one thousand.
The two are complements, not substitutes: the percentile answers *"am I typical?"*, this answers
*"am I adequate?"*, and the interesting vendors are the ones where those disagree.

WHAT KEEPS THIS FROM BECOMING A LIST OF OPINIONS. Every control carries a `basis` naming a real,
dated instrument, and `TargetConfig.validate` rejects the file at load if one does not — the same
guard `expected_posture` has always had. This matters more here than it looks: a plausible-sounding
baseline assembled from professional intuition, with an official-looking citation attached, would
pass any check that only tests for a non-empty string, and would put numbers in front of a client
that nobody ever published. Where an instrument could not be found, the control is ABSENT from
benchmarks.yaml rather than asserted with a vague source.

THREE DISCIPLINES CARRIED OVER FROM THE SCORING ENGINE:
  * a signal never CHECKED is not a signal FAILED — it leaves the denominator rather than counting
    against the vendor, exactly as missing evidence lowers confidence and never posture;
  * a control that could not yet EXIST at this vendor's age (an audit observation window) also
    leaves the denominator, and is disclosed by name rather than dropped silently;
  * below `min_controls` observed we publish nothing, because "2 of 3" assembled from whichever
    signals happened to return is the same false precision as a median over three vendors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import MaturityGap, TargetControl


class TargetConfigError(ValueError):
    """Raised at load time. Fail loudly at startup, never quietly at serve time."""


@dataclass
class TargetControlSpec:
    """One control as CONFIGURED — the spec, before any vendor is measured against it."""

    signal: str
    meets: tuple[str, ...]
    partial: tuple[str, ...]
    basis: str
    attainable_after_years: float = 0.0

    def status_for(self, observed: str | None, age_years: float | None) -> str:
        """Classify one observation. Order matters: attainability is decided BEFORE the observation
        is read, so a control the vendor could not yet hold never reads as a gap."""
        if not self._attainable(age_years):
            return "not_yet_attainable"
        if observed is None:
            return "unchecked"
        if observed in self.meets:
            return "meets"
        if observed in self.partial:
            return "partial"
        return "gap"

    def _attainable(self, age_years: float | None) -> bool:
        if self.attainable_after_years <= 0:
            return True
        if age_years is None:
            # Unknown age: assume attainable, so an unmeasured vendor is held to the FULL baseline
            # rather than quietly excused from it. Erring the other way would make "we could not
            # determine your founding date" a way to shed controls.
            return True
        return age_years >= self.attainable_after_years


@dataclass
class TargetProfile:
    id: str
    description: str
    applies_to: dict[str, str] = field(default_factory=dict)
    controls: list[TargetControlSpec] = field(default_factory=list)

    def matches(self, sector: str | None) -> bool:
        """An empty `applies_to` matches every vendor. Profiles ADD controls; a sector-specific
        profile never replaces the baseline, because 'this sector is special' is a reason to expect
        MORE, never a reason to stop expecting the basics."""
        want = self.applies_to.get("sector")
        return want is None or (sector is not None and want == sector)


class TargetConfig:
    """The `target_maturity` block of benchmarks.yaml, validated."""

    def __init__(self, data: dict[str, Any]) -> None:
        block = (data or {}).get("target_maturity") or {}
        self.min_controls = int(block.get("min_controls", 3))
        self.profiles = [self._profile(p) for p in (block.get("profiles") or [])]

    @staticmethod
    def _profile(raw: dict[str, Any]) -> TargetProfile:
        pid = str(raw.get("id") or "").strip()
        if not pid:
            raise TargetConfigError("a target_maturity profile needs an `id`")
        controls = []
        for c in raw.get("controls") or []:
            signal = str(c.get("signal") or "").strip()
            if not signal:
                raise TargetConfigError(f"target profile {pid!r} has a control with no `signal`")
            basis = str(c.get("basis") or "").strip()
            if not basis:
                # The same rule expected_posture obeys. A required control whose source a client
                # cannot check is an assertion, and this file does not ship assertions.
                raise TargetConfigError(
                    f"target profile {pid!r} control {signal!r} has no `basis` — a control "
                    f"without a named instrument is an opinion with a checkbox next to it"
                )
            meets = tuple(str(b) for b in (c.get("meets") or []))
            if not meets:
                raise TargetConfigError(
                    f"target profile {pid!r} control {signal!r} lists no `meets` bands, so nothing "
                    f"could ever satisfy it"
                )
            overlap = set(meets) & {str(b) for b in (c.get("partial") or [])}
            if overlap:
                raise TargetConfigError(
                    f"target profile {pid!r} control {signal!r} lists {sorted(overlap)} as both "
                    f"`meets` and `partial`"
                )
            controls.append(TargetControlSpec(
                signal=signal, meets=meets,
                partial=tuple(str(b) for b in (c.get("partial") or [])),
                basis=basis,
                attainable_after_years=float(c.get("attainable_after_years", 0) or 0),
            ))
        if not controls:
            raise TargetConfigError(f"target profile {pid!r} defines no controls")
        return TargetProfile(
            id=pid, description=str(raw.get("description") or ""),
            applies_to=dict(raw.get("applies_to") or {}), controls=controls,
        )

    def for_sector(self, sector: str | None) -> list[TargetProfile]:
        return [p for p in self.profiles if p.matches(sector)]


def build_maturity_gap(
    signals: dict[str, str],
    sector: str | None,
    cfg: TargetConfig,
    vendor_age_years: float | None = None,
) -> MaturityGap:
    """Measure this vendor's observed bands against every applicable target profile.

    `signals` is the same subject-signal map the prevalence comparison already receives — signal ->
    observed band. A signal absent from it was not observed this run.
    """
    profiles = cfg.for_sector(sector)
    if not profiles:
        return MaturityGap(available=False, reason="no target maturity profile for this sector",
                           vendor_age_years=vendor_age_years)

    results: list[TargetControl] = []
    seen: set[str] = set()
    for profile in profiles:
        for spec in profile.controls:
            # A signal appearing in two profiles is evaluated ONCE. Counting it twice would let the
            # shape of the config file change a vendor's attainment without any observation changing.
            if spec.signal in seen:
                continue
            seen.add(spec.signal)
            observed = signals.get(spec.signal)
            results.append(TargetControl(
                signal=spec.signal, observed=observed,
                status=spec.status_for(observed, vendor_age_years),
                basis=spec.basis, attainable_after_years=spec.attainable_after_years,
            ))

    counts = {k: sum(1 for r in results if r.status == k)
              for k in ("meets", "partial", "gap", "not_yet_attainable", "unchecked")}
    applicable = counts["meets"] + counts["partial"] + counts["gap"]

    # Worst first: what a reader needs is the controls they observably fail, then the ones that are
    # half-done, then the rest. `unchecked` and `not_yet_attainable` sort last — they are context,
    # not to-do items.
    order = {"gap": 0, "partial": 1, "meets": 2, "not_yet_attainable": 3, "unchecked": 4}
    results.sort(key=lambda r: (order[r.status], r.signal))

    gap = MaturityGap(
        available=applicable >= cfg.min_controls,
        profile_ids=[p.id for p in profiles], controls=results,
        met=counts["meets"], partial=counts["partial"], gaps=counts["gap"],
        applicable=applicable, not_yet_attainable=counts["not_yet_attainable"],
        unchecked=counts["unchecked"], vendor_age_years=vendor_age_years,
    )
    if not gap.available:
        gap.reason = (
            f"only {applicable} baseline control(s) could be observed, below the minimum of "
            f"{cfg.min_controls} — too little to state a maturity position"
        )
        return gap

    # A partial counts half. It is a real difference: p=quarantine is not p=reject, and it is also
    # not the same as publishing no DMARC record at all, so collapsing it to either end would
    # misreport one of the two vendors it describes.
    gap.attainment = round((counts["meets"] + 0.5 * counts["partial"]) / applicable, 3)
    gap.summary = _summary(gap)
    return gap


def _summary(gap: MaturityGap) -> str:
    """The plain sentence, assembled so every excluded control is accounted for in words. A reader
    who is told '4 of 6' must be able to see where the other controls went."""
    parts = [f"{gap.met} of {gap.applicable} baseline controls met"]
    if gap.partial:
        parts.append(f"{gap.partial} partially met")
    if gap.gaps:
        parts.append(f"{gap.gaps} not met")
    if gap.not_yet_attainable:
        years = f"{gap.vendor_age_years:.0f}" if gap.vendor_age_years is not None else "this"
        parts.append(
            f"{gap.not_yet_attainable} excluded as not yet attainable at {years} year(s) of "
            f"operating history"
        )
    if gap.unchecked:
        parts.append(f"{gap.unchecked} not observed this run")
    return "; ".join(parts) + "."
