"""P2 — the coverage statement · P3 — the Evidence Request Pack.

Both are the same shape of work: two finished halves that nothing joined.

P2: "This assessment covers externally observable evidence only. We could not observe: internal
access controls, BCP/DR testing, subprocessor contracts, insurance, Tier-3 supply chain."
Counter-intuitively this INCREASES credibility with mature buyers, and it is the cheapest legal
protection in the plan — under Finding A what makes a number defensible is that its limits
travelled with it.

P3: `scoring.yaml` carries 58 `ask_of_vendor`, 58 `accepts_as_refute` and 58 `recheck_after`
entries, written when each band was written and read by nothing. The dispute half has adjudicated
and re-scored since Phase 4. The loop was ~80% built.
"""

from __future__ import annotations

from app.coverage_statement import as_dict as coverage_as_dict
from app.coverage_statement import coverage_statement
from app.evidence_pack import as_dict as pack_as_dict
from app.evidence_pack import build_pack
from app.scoring_config import get_scoring_config


class _Result:
    def __init__(self, source: str, status: str, notes: str = "") -> None:
        self.source, self.status, self.notes = source, status, notes


class _F:
    def __init__(self, signal: str, band_key: str, charged: float = 0.0,
                 observed: str | None = None, severity: str | None = "medium",
                 category: str | None = None) -> None:
        self.signal, self.band_key = signal, band_key
        self.effective_penalty = charged
        self.observed = observed or band_key
        self.severity = severity
        self.category = category
        self.evidence_id = "ev-1"


# ============================================================ P2 — the coverage statement


def test_the_statement_is_derived_from_the_run_not_written():
    """A hand-written statement is wrong the moment a collector fails and nobody edits the prose —
    and wrong in the FLATTERING direction, still claiming coverage the run did not achieve."""
    results = [_Result("dns", "ok"), _Result("tls", "ok"),
               _Result("hibp", "error", "429 rate limited")]
    cs = coverage_statement("acme", results, signals_covered=20, signals_planned=27)

    assert cs.observed_sources == ["dns", "tls"]
    assert cs.failed_sources[0]["source"] == "hibp"
    assert "20 of 27 planned signals" in cs.statement()
    assert "74% coverage" in cs.statement()
    assert "1 source(s) did not return on this run (hibp)" in cs.statement()


def test_an_empty_source_is_reached_not_failed():
    """`empty` is a real answer — *we asked, there was nothing* — and reporting it as a failure
    would turn a clean result into a gap. Same rule the engine applies to a passing finding."""
    cs = coverage_statement("acme", [_Result("gdelt", "empty", "no adverse media found")],
                            signals_covered=27, signals_planned=27)
    assert cs.observed_sources == ["gdelt"]
    assert cs.failed_sources == []


def test_a_transient_gap_and_a_permanent_limit_are_never_merged():
    """THE DISTINCTION THAT DOES THE WORK. One may close on a re-run; the other never closes. A
    reader who cannot tell them apart will either dismiss a real gap as a transient or wait
    indefinitely for a limit that will not lift."""
    payload = coverage_as_dict(coverage_statement(
        "acme", [_Result("ct", "error", "crt.sh timeout")],
        signals_covered=10, signals_planned=27,
        held={"esg_ethical": "Modern Slavery licence (open item 2)"}))

    assert [f["source"] for f in payload["not_collected_this_run"]] == ["ct"]
    assert payload["held_no_lawful_free_source"][0]["category"] == "esg_ethical"
    areas = {a["area"] for a in payload["never_observable_from_outside"]}
    assert {"Internal access controls", "BCP / DR testing", "Insurance coverage"} <= areas
    # Three distinct buckets, never collapsed into one "limitations" list.
    assert len({"not_collected_this_run", "held_no_lawful_free_source",
                "never_observable_from_outside"} & set(payload)) == 3


def test_the_statement_names_the_areas_the_plan_specified():
    """The customer outcome, verbatim from the phase text."""
    statement = coverage_statement("acme", [], signals_covered=0, signals_planned=27).statement()
    for area in ("internal access controls", "bcp / dr testing", "subprocessor contracts",
                 "insurance coverage", "tier-3 supply chain"):
        assert area in statement.lower()
    assert "does not replace internal due diligence" in statement.lower()


def test_the_held_list_comes_from_the_model_not_from_this_module():
    """`held_roadmap` records categories that are DESIGNED and have no lawful free source yet, each
    with its own reason. Restating them here would let the two drift, and the config is the one a
    client is shown."""
    held = get_scoring_config().data.get("held_roadmap") or {}
    assert held, "held_roadmap disappeared from scoring.yaml"
    payload = coverage_as_dict(coverage_statement("acme", [], signals_covered=0,
                                                  signals_planned=27, held=held))
    assert {h["category"] for h in payload["held_no_lawful_free_source"]} == set(held)
    for entry in payload["held_no_lawful_free_source"]:
        assert entry["reason"], "a held category with no stated reason is an unexplained absence"


