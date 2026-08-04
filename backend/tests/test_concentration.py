"""P1 — fourth-party concentration across the book.

    "Nine of your twenty-three vendors authenticate through Okta. Four are Tier-1. A single Okta
     outage removes 17% of your supplier book simultaneously."

NO PER-VENDOR SCORE CAN EXPRESS THIS — all nine of those vendors may score an A — and no commercial
rating publishes it from free data. It is also the one finding that is a property of the BUYER'S
BOOK rather than of any supplier.

Both halves were already built and nothing joined them: `fourth_party.extract` has enumerated
providers per vendor since Phase 2, while `/api/portfolio` shipped a field called `concentration`
that was only high-criticality vendors below 60 and never called the extractor once.
"""

from __future__ import annotations

from app.concentration import as_dict, concentration
from app.fourth_party import Dependency


def _dep(provider: str, category: str, via: str = "MX record") -> Dependency:
    return Dependency(provider=provider, category=category, detected_via=[via])


def _book(okta: int = 9, critical_on_okta: int = 4, total: int = 23) -> tuple[dict, dict]:
    """A book where nine of twenty-three ride one identity provider, four of them Tier-1."""
    deps: dict[str, list[Dependency]] = {}
    crit: dict[str, str | None] = {}
    for i in range(total):
        ref = f"v{i:02d}"
        deps[ref] = [_dep("Cloudflare", "cdn_dns", "NS record")]
        if i < okta:
            deps[ref].append(_dep("Okta", "identity", "SPF include"))
        # Six Tier-1 vendors in the book; the first `critical_on_okta` of them use Okta.
        crit[ref] = "high" if i < critical_on_okta or total - i <= (6 - critical_on_okta) else "low"
    return deps, crit


# --------------------------------------------------------------------- the five metrics


def test_all_five_metrics_are_published():
    """The exit criterion, item by item: dependent count, book share, critical share, category,
    single point of failure."""
    deps, crit = _book()
    okta = next(p for p in concentration(deps, crit).providers if p.provider == "Okta")

    assert okta.dependent_count == 9
    assert okta.book_share == 9 / 23
    assert okta.critical_share == 4 / 6
    assert okta.category == "identity"
    assert okta.single_point_of_failure is True


def test_the_headline_sentence_is_the_one_a_board_hears():
    deps, crit = _book()
    cited = next(p for p in concentration(deps, crit).providers if p.provider == "Okta").cited()
    assert "9 of 23 scored vendors" in cited
    assert "39% of the book" in cited
    assert "4 of 6 business-critical vendors (67%)" in cited
    assert "single point of failure" in cited


# --------------------------------------------------------------------- the ranking


def test_ranking_is_by_critical_share_not_by_raw_count():
    """A provider under 90% of a book's STATIONERY suppliers is not a finding; one under 50% of its
    Tier-1 suppliers is a board paper. Sorting by count puts the first at the top of the page, and
    a report whose first row is noise trains the reader to skip the section."""
    deps: dict[str, list[Dependency]] = {}
    crit: dict[str, str | None] = {}
    # Twenty vendors on a ubiquitous CDN, none of them critical.
    for i in range(20):
        deps[f"bulk{i}"] = [_dep("BigCDN", "cdn_dns")]
        crit[f"bulk{i}"] = "low"
    # Three vendors on one identity provider — and all three are Tier-1.
    for i in range(3):
        deps[f"tier1-{i}"] = [_dep("Okta", "identity")]
        crit[f"tier1-{i}"] = "high"

    ranked = concentration(deps, crit).providers
    assert ranked[0].provider == "Okta", "raw count won — the noisy row is at the top"
    assert ranked[0].dependent_count == 3 < ranked[1].dependent_count == 20
    assert ranked[0].critical_share == 1.0


def test_a_single_dependency_is_not_concentration():
    """One dependent is a dependency, not a concentration. Reporting it would bury the four rows
    that matter under two hundred that do not."""
    deps = {"a": [_dep("NicheCo", "hosting")], "b": [_dep("Other", "hosting")]}
    crit = {"a": "high", "b": "high"}
    assert concentration(deps, crit).providers == []
    # ...and a small book can lower the line to see anything at all.
    assert len(concentration(deps, crit, min_dependents=1).providers) == 2


