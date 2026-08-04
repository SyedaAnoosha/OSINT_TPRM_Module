"""E11 — the seeding run, and the two defects that made it cost more than it delivered.

E11's remaining work is *the pool, and only the pool* — an operational task with a politeness
budget, not an engineering one. That framing was right about seeding and wrong about the seeder:
the tool an operator runs 114 live scans through had two defects that made those scans buy less
than they should, and both failed silently.

  1. **The sector was thrown away at the call site.** Every seed vendor sits under a sector heading
     — the key of the dict it is in — and `seed()` called `run_pipeline(vendor)` with no sector, so
     cohort assignment fell entirely to inference from GLEIF/Wikidata/PDL industry labels. That
     inference fails for a meaningful share of real companies, and a vendor with no sector gets no
     cohort at all: a live query against someone else's free service, spent in full, contributing
     to no peer group.
  2. **Three headings were not sectors.** `food_agriculture`, `transport_logistics` and
     `energy_utilities` are not in the controlled vocabulary (`agriculture`, `logistics`,
     `utilities` are). `--sector` offered an operator three headings that could never match a
     cohort key even once the sector was passed through.

And `--status`, the one instrument for *"is the pool real yet?"*, reported against
`benchmark.min_cohort_n()` — the DEPRECATED v1 gate — while saying nothing at all about E13, which
is the only thing the pool is actually blocking.
"""

from __future__ import annotations

import inspect

import pytest

from app import seed_cohorts as sc
from app.scoring.log_odds import preconditions
from app.sectors import known_sectors


# --------------------------------------------------------------- the controlled vocabulary


def test_every_seed_heading_is_a_sector_the_system_can_form_a_cohort_on():
    """THE FIRST DEFECT, ASSERTED AT THE VOCABULARY RATHER THAN AT THE THREE NAMES.

    Naming the three that were wrong would pass forever and catch nothing; checking the set against
    `sectors.py` catches the next one. A wrong heading fails in the expensive direction — the run
    completes, every vendor scores, the budget is spent, and the cohort has zero members.
    """
    assert set(sc.SEED_SETS) <= known_sectors()


def test_a_heading_outside_the_vocabulary_fails_at_import_not_at_runtime():
    """Loudly, and before a single request leaves the machine. A validation that fires after 114
    live scans is a post-mortem, not a guard."""
    original = dict(sc.SEED_SETS)
    try:
        sc.SEED_SETS["energy_utilities"] = [sc.SeedVendor("Someone", "someone.com")]
        with pytest.raises(sc.SeedVocabularyError) as exc:
            sc._validate_seed_sectors()
        assert "energy_utilities" in str(exc.value)
        assert "fills no cohort" in str(exc.value)
    finally:
        sc.SEED_SETS.clear()
        sc.SEED_SETS.update(original)


def test_the_seed_list_is_named_real_companies_and_excludes_the_regression_corpus():
    """A benchmark population built from the five vendors the model is TUNED against would be
    measuring itself. Restated here because the exclusion lives only in a comment otherwise."""
    domains = {v.domain for group in sc.SEED_SETS.values() for v in group}
    assert not domains & {"atlassian.com", "snowflake.com", "slack.com", "myob.com",
                          "onetrust.com"}
    assert len(domains) == sum(len(g) for g in sc.SEED_SETS.values()), "a duplicate domain"


# --------------------------------------------------------------- the sector actually travels


def test_the_heading_a_vendor_is_filed_under_is_the_sector_it_is_scored_with():
    """THE JOIN. The dict key already knows the answer; until this was wired, the call site threw
    it away and let inference decide."""
    assert sc.sector_of(sc.SeedVendor("Canva", "canva.com")) == "technology"
    assert sc.sector_of(sc.SeedVendor("Adyen", "adyen.com")) == "financial_services"
    # An ad-hoc `--domains` vendor has no heading, and inventing one to fill a cohort is the single
    # thing seeding must not do.
    assert sc.sector_of(sc.SeedVendor("Nobody", "nobody.example")) is None