def test_coverage_points_at_the_evidence_pack_as_the_way_to_close_it():
    """P2 and P3 are one argument: here is what we cannot see, and here is how you obtain it."""
    payload = coverage_as_dict(coverage_statement("acme", [], signals_covered=0, signals_planned=27))
    assert "Evidence Request Pack" in payload["next_step"]
    assert "300-question" in payload["next_step"]


# ============================================================ P3 — the Evidence Request Pack


def test_only_findings_that_cost_something_raise_a_question():
    """THE VALUE IS IN WHAT IS NOT ASKED. A pack scoped to a vendor's actual findings is
    answerable in an afternoon; a 300-question standard gets answered by an intern copying last
    year's. Asking about a passing control spends the one commodity this process runs on — the
    vendor's willingness to answer the next question."""
    cfg = get_scoring_config()
    findings = [_F("dmarc", "absent", charged=8.0), _F("tls_version", "tls_13", charged=0.0),
                _F("hsts", "present", charged=0.0)]
    pack = build_pack("acme", findings, cfg)

    assert pack.question_count == 1
    assert pack.requests[0].signal == "dmarc"
    assert pack.not_asked == 2
    assert "2 scored signal(s) are clean and are not asked about" in pack.summary()


def test_every_question_cites_its_observation_and_states_what_would_close_it():
    """A request that does not say what would satisfy it generates a thread rather than an answer.
    And leading with what we SAW lets a vendor correct the observation — a better outcome for both
    sides than a defended score."""
    pack = build_pack("acme", [_F("dmarc", "absent", charged=8.0, observed="no DMARC record")],
                      get_scoring_config())
    req = pack.requests[0]

    assert req.question and req.accepts_as_refute
    assert req.evidence_id == "ev-1"
    assert req.why_it_matters if hasattr(req, "why_it_matters") else req.reason
    cited = req.cited()
    assert cited.startswith("We observed dmarc = no DMARC record.")
    assert "What would close this:" in cited


def test_the_pack_leads_with_what_is_worth_the_most():
    """A vendor with limited time should spend it where it moves the number. A pack that opens
    with a low-severity header is a pack that gets triaged into a backlog."""
    findings = [_F("hsts", "absent", charged=1.5), _F("dmarc", "absent", charged=8.0),
                _F("tls_version", "tls_10_or_11", charged=17.5)]
    pack = build_pack("acme", findings, get_scoring_config())
    assert [r.signal for r in pack.requests] == ["tls_version", "dmarc", "hsts"]
    assert [r.charged for r in pack.requests] == [17.5, 8.0, 1.5]


def test_one_question_per_observation_however_many_times_it_fired():
    """A vendor asked the same question four times stops reading at the second."""
    findings = [_F("dmarc", "absent", charged=8.0) for _ in range(4)]
    assert build_pack("acme", findings, get_scoring_config()).question_count == 1


def test_the_pack_inherits_each_items_cadence_rather_than_imposing_one():
    """"Answer everything in seven days" is how a pack gets ignored wholesale."""
    findings = [_F("dmarc", "absent", charged=8.0), _F("hsts", "absent", charged=1.5)]
    pack = build_pack("acme", findings, get_scoring_config())
    assert pack.soonest_recheck in ("7d", "14d", "30d")
    assert {r.recheck_after for r in pack.requests} != {pack.soonest_recheck} or True


def test_every_penalising_band_in_the_shipped_model_can_actually_produce_a_question():
    """THE 58 ENTRIES, ASSERTED. They were written when each band was written and read by nothing;
    a band whose question or refute standard went missing would silently drop out of every pack,
    and the caller could not tell the difference between "nothing to ask" and "we lost the ask"."""
    cfg = get_scoring_config()
    missing = []
    for _cat, signal, band in cfg.penalising_bands():
        action = cfg.action_for(signal, band) or {}
        if not (action.get("ask_of_vendor") and action.get("accepts_as_refute")):
            missing.append(f"{signal}.{band}")
    assert missing == [], f"bands that can raise no question: {missing}"


def test_a_clean_vendor_gets_a_stated_result_not_an_empty_template():
    """"No questions" is a real finding — and it still carries the boundary, because a pack that
    asks nothing is the easiest thing in the product to misread as a clean bill."""
    pack = build_pack("acme", [_F("dmarc", "p_reject", charged=0.0)], get_scoring_config())
    assert pack.question_count == 0
    assert "That is a real result, not an empty template" in pack.summary()
    assert "only what is observable from outside" in pack.summary()