# --------------------------------------------------------------------- criticality handling


def test_vendors_without_criticality_are_counted_in_the_book_and_excluded_from_the_critical_share():
    """The exit criterion, and the exclusion has to be STATED — two percentages drawn from
    different populations will not reconcile, and a reader who notices that without an explanation
    concludes the numbers are wrong."""
    deps = {f"v{i}": [_dep("Okta", "identity")] for i in range(10)}
    crit: dict[str, str | None] = {f"v{i}": ("high" if i < 2 else None) for i in range(10)}

    report = concentration(deps, crit)
    okta = report.providers[0]

    assert okta.dependent_count == 10, "undeclared vendors must still count in the book"
    assert okta.book_share == 1.0
    assert okta.critical_share == 1.0, "2 of 2 declared-critical, not 2 of 10"
    assert report.without_criticality == 8
    assert any("COUNTED in the book share and EXCLUDED from the critical share" in c
               for c in report.caveats)


def test_a_book_with_no_criticality_declared_says_so_instead_of_reporting_zero():
    """A share with no denominator is not a small share, it is NO share. Rendering 0% would read as
    "none of your critical vendors depend on this" when the truth is "you have not told us which
    vendors are critical" — the failure in the reassuring direction."""
    deps = {f"v{i}": [_dep("Okta", "identity")] for i in range(10)}
    report = concentration(deps, {f"v{i}": None for i in range(10)})

    assert report.providers[0].critical_share is None
    assert report.providers[0].single_point_of_failure is False
    assert "cannot be computed" in report.providers[0].cited()
    assert any("cannot be computed for any provider" in c for c in report.caveats)


# --------------------------------------------------------------------- the invariant


def test_no_fourth_party_finding_can_enter_any_score():
    """THE EXIT CRITERION, asserted structurally rather than behaviourally.

    Penalising every Okta customer for an Okta CVE would punish thousands of vendors for a
    dependency they share with their competitors, AND count the same risk once per vendor in one
    buyer's book. The aggregate view is where that temptation returns, so the module imports
    nothing from the scoring path and emits no Finding.
    """
    import ast
    import inspect
    from pathlib import Path

    from app import concentration as module

    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    for name in imported:
        assert "scoring" not in name and "engine" not in name, (
            f"{name!r} reaches the concentration view — it is disclosed, never scored"
        )
    source = inspect.getsource(module)
    assert "Finding(" not in source and "penalty" not in source


def test_tier_two_visibility_is_disclosed_on_every_report():
    """We see who the VENDOR depends on; we do not see who THEY depend on. A book with no visible
    concentration may still funnel through one provider two hops down."""
    deps, crit = _book()
    for report in (concentration(deps, crit), concentration({}, {})):
        assert any("TIER-2 VISIBILITY ONLY" in c for c in report.caveats)
        assert any("DISCLOSED, NEVER SCORED" in c for c in report.caveats)
        assert any("leaves no public trace" in c for c in report.caveats)


def test_the_published_shape_names_which_vendors():
    """Unlike a peer cohort, these are the buyer's OWN vendors — *"which nine?"* is the first
    question anyone asks, and withholding it would make the finding unactionable."""
    deps, crit = _book()
    payload = as_dict(concentration(deps, crit))
    okta = next(p for p in payload["providers"] if p["provider"] == "Okta")
    assert len(okta["dependent_vendors"]) == 9
    assert okta["detected_via"] == ["SPF include"]

    # Both providers are single points of failure in this book, and that is correct rather than
    # noise: every vendor in the fixture sits behind Cloudflare, so 6 of 6 Tier-1 suppliers do too.
    # A CDN that carries the whole book IS a continuity event, and the fact that it is unremarkable
    # to an engineer is exactly why the aggregate is worth publishing to a board.
    assert set(payload["single_points_of_failure"]) == {"Okta", "Cloudflare"}
    # Ranked, so the reader meets the higher critical share first.
    assert payload["providers"][0]["critical_share"] >= payload["providers"][1]["critical_share"]
