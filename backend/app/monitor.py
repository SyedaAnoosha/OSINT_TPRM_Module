"""Continuous monitoring — re-score stale vendors and report drift.

WHAT THIS IS. TPRM is not a point-in-time exam; a vendor that scored A last quarter can lose a
certificate, get breached, or drop a DMARC record tomorrow. This module re-runs the ordinary
scoring pipeline over vendors whose latest score has gone stale, writes a NEW immutable score row
(the old one stays readable), and prints the posture drift so a change is visible, not silent.

WHAT THIS IS NOT. It is not a daemon. A long-lived scheduler is a deployment concern (systemd
timer, cron, a container's entrypoint, a cloud scheduler) — encoding one in the app would bury an
operational decision in code. This is the *unit of work* such a scheduler runs:

    # once a day, re-score anything not scored in the last 7 days
    python -m app.monitor --stale-days 7

    # see what WOULD re-score, change nothing
    python -m app.monitor --stale-days 7 --dry-run

    # force one vendor now
    python -m app.monitor --ref atlassian

Every re-score goes through `run_pipeline`, so a scheduled recheck is byte-for-byte the same path
as an on-demand score — there is no second, weaker scoring route that could drift from the first.

P5 — `--by-tier` REPLACES ONE CLOCK FOR THE WHOLE BOOK WITH THE RELATIONSHIP'S OWN. A single
`--stale-days` re-scores the stationery supplier as often as the vendor holding production data,
which is where the free-API budget goes and why the critical vendors get no more attention than the
trivial ones. Under `--by-tier` each vendor's interval and collection depth come from its declared
inherent tier (`app/assessment_depth.py`), and the soonest OUTSTANDING FINDING re-check can pull a
vendor forward — a passive relationship with an expired certificate is still chased inside a week.

    python -m app.monitor --by-tier --dry-run    # what the tiers say, before spending anything

This is the join P5 needs to be real. A depth-and-cadence table nothing schedules against is a
table, and the budget saving it claims never arrives.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from typing import Literal

from .assessment_depth import AssessmentPlan, Depth, is_due, plan_for
from .assessment_depth import as_dict as plan_as_dict
from .benchmarking.service import firmographics_of
from .logging_config import get_logger
from .longevity import age_band_from_years
from .models import Vendor, utcnow
from .pipeline import run_pipeline
from .profile import operating_years as profile_operating_years
from .residual_risk import inherent_tier
from .scoring.recommend import soonest_recheck
from .scoring_config import get_scoring_config
from .storage import get_store

log = get_logger("monitor")


#: What actually happened to this vendor on this sweep. Stated rather than inferred, because it
#: cannot be recovered from the postures: a SKIPPED vendor carries its previous posture in both
#: slots and is indistinguishable from one that was re-scored to an identical number. The run ledger
#: counted 126 "re-scored" on its first sweep for exactly that reason, when the true figure was 20.
Action = Literal["rescored", "skipped", "would_rescore", "error"]


@dataclass
class Drift:
    ref: str
    old_posture: int | None
    new_posture: int | None
    old_grade: str | None
    new_grade: str | None
    note: str = ""
    #: P5 — set only under `--by-tier`, so the ordinary sweep's output is unchanged.
    tier: str | None = None
    depth: Depth | None = None
    action: Action = "rescored"

    @property
    def delta(self) -> int | None:
        if self.old_posture is None or self.new_posture is None:
            return None
        return self.new_posture - self.old_posture


def _vendor_from_evidence(store, ref: str) -> Vendor | None:
    """Reconstruct a Vendor (ref + domain) from stored evidence, for a re-score.

    The domain is not persisted on its own, but every domain-scoped collector records it in `raw`.
    Reading it back lets a scheduled recheck re-score without a caller re-supplying what the system
    already knows. Mirrors the same helper the dispute re-score path uses in the API.
    """
    # `VendorProfile` HAS NO `operating_years` FIELD — it carries `inception` and
    # `domain_age_days`, and `profile.operating_years(...)` is the helper that derives years from
    # them (entity inception preferred over domain age; see its docstring for why that ordering is
    # the point rather than a tie-break). Reading the attribute directly raised AttributeError on
    # every sweep that found a stored profile, which is to say on every real sweep.
    vendor_years = profile_operating_years(store.latest_profile(ref))

    for e in store.for_vendor(ref):
        if e.raw and isinstance(e.raw.get("domain"), str):
            return Vendor(ref=ref, domain=e.raw["domain"], resolved=True, resolution_confidence=1.0,
                          operating_years=vendor_years)
    return None


def _stale_refs(store, stale_days: int) -> list[str]:
    """Vendor refs whose most recent score is older than `stale_days` (all of them if 0)."""
    cutoff_secs = stale_days * 86400
    now = utcnow()
    refs: list[str] = []
    for s in store.latest_scores_all():
        age = (now - s.computed_at).total_seconds()
        if stale_days <= 0 or age >= cutoff_secs:
            refs.append(s.vendor_ref)
    return refs


def plan_of(store, ref: str) -> AssessmentPlan:
    """This vendor's P5 plan, from the two client-declared inputs E10b already takes.

    Neither is inferred and neither is invented here: `criticality` rides on the profile,
    `data_access_scope` on the benchmarking attribute row, and an absent one leaves the tier
    undeclared — which routes to FULL depth, not to screening.
    
    AGE-BASED ADJUSTMENT. Vendor age is extracted from stored financial profile to apply
    age-adjusted monitoring cadence when using --by-tier scheduling.
    """
    profile = store.latest_profile(ref)
    firmographics = firmographics_of(store, ref)
    
    # Extract age band for age-based monitoring cadence adjustment
    age_band = None
    if profile and hasattr(profile, 'operating_years') and profile.operating_years is not None:
        age_band = age_band_from_years(profile.operating_years)
    
    return plan_for(inherent_tier(
        profile.criticality if profile else None,
        firmographics.data_access_scope if firmographics else None,
        # A PROVISIONAL DECLARATION STILL ROUTES. Refusing to schedule against an unconfirmed tier
        # would put every relationship back on FULL/semi-annual — the undeclared default — and the
        # whole budget saving `--by-tier` exists for would never arrive. The register's own rule:
        # a provisional answer routes better than no answer, and it is labelled everywhere it is read.
        provisional=profile.inherent_provisional if profile else False,
    ).tier, age_band=age_band)


def _soonest_finding_recheck(store, ref: str) -> str | None:
    """The shortest re-check any CHARGED finding on this vendor asks for.

    This is the second clock, and it is what stops `--by-tier` from parking a real problem. A
    passive T4 relationship serving an expired certificate has a 7-day date on that finding, and
    the finding's clock wins over the relationship's.
    """
    cfg = get_scoring_config()
    soonest = None
    for row in store.findings_for_vendor(ref):
        if row.effective_penalty > 0:
            soonest = soonest_recheck(
                soonest, (cfg.action_for(row.signal, row.band_key) or {}).get("recheck_after"))
    return soonest


async def monitor(stale_days: int, only_ref: str | None, dry_run: bool,
                  by_tier: bool = False) -> list[Drift]:
    store = get_store()
    # UNDER `--by-tier` THE STALENESS FILTER IS NOT APPLIED HERE. Every vendor is considered and
    # `is_due` decides per relationship, because a single cutoff is exactly the thing being
    # replaced — pre-filtering on it would make the tier intervals unreachable above the cutoff and
    # decorative below it.
    if only_ref:
        refs = [only_ref]
    elif by_tier:
        refs = [s.vendor_ref for s in store.latest_scores_all()]
    else:
        refs = _stale_refs(store, stale_days)
    drifts: list[Drift] = []
    now = utcnow()

    for ref in refs:
        prev = store.latest_score(ref)
        plan: AssessmentPlan | None = None
        depth: Depth | None = None
        if by_tier:
            plan = plan_of(store, ref)
            depth = plan.depth
            age_days = ((now - prev.computed_at).total_seconds() / 86400.0) if prev else None
            due, why = is_due(plan, age_days, _soonest_finding_recheck(store, ref))
            if not due:
                drifts.append(Drift(ref, prev.posture if prev else None,
                                    prev.posture if prev else None,
                                    prev.grade if prev else None, prev.grade if prev else None,
                                    note=f"skipped — {why}", tier=plan.tier_label, depth=depth,
                                    action="skipped"))
                continue
        vendor = _vendor_from_evidence(store, ref)
        if vendor is None:
            drifts.append(Drift(ref, prev.posture if prev else None, None, None, None,
                                note="skipped — no stored domain to reconstruct the vendor",
                                tier=plan.tier_label if plan else None, depth=depth,
                                action="skipped"))
            continue
        if dry_run:
            note = "would re-score"
            if plan is not None:
                note += f" at {plan.depth} depth ({plan.source_count})"
                if not plan.publishes_posture:
                    note += " — screening only, publishes no posture"
            drifts.append(Drift(ref, prev.posture if prev else None, prev.posture if prev else None,
                                prev.grade if prev else None, prev.grade if prev else None,
                                note=note, tier=plan.tier_label if plan else None, depth=depth,
                                action="would_rescore"))
            continue
        try:
            outcome = await run_pipeline(vendor, store=store, depth=depth)
            new = outcome.score
            note = "blocked" if new.blocked else "refused (Ghost)" if new.refused else ""
            if new.refused and plan is not None and not plan.publishes_posture:
                # EXPECTED, NOT A FINDING. A screening run reaches a fifth of the model and refuses
                # by design; printing it beside a genuine coverage failure would teach a reader to
                # ignore both.
                note = "screening depth — no posture published, as planned"
            drifts.append(Drift(
                ref, prev.posture if prev else None, new.posture,
                prev.grade if prev else None, new.grade, note=note,
                tier=plan.tier_label if plan else None, depth=depth,
            ))
        except Exception as exc:  # noqa: BLE001 — one bad vendor must not end the sweep
            drifts.append(Drift(ref, prev.posture if prev else None, None,
                                prev.grade if prev else None, None,
                                note=f"ERROR — {type(exc).__name__}: {exc}",
                                tier=plan.tier_label if plan else None, depth=depth,
                                action="error"))
    return drifts


def _print(drifts: list[Drift], dry_run: bool) -> None:
    verb = "would re-score" if dry_run else "re-scored"
    print(f"\n{verb} {len(drifts)} vendor(s)\n" + "-" * 60)
    # Biggest deteriorations first — a drop is the whole reason to monitor.
    drifts.sort(key=lambda d: (d.delta if d.delta is not None else 0))
    for d in drifts:
        if d.delta is None:
            arrow = "  ·  "
        elif d.delta < 0:
            arrow = f" ▼{abs(d.delta)} "
        elif d.delta > 0:
            arrow = f" ▲{d.delta} "
        else:
            arrow = "  =  "
        old = d.old_posture if d.old_posture is not None else "—"
        new = d.new_posture if d.new_posture is not None else "—"
        tier = f" [{d.tier}·{d.depth}]" if d.tier else ""
        tail = f"   {d.note}" if d.note else ""
        print(f"  {d.ref:<28} {old!s:>3} →{arrow}→ {new!s:<3} "
              f"{d.old_grade or '—'}→{d.new_grade or '—'}{tier}{tail}")

    dropped = [d for d in drifts if (d.delta or 0) < 0]
    if dropped and not dry_run:
        print(f"\n{len(dropped)} vendor(s) DETERIORATED since last score — review the drops above.")

    # THE BUDGET LINE, and the reason `--by-tier` exists. A sweep that says only what it did hides
    # the saving it made, and a saving nobody can see is one nobody will defend when a reviewer asks
    # why the stationery supplier has not been re-scored since March.
    skipped = [d for d in drifts if d.note.startswith("skipped —")]
    if any(d.tier for d in drifts):
        by_tier: dict[str, int] = {}
        for d in drifts:
            if d.tier:
                by_tier[d.tier] = by_tier.get(d.tier, 0) + 1
        print(f"\nBy tier: " + " · ".join(f"{t} ×{n}" for t, n in sorted(by_tier.items())))
        print(f"{len(skipped)} of {len(drifts)} vendor(s) not due — that is the collection budget "
              f"P5 saves, and every one of them names the interval it is inside.")
        undeclared = sum(1 for d in drifts if d.tier == "Unclassified")
        if undeclared:
            print(f"{undeclared} vendor(s) have NO DECLARED INHERENT TIER and are running at FULL "
                  f"depth as a result. Undeclared is not low — declare criticality and data access "
                  f"scope to stop paying for the unknown.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-score stale vendors and report drift.")
    ap.add_argument("--stale-days", type=int, default=7,
                    help="re-score vendors not scored in this many days (0 = all). Default 7.")
    ap.add_argument("--ref", default=None, help="re-score exactly this vendor ref, now")
    ap.add_argument("--dry-run", action="store_true", help="list what would re-score; change nothing")
    ap.add_argument("--by-tier", action="store_true",
                    help="P5: use each vendor's inherent-tier interval and collection depth instead "
                         "of one --stale-days clock for the whole book. An outstanding finding's "
                         "re-check date can still pull a vendor forward.")
    ap.add_argument("--plan", action="store_true",
                    help="Print the published tier -> depth + cadence table and exit.")
    args = ap.parse_args()

    if args.plan:
        _print_plan()
        return

    drifts = asyncio.run(monitor(args.stale_days, args.ref, args.dry_run, by_tier=args.by_tier))
    _print(drifts, args.dry_run)


def _print_plan() -> None:
    from .assessment_depth import table

    print("\nP5 — assessment depth and cadence by inherent tier\n" + "-" * 78)
    for row in table():
        art = (" + " + ", ".join(row["artefacts"])) if row["artefacts"] else ""
        print(f"  {row['tier_label']:<14} {row['depth']:<10} "
              f"sources={row['sources']!s:<4} {row['cadence']:<28} "
              f"{'posture' if row['publishes_posture'] else 'NO POSTURE'}{art}")
    print("\n  Undeclared tier -> FULL depth, semi-annual. Not T4: the relationships nobody has\n"
          "  classified are the ones nobody has looked at, so they get the fuller treatment.")
    print(dict(plan_as_dict(plan_for(None)))["caveats"][-1])


if __name__ == "__main__":
    main()