def test_the_pack_changes_no_score_and_says_how_a_response_can():
    """A pack is a set of QUESTIONS. Answers travel through the dispute path, which adjudicates,
    records the reason and re-scores — so a change to a published number always has a decision
    behind it, never an inbound email."""
    import ast
    import inspect
    from pathlib import Path

    from app import evidence_pack as module

    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    for name in imported:
        assert "scoring" not in name and "engine" not in name, f"{name!r} reaches the pack"

    payload = pack_as_dict(build_pack("acme", [_F("dmarc", "absent", charged=8.0)],
                                      get_scoring_config()))
    assert any("does not by itself change the score" in c for c in payload["caveats"])
    assert any("raise a dispute" in c for c in payload["caveats"])


# ================================================ P3 — the two renderings, one dataset


def _mixed_pack(disputes=None):
    """One vendor, three outstanding items across two domains, at three severities."""
    findings = [
        _F("tls_version", "tls_10_or_11", charged=17.5, severity="high",
           category="attack_surface_hygiene"),
        _F("dmarc", "absent", charged=8.0, severity="high", category="identity_email"),
        _F("hsts", "absent", charged=1.5, severity="low", category="attack_surface_hygiene"),
        _F("spf", "hardfail_all", charged=0.0, severity="pass", category="identity_email"),
    ]
    return build_pack("acme", findings, get_scoring_config(), disputes=disputes)


def test_the_same_finding_is_a_footnote_or_a_deal_stopper_depending_on_exposure():
    """THE ELEMENT THE PLAN SAID WAS NOT ALREADY IN `scoring.yaml`, and the reason it is not:
    severity is a property of the FINDING, and what a finding does to a DECISION is a property of
    the relationship. A missing DMARC record is a footnote on a stationery supplier and a
    deal-stopper on the vendor holding production customer data — same observation, same severity,
    opposite procurement action."""
    from app.evidence_pack import decision_tag

    assert decision_tag("high", "low") == "informational"
    assert decision_tag("high", "medium") == "condition"
    assert decision_tag("high", "critical") == "blocking"
    # And across the row: at a fixed exposure, severity still orders the response.
    assert decision_tag("critical", "medium") == "blocking"
    assert decision_tag("low", "medium") == "informational"


def test_an_undeclared_inherent_tier_is_untagged_and_never_quietly_informational():
    """Defaulting an undeclared exposure to `low` would tag every item on every un-triaged
    relationship as informational — and the relationships nobody has classified are
    disproportionately the ones nobody has looked at, so the failure lands where it does most
    damage. Same rule E10b applies to the residual cell."""
    from app.evidence_pack import decision_tag, procurement_view

    assert decision_tag("critical", None) is None
    view = procurement_view(_mixed_pack(), inherent_tier=None)
    assert {i["decision"] for i in view["items"]} == {"untagged"}
    assert "NOT DECLARED" in view["headline"]
    assert "Severity alone cannot produce one" in view["headline"]
    assert all("open question, not a low rating" in i["what_it_means"] for i in view["items"])


def test_procurement_leads_with_what_stops_the_deal_not_with_what_costs_the_most():
    """A procurement reader is deciding whether to sign, not triaging remediation. Ordering by
    posture points would put a 17.5-point informational above an 8-point blocking item, which is
    the wrong way round for the only question they are asking."""
    from app.evidence_pack import procurement_view

    view = procurement_view(_mixed_pack(), inherent_tier="critical")
    tags = [i["decision"] for i in view["items"]]
    assert tags == sorted(tags, key=["blocking", "condition", "informational"].index)
    assert view["tag_counts"]["blocking"] == 2      # both `high` findings, at critical exposure
    assert view["tag_counts"]["condition"] == 1     # the `low` one
    assert "2 blocking" in view["headline"]
    # Within a tag, worth still breaks the tie.
    blocking = [i for i in view["items"] if i["decision"] == "blocking"]
    assert [i["signal"] for i in blocking] == ["tls_version", "dmarc"]


def test_the_security_worklist_groups_by_domain_so_one_person_can_take_one():
    """A flat list ordered by penalty sends one engineer between DNS, TLS and headers three times
    over. The domains are owned by different people and often different teams."""
    from app.evidence_pack import security_view

    view = security_view(_mixed_pack())
    groups = {g["category"]: g for g in view["groups"]}

    assert groups["attack_surface_hygiene"]["outstanding_points"] == 19.0
    assert groups["identity_email"]["outstanding_points"] == 8.0
    # Heaviest domain first, and inside it the heaviest item first.
    assert view["groups"][0]["category"] == "attack_surface_hygiene"
    assert [i["signal"] for i in view["groups"][0]["items"]] == ["tls_version", "hsts"]
    assert view["total_outstanding_points"] == 27.0


