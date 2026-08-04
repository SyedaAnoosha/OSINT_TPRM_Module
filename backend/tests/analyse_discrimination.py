"""E0.3 — the discrimination analysis, as a runnable artefact.

    python -m tests.analyse_discrimination        (from backend/)

Writes `docs/discrimination-analysis.md`.

THE QUESTION. A signal that every vendor fails, or that every vendor passes, cannot order anyone.
It moves the intercept and nothing else — a flat tax wearing the clothes of a comparison. E0.3
exists because an earlier by-hand pass found nineteen of twenty-seven signals in that state, which
is a finding about the MODEL that no amount of per-vendor reporting would surface.

WHY THIS REUSES `app/benchmarking/discrimination.py` RATHER THAN REIMPLEMENTING IT.
EB already runs exactly this test, per cohort, on every build. A second implementation here would
drift from it, and then "the corpus says X but the product says Y" becomes a debugging session
about which one is right. The corpus is converted into `PeerRecord`s and handed to the same
function the product calls. Modal share for categorical bands (variance is undefined for strings);
the `max_modal_share` and `min_observations` thresholds come from `benchmarks.yaml`, not from here.

WHY THIS COULD NOT RUN BEFORE E0.2 — and nobody noticed.
`discrimination_min_observations` is **8**. The corpus was **5** published vendors. Every verdict
would have come back `untested`, so E0.3 was not merely unstarted: it was unrunnable, and the
status table said "◑ the instrument now exists" without anyone checking that the instrument had
enough input to say anything. E0.2 is a hard prerequisite for E0.3, which no plan recorded.

WHAT THIS IS NOT. It is not the seeded-pool run E0.3's exit criterion asks for. Eight vendors,
five of them constructed, is enough to test whether a signal is CONSTANT and nothing more. It
cannot estimate how strongly a signal discriminates, and it cannot say anything about whether the
ordering it produces is correct — that needs E0.4's outcome labels, which do not exist. Both
limits are stated on the artefact itself, not just here.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.benchmarking.config import get_benchmarking_config
from app.benchmarking.discrimination import discrimination_report
from app.benchmarking.models import PeerRecord
from app.scoring import ScoringEngine
from app.scoring_config import get_scoring_config

from .test_corpus import ALL_REFS, ARCHETYPE_REFS, AS_AT, VENDOR_REFS, load_fixture

REPORT = Path(__file__).resolve().parents[2] / "docs" / "discrimination-analysis.md"


def corpus_peers() -> tuple[list[PeerRecord], list[str]]:
    """Every PUBLISHED corpus vendor as a PeerRecord, plus the refs that published nothing.

    A refused or blocked vendor is deliberately excluded: it has no posture, so it is not a peer,
    and folding it in as a zero would be the same category error the Ghost exists to prevent.
    """
    peers: list[PeerRecord] = []
    unpublished: list[str] = []
    for ref in ALL_REFS:
        vendor, results = load_fixture(ref)
        out = ScoringEngine().score(vendor, results, now=AS_AT)
        score = out.score
        if score.posture is None:
            unpublished.append(ref)
            continue
        peers.append(PeerRecord(
            supplier_ref=ref,
            posture=int(score.posture),
            confidence=score.overall_confidence,
            domains={c.category: c.posture for c in score.categories if c.posture is not None},
            signals={n.signal: n.band_key for n in out.normalized if not n.is_sanctions},
        ))
    return peers, unpublished


def _band_spread(peers: list[PeerRecord], signal: str) -> str:
    counts = Counter(p.signals[signal] for p in peers if signal in p.signals)
    return " · ".join(f"`{b}`×{n}" for b, n in counts.most_common())


def build_report() -> str:
    cfg, bcfg = get_scoring_config(), get_benchmarking_config()
    peers, unpublished = corpus_peers()
    verdicts = discrimination_report(peers)

    signals = [v for v in verdicts if v.kind == "signal"]
    domains = [v for v in verdicts if v.kind == "domain"]
    flat = [v for v in signals if v.verdict == "non_discriminating"]
    works = [v for v in signals if v.verdict == "discriminating"]
    untested = [v for v in signals if v.verdict == "untested"]

    planned = cfg.planned_signal_count()
    never_observed = sorted(
        {s for c in cfg.category_names() for s in cfg.signals_of(c)}
        - {s for p in peers for s in p.signals}
    )

    L: list[str] = []
    add = L.append
    add("# Discrimination analysis — which signals can actually rank a vendor")
    add("")
    add(f"**Generated:** {datetime.now(UTC).date()} by `python -m tests.analyse_discrimination` · "
        f"**Model:** `scoring.yaml` v{cfg.version} · "
        f"**Population:** {len(peers)} published corpus vendors "
        f"({len(VENDOR_REFS)} real, {len(ARCHETYPE_REFS)} synthetic archetypes)")
    add("")
    add("> **Do not read this as evidence that the model ranks vendors correctly.** It answers a "
        "narrower question — *can this signal distinguish anyone at all?* A signal every vendor "
        "fails and a signal every vendor passes are equally useless for ordering, and both look "
        "fine on a per-vendor report. Whether the ordering it produces is *right* needs outcome "
        "labels (E0.4), which do not exist.")
    add("")

    # ------------------------------------------------------------------ population honesty
    add("## The population, and what it cannot tell you")
    add("")
    add(f"- **{len(peers)} published vendors.** The discrimination threshold in `benchmarks.yaml` "
        f"is `min_observations: {bcfg.discrimination_min_observations()}` — so this analysis "
        f"**could not have run at all before E0.2**, when the corpus held "
        f"{len(VENDOR_REFS)} published vendors. Every verdict would have read `untested`.")
    add(f"- **{len(ARCHETYPE_REFS)} of the {len(ALL_REFS)} fixtures are CONSTRUCTED**, not "
        "observed (`tests/build_archetypes.py`). They were built to exercise engine paths, so "
        "they widen the band spread **by design**. A signal that discriminates here has been "
        "shown to be capable of varying — not shown to vary across real vendors.")
    if unpublished:
        add(f"- **{len(unpublished)} fixtures publish no posture** and are excluded rather than "
            f"counted as zero: {', '.join(f'`{r}`' for r in unpublished)}. A refused or gated "
            "vendor is not a peer.")
    add(f"- **This is not the seeded-pool run** E0.3's exit criterion asks for. That needs "
        "`python -m app.seed_cohorts --all` against ~115 real vendors and remains outstanding.")
    add("")

    # ------------------------------------------------------------------ the finding
    add("## Signals that cannot rank anyone")
    add("")
    if flat:
        add(f"`modal_share >= {bcfg.max_modal_share()}` — nearly every vendor sits in one band.")
        add("")
        add("| Signal | Modal share | Bands observed |")
        add("|---|--:|---|")
        for v in flat:
            add(f"| `{v.key}` | {v.value:.2f} | {_band_spread(peers, v.key)} |")
    else:
        add(f"**None.** Every observed signal varies across the population at "
            f"`max_modal_share = {bcfg.max_modal_share()}`.")
    add("")
    if never_observed:
        add(f"### Never observed at all — {len(never_observed)} of {planned}")
        add("")
        add("A signal no collector emitted for any vendor is not *non-discriminating*; it is "
            "**absent**, which is worse, because it silently occupies a slot in the confidence "
            "denominator while contributing nothing to either axis.")
        add("")
        for s in never_observed:
            add(f"- `{s}`")
        add("")

    # ------------------------------------------------------------------ the real five, alone
    # The section that stops this document lying by omission. Run over all eight, the archetypes
    # make almost everything look like it varies — because they were BUILT to vary. The question
    # E0.3 actually asks is about real vendors, and there the original finding still holds.
    real = [p for p in peers if p.supplier_ref in VENDOR_REFS]
    real_signals: dict[str, list[str]] = {}
    for p in real:
        for signal, band in p.signals.items():
            real_signals.setdefault(signal, []).append(band)

    def _pen(signal: str, band: str) -> float:
        return cfg.penalty_for(cfg.signal_severity(cfg.category_of(signal) or "", signal, band))

    # TWO DIFFERENT FAILURES, and an earlier draft of this report conflated them — which understated
    # the flat tax by three signals. A signal can charge every single vendor while its BANDS vary:
    # `stale_hosts` reads `many` for some and `some` for others, so modal share says it
    # discriminates, and yet nobody escapes a penalty. "Everyone pays something" is the condition
    # E0.3 names, and it is not the same as "everyone sits in one band".
    n_real = len(real)
    charges_everyone = {
        s: b for s, b in real_signals.items()
        if len(b) == n_real and all(_pen(s, band) > 0 for band in b)
    }
    charges_nobody = {
        s: b for s, b in real_signals.items()
        if len(b) == n_real and all(_pen(s, band) == 0 for band in b)
    }
    real_flat = {s: b for s, b in real_signals.items() if len(set(b)) == 1}
    all_pass, all_fail = charges_nobody, charges_everyone

    add("## ⚠️ The real five, analysed separately — the number that matters")
    add("")
    add("**Read this section before the one above it.** Across all eight the answer is *"
        "\"everything discriminates\"*, and that is an artefact: the archetypes were constructed "
        "to exercise distinct engine paths, so they vary **by design**. Removing them and asking "
        "the question of the five real vendors gives the opposite answer, and it is the answer "
        "E0.3 was written to obtain.")
    add("")
    add(f"n = {len(real)}, which is **below** the `min_observations: "
        f"{bcfg.discrimination_min_observations()}` threshold. Reported anyway, flagged as "
        "under-powered, because a constant across five vendors is still a constant — and "
        "suppressing it until the pool is seeded is how this finding stayed invisible.")
    add("")
    add("| | Count | Signals |")
    add("|---|--:|---|")
    add(f"| **Charges every vendor** — a flat tax, whatever the bands do | {len(all_fail)} | "
        + " ".join(f"`{s}`" for s in sorted(all_fail)) + " |")
    add(f"| **Charges no vendor** — all-pass, so it ranks nobody either | {len(all_pass)} | "
        + " ".join(f"`{s}`" for s in sorted(all_pass)) + " |")
    add(f"| **Separates the real five** | "
        f"{len(real_signals) - len(all_fail) - len(all_pass)} | "
        + " ".join(f"`{s}`" for s in sorted(set(real_signals) - set(all_fail) - set(all_pass)))
        + " |")
    add("")
    # Each vendor's own worst charge per signal, averaged — not the modal band's penalty. A signal
    # that charges 20 for three vendors and 8 for two does not cost "8 across the board".
    flat_tax = sum(
        sum(_pen(s, band) for band in bands) / len(bands) for s, bands in all_fail.items()
    )
    add(f"**{len(all_fail) + len(all_pass)} of the {len(real_signals)} signals observed on real "
        f"vendors cannot order them at all.** The {len(all_fail)} that charge everyone cost a "
        f"mean of **{flat_tax:.0f} category points ≈ {flat_tax / cfg.penalty_divisor():.1f} "
        f"posture points** before anything specific to a vendor is considered — moving the whole "
        "population down together and separating none of it.")
    add("")
    add("> **Two different failures, and they are easy to conflate.** A signal can charge every "
        "vendor while its *bands* vary — `stale_hosts` reads `many` for three and `some` for two, "
        "so modal share calls it discriminating, and yet nobody escapes a penalty. "
        f"{len(real_flat)} signals are constant-BAND; **{len(all_fail)} are constant-CHARGE**, "
        "and it is the second number E0.3 is about. An earlier draft of this report reported the "
        "first and understated the flat tax by three signals.")
    add("")
    unobserved_real = sorted(
        {s for c in cfg.category_names() for s in cfg.signals_of(c)} - set(real_signals))
    if unobserved_real:
        add(f"One further signal is never observed on a real vendor at all — "
            + " ".join(f"`{s}`" for s in unobserved_real)
            + " — so it occupies a slot in the confidence denominator and contributes to neither "
            "axis. It fires only on `synthetic_smallco`, which is why that archetype was built.")
        add("")
    add("This is a finding about the **corpus** as much as the model: five large, well-run "
        "technology vendors genuinely are alike. It becomes a finding about the model only once "
        "the seeded pool shows the same constants across a diverse population — which is exactly "
        "why the exit criterion asks for the seeded run and not this one.")
    add("")
    add("### Against the by-hand baseline, and what the migration actually bought")
    add("")
    add("The original E0.3 pass, run by hand against `scoring.yaml` v4.2.0 on the same five "
        "vendors, found **six signals penalising 100% of them** — `stale_hosts` `contactability` "
        "`weak_issuance` `subdomain_estate` `cert_posture` `vd_program` — worth **≥28 category "
        "points, roughly 7 posture points of flat tax**.")
    add("")
    add(f"Same five vendors, same analysis, v{cfg.version}: **{len(all_fail)} "
        f"{'signal' if len(all_fail) == 1 else 'signals'}** — "
        + " ".join(f"`{s}`" for s in sorted(all_fail))
        + f" — worth a mean {flat_tax:.0f} category points ≈ "
        f"{flat_tax / cfg.penalty_divisor():.1f} posture points.")
    add("")
    add("**Compare the signal counts, not the posture points.** The two posture figures are on "
        f"different scales — `penalty_divisor` moved 4.0 → {cfg.penalty_divisor()} at E5, so the "
        "same category point costs more posture now — and the v4.2.0 figure was written as a "
        "lower bound (`≥28`). **Six flat taxes became four.** That is the comparable number.")
    add("")
    add("Two went away and four did not, which is a more useful result than a clean sweep would "
        "have been. `contactability` stopped charging at E3 and `cert_posture` at E2 "
        "(`none_claimed` is free now, and the vendors that still pay are the ones asserting a "
        "certification that does not check out — a different and defensible charge).")
    add("")
    add("**The four that remain are the case for E6, stated in one line.** `stale_hosts`, "
        "`subdomain_estate` and `weak_issuance` all charge every real vendor, and all three are "
        "footprint signals with no denominator: they measure how *large* a vendor's estate is and "
        "call the answer risk. E6 divides the first by the second. `vd_program` is the fourth and "
        "is a different problem — no real vendor runs a bug bounty we can observe — which puts it "
        "with E9b's positive credit rather than with E6.")
    add("")

    # ------------------------------------------------------------------ what works
    add(f"## The full population — signals that discriminate across all {len(peers)}")
    add("")
    add("| Signal | Modal share | Bands observed |")
    add("|---|--:|---|")
    for v in sorted(works, key=lambda v: v.value or 0):
        add(f"| `{v.key}` | {v.value:.2f} | {_band_spread(peers, v.key)} |")
    add("")
    if untested:
        add(f"### Untested — {len(untested)}")
        add("")
        add("Observed on too few vendors to test. Not a pass.")
        add("")
        for v in untested:
            add(f"- `{v.key}` — {v.detail}")
        add("")

    # ------------------------------------------------------------------ categories
    add("## Category postures")
    add("")
    add("| Category | Verdict | Statistic |")
    add("|---|---|---|")
    for v in sorted(domains, key=lambda v: v.key):
        add(f"| `{v.key}` | {v.verdict.replace('_', ' ')} | {v.detail} |")
    add("")

    # ------------------------------------------------------------------ spread
    add("## Published postures")
    add("")
    add("| Vendor | Posture | Confidence |")
    add("|---|--:|--:|")
    for p in sorted(peers, key=lambda p: -p.posture):
        kind = "synthetic" if p.supplier_ref in ARCHETYPE_REFS else "real"
        add(f"| `{p.supplier_ref}` ({kind}) | {p.posture} | {p.confidence:.3f} |")
    add("")
    postures = sorted(p.posture for p in peers)
    add(f"Range **{postures[0]}–{postures[-1]}**, spread {postures[-1] - postures[0]} points. "
        f"Real vendors alone span "
        f"{min(p.posture for p in peers if p.supplier_ref in VENDOR_REFS)}–"
        f"{max(p.posture for p in peers if p.supplier_ref in VENDOR_REFS)} — "
        "**a 13-point band across five vendors**, which is the compression this whole migration "
        "is trying to fix and the reason a 5-vendor corpus cannot detect a discrimination problem.")
    add("")
    add("---")
    add("")
    add("*Regenerate with `python -m tests.analyse_discrimination`. Do not hand-edit.*")
    return "\n".join(L) + "\n"


def main() -> None:
    REPORT.write_text(build_report(), encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