@pytest.mark.anyio
async def test_seed_passes_the_declared_sector_through_to_the_pipeline(monkeypatch):
    """Asserted through the call rather than by reading the source — the previous version of this
    code would have passed any structural check, because the parameter simply was not supplied."""
    seen: list[tuple[str, str | None]] = []

    class _Score:
        blocked = refused = False
        posture, grade, overall_confidence = 71, "B", 0.83

    class _Outcome:
        score = _Score()

    async def fake_pipeline(vendor, **kwargs):
        seen.append((vendor.domain, kwargs.get("sector")))
        return _Outcome()

    monkeypatch.setattr(sc, "run_pipeline", fake_pipeline)

    vendors = [sc.SeedVendor("Canva", "canva.com"), sc.SeedVendor("Adyen", "adyen.com")]
    await sc.seed(vendors)
    assert sorted(seen) == [("adyen.com", "financial_services"), ("canva.com", "technology")]

    seen.clear()
    await sc.seed(vendors, declare_sector=False)
    assert sorted(seen) == [("adyen.com", None), ("canva.com", None)]


def test_the_declared_sector_is_recorded_as_client_stated_not_as_an_observation():
    """It is our editorial judgement about which peer group a company belongs in, and the profile
    records it with `source="client"` exactly like a buyer's own declaration. Asserting the seeder
    uses the same door a client does is what keeps a seeded sector from reading as a finding."""
    sig = inspect.signature(sc.run_pipeline)
    assert "sector" in sig.parameters
    assert "declare_sector" in inspect.signature(sc.seed).parameters


# --------------------------------------------------------------- the instrument


def test_status_reports_against_the_gates_that_gate_and_not_the_deprecated_one(monkeypatch, capsys):
    """THE SECOND DEFECT. `--status` measured `benchmark.min_cohort_n()` — the v1 path EB replaced
    — and printed one publishes/insufficient column. A quartile becomes available at 8 and a
    percentile at 30 because they are different claims; an operator watching one column could not
    tell which of the things they were waiting for had arrived."""
    monkeypatch.setattr(sc, "cohort_depths", lambda: {
        "technology|rev=?|emp=large|anz": 12,
        "healthcare|rev=?|emp=medium|anz": 3,
    })
    sc.report_cohorts()
    out = capsys.readouterr().out

    assert "EB quartile + rank-of-n" in out
    assert "EB percentile" in out
    assert "E13 shrinkage floor" in out
    assert "deprecated" in out, "the v1 gate is still shown, and still labelled as superseded"
    # 12 clears quartile and the E13 floor, not the percentile. 3 clears nothing.
    assert "[vqL]" not in out and "[vq-L]" in out
    assert "[----]" in out


def test_status_answers_the_question_the_pool_actually_blocks(monkeypatch, capsys):
    """E11's remaining work exists mainly to unblock E13, and nothing reported on that. An operator
    finishing a 114-vendor run had no way to learn what it had bought them."""
    monkeypatch.setattr(sc, "cohort_depths", lambda: {"technology|rev=?|emp=large|anz": 9})
    sc.report_cohorts()
    out = capsys.readouterr().out

    assert "1 of 1 cohort(s) can supply L_peer" in out
    assert "publishes for these on their next score" in out
    assert "still a release decision" in out, (
        "L_peer becoming available is not the same event as E13 moving the published number"
    )


def test_a_thin_pool_is_told_what_it_will_keep_seeing_in_the_transforms_own_words(
        monkeypatch, capsys):
    """`preconditions()` is called rather than restated, so the status line cannot drift from the
    rule the transform enforces — which is how `min_cohort_n: 1` survived in the first place."""
    monkeypatch.setattr(sc, "cohort_depths", lambda: {"mining|rev=?|emp=small|anz": 5})
    sc.report_cohorts()
    out = capsys.readouterr().out

    assert "0 of 1 cohort(s) can supply L_peer" in out
    assert preconditions(sc._probe(5))[-1] in out
    assert "cohort holds 5 peers, below the floor of 8" in out


def test_no_cohorts_at_all_says_so_rather_than_printing_an_empty_table(monkeypatch, capsys):
    monkeypatch.setattr(sc, "cohort_depths", lambda: {})
    sc.report_cohorts()
    assert "score some vendors first" in capsys.readouterr().out