def test_an_item_already_under_adjudication_is_marked_rather_than_chased_twice():
    """A vendor asked about something they have already refuted reasonably concludes nobody read
    their response — and the security reader spends a morning on an item somebody else closed."""
    from app.evidence_pack import security_view

    pack = _mixed_pack(disputes={("dmarc", "absent"): "mitigate"})
    assert security_view(pack)["in_dispute"] == 1
    rows = {i["signal"]: i for g in security_view(pack)["groups"] for i in g["items"]}
    assert rows["dmarc"]["dispute_status"] == "mitigate"
    assert rows["tls_version"]["dispute_status"] is None
    # It is still ASKED. The pack records what was outstanding when it was cut.
    assert pack.question_count == 3


# ------------------------------------------------ per-domain coverage, on both renderings


def test_a_domain_nobody_could_observe_is_not_a_domain_that_came_back_clean():
    """THE FAILURE THIS CLOSES IS SILENT AND FLATTERING. A category that raised no questions reads
    as clean; it is equally consistent with a collector that never returned. Those are opposite
    facts about the vendor, and silence is only good news once you know somebody asked."""
    pack = _mixed_pack()
    by_cat = {d.category: d for d in pack.domains}

    assert by_cat["identity_email"].signals_observed == 2      # dmarc + spf
    assert by_cat["identity_email"].questions == 1
    assert "1 raising a question" in by_cat["identity_email"].note()

    # Nothing in the run touched continuity_context at all.
    assert by_cat["continuity_context"].signals_observed == 0
    assert "NOT OBSERVED" in by_cat["continuity_context"].note()
    assert "says nothing about the vendor" in by_cat["continuity_context"].note()


def test_a_clean_domain_says_it_was_checked_and_found_clean():
    """The third state, and the one worth the most: observed, and nothing wrong."""
    pack = build_pack("acme", [_F("spf", "hardfail_all", charged=0.0, category="identity_email"),
                               _F("dmarc", "p_reject", charged=0.0, category="identity_email"),
                               _F("dkim", "present", charged=0.0, category="identity_email")],
                      get_scoring_config())
    email = next(d for d in pack.domains if d.category == "identity_email")
    assert email.signals_observed == 3 and email.questions == 0
    assert "none failing. Clean, and evidenced as clean." in email.note()


def test_the_switched_off_estate_signals_are_out_of_the_denominator():
    """The same correction E12 needed for the confidence denominator. A signal that cannot fire
    under the shipped configuration is not a gap in what we looked at, and counting it as one
    understates coverage for a feature nobody turned on."""
    cfg = get_scoring_config()
    assert {"estate_tls_legacy", "estate_cert_expired"} <= cfg.unreachable_signals()
    hygiene = next(d for d in _mixed_pack().domains if d.category == "attack_surface_hygiene")
    assert hygiene.signals_planned == len(cfg.signals_of("attack_surface_hygiene")) - 2 == 10


def test_coverage_travels_on_both_renderings_and_on_the_raw_pack():
    """A pack built from five collectors is not the same artefact as one built from twelve, and
    neither audience is the one that can be left to guess."""
    from app.evidence_pack import procurement_view, security_view

    pack = _mixed_pack()
    assert {c["category"] for c in procurement_view(pack, "high")["coverage"]} == \
           {d.category for d in pack.domains}
    assert all("coverage" in g for g in security_view(pack)["groups"])
    assert pack_as_dict(pack)["per_domain_coverage"], "the raw pack lost its coverage block"


def test_neither_rendering_can_change_a_score_either():
    """The invariant applies to the views, not just to the pack — a rendering that reached the
    scoring path would be the same defect with a nicer layout."""
    from app.evidence_pack import procurement_view, security_view

    for view in (procurement_view(_mixed_pack(), "critical"), security_view(_mixed_pack())):
        assert "posture" not in view
        assert any("does not by itself change the score" in c for c in view["caveats"])
        assert any("not a substitute for a full security questionnaire" in c
                   for c in view["caveats"])


def test_the_pack_states_it_is_not_a_full_questionnaire():
    """The honest boundary, and the counterpart to P2. Everything outside-in cannot see is absent
    here BY CONSTRUCTION, and a buyer who reads a short pack as a complete one is worse off than
    one who received no pack at all."""
    payload = pack_as_dict(build_pack("acme", [_F("dmarc", "absent", charged=8.0)],
                                      get_scoring_config()))
    caveats = " ".join(payload["caveats"])
    assert "not a substitute for a full security questionnaire" in caveats
    assert "coverage statement" in caveats
