"""Cohort seeder — score a list of real vendors so benchmarking has a population to work with.

WHY THIS EXISTS. The benchmark refuses to publish a percentile below `min_cohort_n` peers, which
is correct and means the feature shows nothing at all until enough vendors in one cohort have been
scored. Seeding is how you get from "insufficient peers (0 of 8)" to a working comparison. There is
no shortcut: the median has to come from vendors we actually assessed, because the alternative is
typing a number in, and a sector target nobody published is exactly what `benchmarks.yaml` refuses
to carry.

WHAT IT IS NOT. Not a data-collection exercise for its own sake, and not a way to manufacture a
distribution. Every vendor named here is scored by the same pipeline as any other, writes the same
hash-stamped evidence, and can be inspected on the scorecard afterwards. If a seeded score looks
wrong, it is wrong in the ordinary way and should be investigated, not excluded for being
inconvenient.

USAGE
    python -m app.seed_cohorts --list                     # what would be scored, by sector
    python -m app.seed_cohorts --sector technology        # one sector
    python -m app.seed_cohorts --all --concurrency 2      # everything, politely
    python -m app.seed_cohorts --domains a.com b.com      # an ad-hoc set

POLITENESS IS NOT OPTIONAL. Vendors are scored sequentially by default. Every collector in this
system queries someone else's free service, and a seeding run multiplies that by the number of
vendors — the fastest way to lose access to a free source is to hammer it. `--concurrency` exists
for impatience; the default of 1 is the right setting.

THE SECTOR IS DECLARED, NOT LEFT TO INFERENCE — and this is the difference between a seeding run
that fills cohorts and one that only spends the politeness budget. A cohort is `sector × size ×
region`; a vendor with no sector gets no cohort and contributes to no peer group at all. Sector is
inferred from GLEIF/Wikidata/PDL industry labels and that inference simply fails for a meaningful
share of real companies. Every vendor below already sits under a sector heading — the key of the
dict it is in — and until this was wired that knowledge was thrown away at the call site: a live
scan against someone else's free service, spent, and no cohort depth to show for it.

It is passed as a CLIENT-STATED sector, recorded with `source="client"` exactly like a buyer's own
declaration, because that is what it is: our editorial judgement about which peer group a company
belongs in, not something we observed. `--infer-sector` opts out and reproduces the old behaviour
for anyone who would rather measure the inference than override it.

THE KEYS ARE THE CONTROLLED VOCABULARY, and `_validate_seed_sectors` refuses at import if one is
not. Three of them were not: `food_agriculture`, `transport_logistics` and `energy_utilities` are
not sectors this system knows (`agriculture`, `logistics`, `utilities` are), so `--sector` offered
an operator three headings that could never match a cohort key even once the sector was passed.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from typing import Any

from .benchmark import get_benchmark_config
from .logging_config import get_logger, setup_logging
from .pipeline import resolve_vendor, run_pipeline
from .scoring.log_odds import preconditions
from .sectors import known_sectors
from .storage import get_store

log = get_logger("seed")

#: E13's floor, restated here only so `--status` can report against it. The authority is
#: `log_odds.preconditions`, which is asserted below rather than duplicated.
_E13_MIN_PEERS = 8


@dataclass(frozen=True)
class SeedVendor:
    name: str
    domain: str


# Real, named companies — the brief's own rule ("don't shortcut with 'test test' or 'Acme Corp'")
# applies here as much as to the assessment set.
#
# DELIBERATELY GLOBAL, AND THAT IS A STRUCTURAL REQUIREMENT RATHER THAN AMBITION. The cohort key
# is sector × size × region, so a seed list drawn from one region fills exactly one region's
# cohorts and every vendor outside it still reads "insufficient peers". Each sector below is
# therefore spread across ANZ, North America, UK/EU and APAC — a US SaaS vendor is benchmarked
# against US SaaS vendors, an Australian one against Australian ones, because the regulatory
# regime a company answers to changes what its posture means.
#
# Size is spread on purpose too. A list of twelve mega-caps produces a cohort that no ordinary
# supplier belongs to, and `mega` vendors are exactly the ones a buyer least needs help judging.
#
# The five reference vendors (Atlassian, Snowflake, Slack, MYOB, OneTrust) are NOT here: they are
# the frozen regression corpus, and a benchmark population built from the same vendors the model
# is tuned against would be measuring itself.
#
# STARTING POINTS, NOT A CANONICAL UNIVERSE. Add the vendors your own portfolio contains — a
# cohort built from your actual suppliers is worth more than one built from ours.
SEED_SETS: dict[str, list[SeedVendor]] = {
    "technology": [
        # North America
        SeedVendor("HubSpot", "hubspot.com"),
        SeedVendor("Zendesk", "zendesk.com"),
        SeedVendor("Datadog", "datadoghq.com"),
        SeedVendor("Twilio", "twilio.com"),
        SeedVendor("Okta", "okta.com"),
        SeedVendor("DocuSign", "docusign.com"),
        SeedVendor("Asana", "asana.com"),
        SeedVendor("Box", "box.com"),
        SeedVendor("PagerDuty", "pagerduty.com"),
        # UK / EU
        SeedVendor("Sage Group", "sage.com"),
        SeedVendor("SAP", "sap.com"),
        SeedVendor("Dassault Systemes", "3ds.com"),
        SeedVendor("Personio", "personio.com"),
        SeedVendor("Contentful", "contentful.com"),
        SeedVendor("Darktrace", "darktrace.com"),
        # ANZ
        SeedVendor("Canva", "canva.com"),
        SeedVendor("WiseTech Global", "wisetechglobal.com"),
        SeedVendor("Nearmap", "nearmap.com"),
        SeedVendor("Xero", "xero.com"),
        # APAC
        SeedVendor("Freshworks", "freshworks.com"),
        SeedVendor("Zoho", "zoho.com"),
        SeedVendor("Grab", "grab.com"),
        SeedVendor("Line", "line.me"),
    ],
    "financial_services": [
        # North America
        SeedVendor("Stripe", "stripe.com"),
        SeedVendor("Block", "block.xyz"),
        SeedVendor("Plaid", "plaid.com"),
        SeedVendor("Marqeta", "marqeta.com"),
        SeedVendor("Brex", "brex.com"),
        # UK / EU
        SeedVendor("Adyen", "adyen.com"),
        SeedVendor("Wise", "wise.com"),
        SeedVendor("Revolut", "revolut.com"),
        SeedVendor("Klarna", "klarna.com"),
        SeedVendor("Monzo", "monzo.com"),
        SeedVendor("Checkout.com", "checkout.com"),
        # ANZ
        SeedVendor("Airwallex", "airwallex.com"),
        SeedVendor("Zip Co", "zip.co"),
        SeedVendor("Tyro Payments", "tyro.com"),
        SeedVendor("Judo Bank", "judo.bank"),
        # APAC
        SeedVendor("Nium", "nium.com"),
        SeedVendor("Razorpay", "razorpay.com"),
    ],
    "healthcare": [
        SeedVendor("ResMed", "resmed.com"),
        SeedVendor("Cochlear", "cochlear.com"),
        SeedVendor("CSL", "csl.com"),
        SeedVendor("Sonic Healthcare", "sonichealthcare.com"),
        SeedVendor("Ramsay Health Care", "ramsayhealth.com"),
        SeedVendor("Veeva Systems", "veeva.com"),
        SeedVendor("Doctolib", "doctolib.fr"),
        SeedVendor("Babylon Health", "babylonhealth.com"),
        SeedVendor("Siemens Healthineers", "siemens-healthineers.com"),
        SeedVendor("Philips", "philips.com"),
    ],
    "retail": [
        SeedVendor("Woolworths Group", "woolworthsgroup.com.au"),
        SeedVendor("Coles Group", "colesgroup.com.au"),
        SeedVendor("Wesfarmers", "wesfarmers.com.au"),
        SeedVendor("Kogan", "kogan.com"),
        SeedVendor("Shopify", "shopify.com"),
        SeedVendor("Etsy", "etsy.com"),
        SeedVendor("Zalando", "zalando.com"),
        SeedVendor("ASOS", "asos.com"),
        SeedVendor("Ocado Group", "ocadogroup.com"),
        SeedVendor("Marks and Spencer", "marksandspencer.com"),
    ],
    "agriculture": [
        SeedVendor("Bega Group", "begagroup.com.au"),
        SeedVendor("Treasury Wine Estates", "tweglobal.com"),
        SeedVendor("Elders", "elders.com.au"),
        SeedVendor("Inghams Group", "inghams.com.au"),
        SeedVendor("Fonterra", "fonterra.com"),
        SeedVendor("Danone", "danone.com"),
        SeedVendor("Nestle", "nestle.com"),
        SeedVendor("Tate & Lyle", "tateandlyle.com"),
        SeedVendor("Cargill", "cargill.com"),
        SeedVendor("Bunge", "bunge.com"),
    ],
    "telecommunications": [
        SeedVendor("Telstra", "telstra.com.au"),
        SeedVendor("TPG Telecom", "tpgtelecom.com.au"),
        SeedVendor("Aussie Broadband", "aussiebroadband.com.au"),
        SeedVendor("Spark New Zealand", "sparknz.co.nz"),
        SeedVendor("BT Group", "bt.com"),
        SeedVendor("Vodafone Group", "vodafone.com"),
        SeedVendor("Deutsche Telekom", "telekom.com"),
        SeedVendor("Orange", "orange.com"),
        SeedVendor("Singtel", "singtel.com"),
        SeedVendor("Lumen Technologies", "lumen.com"),
    ],
    "professional_services": [
        SeedVendor("Computershare", "computershare.com"),
        SeedVendor("SEEK", "seek.com.au"),
        SeedVendor("REA Group", "rea-group.com"),
        SeedVendor("IRESS", "iress.com"),
        SeedVendor("Experian", "experian.com"),
        SeedVendor("RELX", "relx.com"),
        SeedVendor("Wolters Kluwer", "wolterskluwer.com"),
        SeedVendor("Thomson Reuters", "thomsonreuters.com"),
        SeedVendor("Robert Half", "roberthalf.com"),
        SeedVendor("Randstad", "randstad.com"),
    ],
    "logistics": [
        SeedVendor("DHL Group", "dhl.com"),
        SeedVendor("Maersk", "maersk.com"),
        SeedVendor("DSV", "dsv.com"),
        SeedVendor("Toll Group", "tollgroup.com"),
        SeedVendor("Qube Holdings", "qube.com.au"),
        SeedVendor("FedEx", "fedex.com"),
        SeedVendor("Kuehne+Nagel", "kuehne-nagel.com"),
        SeedVendor("Singapore Airlines", "singaporeair.com"),
    ],
    "utilities": [
        SeedVendor("Origin Energy", "originenergy.com.au"),
        SeedVendor("AGL Energy", "agl.com.au"),
        SeedVendor("Iberdrola", "iberdrola.com"),
        SeedVendor("Orsted", "orsted.com"),
        SeedVendor("National Grid", "nationalgrid.com"),
        SeedVendor("Enel", "enel.com"),
        SeedVendor("NextEra Energy", "nexteraenergy.com"),
        SeedVendor("SSE", "sse.com"),
    ],
    "manufacturing": [
        SeedVendor("Siemens", "siemens.com"),
        SeedVendor("ABB", "abb.com"),
        SeedVendor("Schneider Electric", "se.com"),
        SeedVendor("Bosch", "bosch.com"),
        SeedVendor("Amcor", "amcor.com"),
        SeedVendor("Brambles", "brambles.com"),
        SeedVendor("Honeywell", "honeywell.com"),
        SeedVendor("Rockwell Automation", "rockwellautomation.com"),
    ],
}


class SeedVocabularyError(ValueError):
    """Raised at import when a seed-set heading is not a sector the system can form a cohort on."""


def _validate_seed_sectors() -> None:
    """Every heading in `SEED_SETS` must be a canonical sector. Enforced at import, not at run.

    A wrong heading fails SILENTLY AND IN THE EXPENSIVE DIRECTION: the run completes, every vendor
    scores, the politeness budget is spent in full, and the cohort those vendors were supposed to
    fill has zero members because no cohort key ever carried that word. The operator's only signal
    is `--status` continuing to say "insufficient", which reads as *not enough vendors yet* rather
    than *these vendors went somewhere else*.
    """
    unknown = sorted(set(SEED_SETS) - known_sectors())
    if unknown:
        raise SeedVocabularyError(
            f"seed-set headings that are not sectors: {unknown}. A heading is passed to the "
            f"pipeline as the vendor's sector and has to match the controlled vocabulary in "
            f"sectors.py, or the run fills no cohort. Known: {sorted(known_sectors())}"
        )


_validate_seed_sectors()


def sector_of(vendor: SeedVendor) -> str | None:
    """The heading `vendor` is filed under — the sector we will declare for it."""
    for sector, members in SEED_SETS.items():
        if vendor in members:
            return sector
    return None


async def seed(vendors: list[SeedVendor], concurrency: int = 1,
               *, declare_sector: bool = True) -> dict[str, str]:
    """Score each vendor through the ordinary pipeline. Returns `{domain: outcome}`.

    One vendor failing must never stop the run — a seeding pass over 40 vendors will hit a dead
    DNS record or a rate limit somewhere, and losing the other 39 to it would be absurd. Failures
    are recorded and reported at the end.

    `declare_sector` passes the seed-set heading through as a client-stated sector. On by default,
    because the alternative is spending a live scan on a vendor who then lands in no cohort — see
    the module docstring. `--infer-sector` turns it off.
    """
    results: dict[str, str] = {}
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(sv: SeedVendor) -> None:
        async with semaphore:
            try:
                vendor = resolve_vendor(name=sv.name, domain=sv.domain)
                outcome = await run_pipeline(
                    vendor, sector=sector_of(sv) if declare_sector else None)
                score = outcome.score
                if score.blocked:
                    results[sv.domain] = f"BLOCKED — {score.blocked_reason}"
                elif score.refused:
                    results[sv.domain] = f"refused (Ghost, confidence {score.overall_confidence})"
                else:
                    results[sv.domain] = f"{score.posture} ({score.grade}), conf {score.overall_confidence}"
                log.info("%-32s %s", sv.domain, results[sv.domain])
            except Exception as exc:  # noqa: BLE001 — one bad vendor must not end the run
                results[sv.domain] = f"ERROR — {type(exc).__name__}: {exc}"
                log.warning("%-32s %s", sv.domain, results[sv.domain])

    await asyncio.gather(*(one(sv) for sv in vendors))
    return results


def _probe(n_peers: int):
    """A `ShrinkageInput` that exists only to ask `preconditions()` what it would say at this depth.

    Built with a real peer rate so the ONLY failure it can report is the population one — otherwise
    the status line would print "no cohort penalty rate available", which is a per-vendor fact and
    not the thing an operator is waiting on.
    """
    from .scoring.log_odds import ShrinkageInput

    return ShrinkageInput(penalty_fraction=0.2, confidence=0.8, peer_penalty_fraction=0.2,
                          n_peers=n_peers, peers_are_synthetic=False)


def cohort_depths() -> dict[str, int]:
    """`{cohort_key: member count}` over every cohort this deployment has actually written."""
    store = get_store()
    try:
        keys = {
            row["cohort_key"]
            for row in store._conn.execute(  # noqa: SLF001 — a CLI reporting on its own store
                "SELECT DISTINCT cohort_key FROM vendor_profiles WHERE cohort_key IS NOT NULL"
            )
        } if hasattr(store, "_conn") else set()
        return {key: len(store.cohort_members(key)) for key in sorted(keys)}
    finally:
        store.close()


def report_cohorts() -> None:
    """Every cohort's depth against the gates that actually gate — and whether E13 may switch on.

    IT USED TO REPORT AGAINST ONE NUMBER, AND THE WRONG ONE. `benchmark.min_cohort_n()` belongs to
    the DEPRECATED v1 path; EB replaced it with two thresholds (a quartile at 8, a percentile at 30)
    because a rank-of-n and a percentile are not the same claim and do not become available at the
    same population. An operator watching a single "publishes / insufficient" column could not tell
    which of the three things they were waiting for had arrived.

    AND IT ANSWERED THE WRONG QUESTION. E11's remaining work exists mainly to unblock E13, and
    nothing anywhere reported on that. `preconditions()` is called here rather than restated, so the
    readiness line cannot drift from the rule the transform actually enforces.
    """
    from .benchmarking.config import get_benchmarking_config

    depths = cohort_depths()
    if not depths:
        print("No cohorts yet — score some vendors first.")
        return

    v1 = get_benchmark_config().min_cohort_n()
    bcfg = get_benchmarking_config()
    quartile, percentile = bcfg.min_quartile_n(), bcfg.min_percentile_n()

    print(f"\nCohort depth — {len(depths)} cohort(s)\n"
          f"  v1 benchmark (deprecated) gate : {v1}\n"
          f"  EB quartile + rank-of-n        : {quartile}\n"
          f"  EB percentile                  : {percentile}\n"
          f"  E13 shrinkage floor            : {_E13_MIN_PEERS}\n" + "-" * 78)
    for key, n in depths.items():
        marks = "".join([
            "v" if n >= v1 else "-",
            "q" if n >= quartile else "-",
            "p" if n >= percentile else "-",
            "L" if n >= _E13_MIN_PEERS else "-",
        ])
        print(f"  {key:<52} n={n:<4} [{marks}]")

    ready = sorted(k for k, n in depths.items() if n >= _E13_MIN_PEERS)
    print(f"\nE13 — bounded log-odds: {len(ready)} of {len(depths)} cohort(s) can supply L_peer.")
    if ready:
        # The preview begins publishing for these vendors on their next score, with no code change
        # and no flag. That is what makes the switch-on data-driven rather than a promise.
        print("  L_peer available for: " + ", ".join(ready[:6])
              + (f" (+{len(ready) - 6} more)" if len(ready) > 6 else ""))
        print("  The SIDE-BY-SIDE preview publishes for these on their next score. Consuming it in "
              "the live posture is still a release decision, not a threshold.")
    else:
        deepest = max(depths.values())
        print(f"  Deepest cohort holds {deepest}. Every vendor will keep refusing with: "
              f"{preconditions(_probe(deepest))[-1]}")


def backfill_cohort_attributes(*, dry_run: bool = False) -> dict[str, int]:
    """Give already-scored vendors the v2 cohort row a score now writes for them.

    WHY A BACKFILL IS NEEDED AT ALL. `supplier_attributes` is the only table `bm_cohort_peers`
    reads, and until recently nothing in the scoring pipeline wrote it — the only writers were the
    v2 attributes route and the inherent register. So a vendor could be fully assessed, carry a
    sector resolved from Wikidata or GLEIF, and still be invisible to every peer group. The
    pipeline now records the row on each run, but that only helps vendors scored FROM NOW ON; a
    book of already-scored vendors would sit unbenchmarkable until each was re-scored, which means
    re-querying other people's free APIs to move data we already hold.

    IT DOES NOT RE-SCORE AND IT QUERIES NO SOURCE. Profile in, attribute row out.

    MERGE, NEVER OVERWRITE — the same rule `inherent_register.apply_entry` follows. A stored row
    may carry a client correction, an upheld cohort dispute, or a `data_access_scope` that no
    collector can observe, and this table is append-only: a fresh row written without them would
    make the newest row the one that lost them. Only fields the stored row LACKS are filled.
    """
    from .benchmarking.models import SupplierFirmographics
    from .benchmarking.service import firmographics_of, record_attributes

    def _v(field: Any) -> Any:
        return field.value if field is not None else None

    store = get_store()
    counts = {"profiles": 0, "written": 0, "unchanged": 0, "no_firmographics": 0}
    try:
        for ref, profile in sorted(store.latest_profiles_all().items()):
            counts["profiles"] += 1
            from_profile = {
                "sector": _v(profile.sector),
                "employees": _v(profile.employees),
                "revenue": _v(profile.revenue),
                "revenue_currency": _v(profile.revenue_currency),
            }
            if not any(v is not None for v in from_profile.values()):
                # Nothing observed. A row of all-None would add a supplier to the table that no
                # cohort can ever match, which is noise rather than a peer.
                counts["no_firmographics"] += 1
                continue

            stored = firmographics_of(store, ref)
            if stored is None:
                merged = SupplierFirmographics(supplier_ref=ref, **from_profile)
            else:
                filled = {k: v for k, v in from_profile.items()
                          if getattr(stored, k, None) is None and v is not None}
                if not filled:
                    counts["unchanged"] += 1
                    continue
                merged = stored.model_copy(update=filled)

            if not dry_run:
                record_attributes(store, merged, source="derived")
            counts["written"] += 1
            log.info("%s: cohort attributes %s (sector=%s employees=%s)",
                     ref, "would be written" if dry_run else "written",
                     merged.sector, merged.employees)
    finally:
        store.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed peer cohorts by scoring real vendors.")
    parser.add_argument("--sector", action="append", choices=sorted(SEED_SETS),
                        help="Seed one sector (repeatable).")
    parser.add_argument("--all", action="store_true", help="Seed every sector.")
    parser.add_argument("--domains", nargs="+", help="Ad-hoc domains to score.")
    parser.add_argument("--list", action="store_true", help="Show the seed sets and exit.")
    parser.add_argument("--status", action="store_true",
                        help="Report cohort depth against every gate, plus E13 readiness, and exit.")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Vendors in flight. Default 1 — these are other people's free APIs.")
    parser.add_argument("--infer-sector", action="store_true",
                        help="Do NOT declare the seed-set sector; leave it to public sources. "
                             "Measures the inference at the cost of cohorts it fails to fill.")
    parser.add_argument("--backfill-attributes", action="store_true",
                        help="Give already-scored vendors their v2 cohort row, from the profile "
                             "already stored. Queries no source and re-scores nothing.")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --backfill-attributes: report what would be written.")
    args = parser.parse_args()

    setup_logging()

    if args.backfill_attributes:
        counts = backfill_cohort_attributes(dry_run=args.dry_run)
        verb = "would be written" if args.dry_run else "written"
        print(f"\n{counts['profiles']} profiles examined")
        print(f"  {counts['written']:>4} cohort rows {verb}")
        print(f"  {counts['unchanged']:>4} already complete — nothing to add")
        print(f"  {counts['no_firmographics']:>4} skipped: nothing observed to put in a cohort")
        if not args.dry_run:
            report_cohorts()
        return

    if args.list:
        for sector, vendors in sorted(SEED_SETS.items()):
            print(f"\n{sector}  ({len(vendors)})")
            for v in vendors:
                print(f"  {v.name:<28} {v.domain}")
        total = sum(len(v) for v in SEED_SETS.values())
        print(f"\n{total} vendors across {len(SEED_SETS)} sectors. Each is scored with its heading "
              f"declared as a client-stated sector (--infer-sector to leave it to inference).")
        print(f"Gate: {get_benchmark_config().min_cohort_n()} peers per cohort before a "
              f"percentile is published — see --status for every gate.")
        return

    if args.status:
        report_cohorts()
        return

    vendors: list[SeedVendor] = []
    if args.all:
        vendors = [v for group in SEED_SETS.values() for v in group]
    elif args.sector:
        vendors = [v for s in args.sector for v in SEED_SETS[s]]
    elif args.domains:
        vendors = [SeedVendor(name=d.split(".")[0].title(), domain=d) for d in args.domains]
    else:
        parser.error("choose --all, --sector, --domains, --list or --status")

    # An ad-hoc `--domains` set has no heading, so `sector_of` returns None for each and the run
    # falls back to inference for exactly those vendors — which is correct: we have not been told
    # what they are, and inventing a sector to fill a cohort is the one thing seeding must not do.
    declare = not args.infer_sector
    print(f"Scoring {len(vendors)} vendors (concurrency {args.concurrency}, "
          f"sector {'declared from the seed set' if declare else 'left to inference'})…\n")
    results = asyncio.run(seed(vendors, args.concurrency, declare_sector=declare))

    failures = {d: r for d, r in results.items() if r.startswith("ERROR")}
    print(f"\nDone: {len(results) - len(failures)} scored, {len(failures)} failed.")
    for domain, reason in failures.items():
        print(f"  ! {domain}: {reason}")
    report_cohorts()


if __name__ == "__main__":
    main()
