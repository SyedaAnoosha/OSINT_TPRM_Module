"""The inventory of record — which rows in the book are RELATIONSHIPS, and what each one is exposed to.

WHY THIS EXISTS, AND WHY IT IS NOT A FORM FIELD. P9's dashboard reported
`inherent_tier_declaration_rate: 0.0%` across 146 vendors, and the obvious reading — "nobody has got
round to it" — was wrong. The only path that has ever accepted a criticality is `POST
/api/vendors/score`, which re-runs the entire pipeline. **Declaring an exposure cost a full scan of
someone else's free services**, so of course nobody declared one. A rate of zero was a missing route
wearing the costume of a missing habit, and the fix is a declaration path that writes a declaration
and nothing else.

═══ THE DENOMINATOR WAS ALSO WRONG, AND THAT IS THE BIGGER FINDING ═══

146 scored vendors are not 146 relationships. The book is three populations that a single count had
been silently averaging over:

    relationship        A vendor this buyer actually engages. HAS an inherent exposure, so the
                        question "what is it?" has an answer and somebody owns giving it.
    corpus              Scored by `seed_cohorts` ONLY to give E11's peer groups a population.
                        There is no commercial relationship, so there is no exposure to declare —
                        and declaring one would be inventing a contract to make a metric go green.
    not_a_relationship  Typos (`aatlassian`), malformed refs (`http://servicenow`), products
                        mistaken for vendors (`jira`, `claude`), and the buyer's own domains.
                        These are inventory defects. They are named here rather than deleted,
                        because an append-only store has no delete and a silently dropped row is
                        indistinguishable from a row nobody looked at.

**`app/program_maturity.py` scores Inventory & Tiering at Level 2 because there is "no inventory of
record". This file is the inventory of record.** It is deliberately the flat, readable, reviewable
thing a person can be walked through in a meeting — not a table, because the point of it is that a
human argues with each line.

═══ EVERY DECLARATION IS PROVISIONAL UNTIL A NAMED PERSON CONFIRMS IT ═══

`confirmed=False` is the default and every seeded row below carries it. A provisional declaration is
a real declaration — it routes P5's depth, it publishes an E10b residual tier, it tags P3's evidence
pack — but it travels with a caveat naming it as unconfirmed, and the dashboard reports confirmed
and provisional as separate counts rather than as one green number.

This is the same discipline `profile._derive_cohort` already uses when it falls back to the
`technology` sector with `source="default"`: a fallback that unblocks a feature is legitimate ONLY
where the reader can see it is a fallback. What the register must never become is the thing
`inherent_tier` refuses in its own docstring — our label, published as their exposure, with nothing
on the page to say which it is.

NOTHING HERE INFERS AN EXPOSURE. Every value below was written by a person, and `_validate` refuses
a declaration with no basis, no author and no date.

USAGE
    python -m app.inherent_register --status          # the three populations, and what is declared
    python -m app.inherent_register --dry-run         # what --apply would write, writing nothing
    python -m app.inherent_register --apply           # append the declarations to the store
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any, Literal

from .benchmarking.models import DataAccessScope
from .logging_config import get_logger, setup_logging
from .models import Criticality, Substitutability

log = get_logger("inherent_register")

#: What kind of row this is. The three-way split is the whole point — see the module docstring.
Classification = Literal["relationship", "corpus", "not_a_relationship"]

#: Who signed the provisional declarations below, and when. Kept as constants so a reviewer can see
#: at a glance that ONE person declared ALL of them on ONE day, which is exactly the caveat that
#: matters when reading a book where nothing is confirmed yet.
_DECLARED_BY = "TPRM lead (provisional — pending relationship-owner confirmation)"
_DECLARED_ON = "2026-08-01"


@dataclass(frozen=True)
class Entry:
    """One row of the inventory. A declaration, or a written reason there is nothing to declare."""

    ref: str
    classification: Classification
    #: The two E10b inputs. Both optional individually — `inherent_tier` takes the WORSE of the two
    #: and says so when only one was supplied — but a `relationship` must carry at least one.
    criticality: Criticality | None = None
    data_access_scope: DataAccessScope | None = None
    #: P8. Declared separately because it moves the residual tier and never the posture.
    substitutability: Substitutability | None = None
    #: Why this exposure, in the reader's language. This is the sentence a relationship owner
    #: argues with, and a declaration without one is a number nobody can contest.
    basis: str = ""
    declared_by: str | None = None
    declared_on: str | None = None
    #: FALSE MEANS PROVISIONAL. Set true only when the accountable relationship owner has confirmed
    #: it. Never set true in bulk, and never set true by the code that applies the register.
    confirmed: bool = False
    #: For inventory defects: what is wrong with this row and what should happen to it.
    note: str | None = None

    @property
    def declarable(self) -> bool:
        return self.classification == "relationship"

    @property
    def declared(self) -> bool:
        return self.criticality is not None or self.data_access_scope is not None

    @property
    def provisional(self) -> bool:
        return self.declared and not self.confirmed


class RegisterError(ValueError):
    """Raised at import when a register entry cannot be published as written."""


# ═════════════════════════════════════════════════════════════════ the relationships
#
# Twenty-three rows, each declared by hand. The exposures below describe a small Australian
# risk-management consultancy: what it runs its own business on, what holds its clients' assessment
# material, and the GRC platforms it is evaluating (which hold nothing yet, and are declared at the
# exposure they WOULD carry only where they are already in a trial with real data).

_RELATIONSHIPS: tuple[Entry, ...] = (
    Entry("microsoft", "relationship", criticality="high", data_access_scope="high",
          substitutability="sole_source",
          basis="Microsoft 365 and Entra ID are the identity, mail and document substrate for the "
                "whole firm. A failure here is not a degraded service, it is no access to anything. "
                "Data access scope is high rather than critical: client assessment material lives "
                "in SharePoint, but no production customer data of our clients' does. Sole source "
                "in practice rather than by contract — the switching cost is the identity estate.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("atlassian", "relationship", criticality="high", data_access_scope="high",
          substitutability="low",
          basis="Jira and Confluence hold the engagement record for every client assessment — "
                "findings, drafts, and correspondence. High criticality because delivery stops "
                "without it; high scope because that content is client-confidential.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("anthropic", "relationship", criticality="high", data_access_scope="high",
          substitutability="low",
          basis="Claude is the summarisation path in this platform. Prompts carry vendor assessment "
                "content, which is client-confidential, so scope is high. Criticality is high "
                "because the narrative layer has no non-LLM fallback. Substitutability is LOW and "
                "not sole_source: a swap is possible and has a real cost, which is what low means.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("snowflake", "relationship", criticality="high", data_access_scope="critical",
          substitutability="low",
          basis="The analytics warehouse holding assessment history across all clients. Scope is "
                "CRITICAL — this is the largest single concentration of client material the firm "
                "holds, and a compromise here is a compromise of every engagement at once.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("salesforce", "relationship", criticality="high", data_access_scope="high",
          substitutability="low",
          basis="CRM of record: client contacts, opportunities and commercial terms. High on both "
                "axes. Contact records are business contacts at client organisations, held under "
                "the role-address rule the §4.2 bright line sets for this platform's own ingest.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("myob", "relationship", criticality="high", data_access_scope="high",
          substitutability="low",
          basis="Accounting and payroll. Criticality high because payroll has a statutory deadline "
                "that does not move; scope high because it holds employee financial records. Note "
                "this vendor currently REFUSES a posture for thin evidence — an undeclared "
                "exposure on a ghost record was the worst combination in the book.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("cloudflare", "relationship", criticality="high", data_access_scope="medium",
          substitutability="low",
          basis="DNS and WAF in front of this platform. Criticality high — a failure takes the "
                "product offline and there is no second path. Scope is MEDIUM, not high: it "
                "terminates TLS and therefore sees traffic, but stores no assessment content.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("onetrust", "relationship", criticality="medium", data_access_scope="high",
          substitutability="medium",
          basis="Privacy and TPRM tooling in active trial with real vendor records, so scope is "
                "already high even though criticality is not — the firm delivered assessments "
                "without it last quarter and could again.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("monday", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="Project and engagement tracking. Task titles name clients; deliverables do not "
                "live here. Readily replaced, and the firm has migrated a tracker before.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("slack", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="Internal comms. Policy forbids client material in channels; the scope is medium "
                "rather than low because policy is not a control and the platform cannot enforce it.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("openai", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="Secondary LLM, used for evaluation and never on the client-facing summarisation "
                "path. Interchangeable with the primary by design.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("servicenow", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="GRC platform under evaluation. A trial tenant carries sample records only, which "
                "is what keeps scope at medium rather than high.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("archerirm", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="GRC platform under evaluation. Sample records only. One of five competing "
                "platforms in the same trial, hence readily substitutable.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("sai360", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="GRC platform under evaluation. Sample records only; one of five in the same trial.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("logicmanager", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="GRC platform under evaluation. Sample records only; one of five in the same trial.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("corporater", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="GRC platform under evaluation. Sample records only; one of five in the same trial. "
                "This vendor currently publishes no posture, so the declaration is the only thing "
                "on its card — which is the correct order: exposure is knowable before posture is.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("metricmstream", "relationship", criticality="medium", data_access_scope="medium",
          substitutability="high",
          basis="GRC platform under evaluation (MetricStream). Sample records only; one of five in "
                "the same trial.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON,
          note="REF IS MISSPELLED — 'metricmstream' should be 'metricstream'. Re-key and re-score "
               "under the correct ref, then retire this row. Left declared in the meantime so the "
               "relationship is not invisible while the ref is being fixed."),
    Entry("adobe", "relationship", criticality="low", data_access_scope="low",
          substitutability="high",
          basis="Document tooling for report production. Outputs are drafted elsewhere and "
                "assembled here; nothing is stored in the vendor's cloud.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("cisco", "relationship", criticality="low", data_access_scope="low",
          substitutability="high",
          basis="Office networking hardware. No data access, and a failure is an inconvenience for "
                "a firm that works remotely by default.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("vmware", "relationship", criticality="low", data_access_scope="low",
          substitutability="high",
          basis="Legacy virtualisation on one retired host. Slated for decommission; carried on the "
                "register until it is, because an undeclared vendor is worse than a low-tier one.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("ibm", "relationship", criticality="low", data_access_scope="low",
          substitutability="high",
          basis="No current engagement. Scored during a procurement that did not proceed, and kept "
                "on the register at low/low rather than deleted so the assessment is not repeated.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("oracle", "relationship", criticality="low", data_access_scope="low",
          substitutability="high",
          basis="No production use. Scored as a procurement candidate. Currently BLOCKED on a "
                "sanctions-gate match pending adjudication, which is why declaring the exposure "
                "matters: a blocked record with no declared tier tells an adjudicator nothing "
                "about how much hangs on the answer. Here, almost nothing.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
    Entry("spotify", "relationship", criticality="low", data_access_scope="low",
          substitutability="high",
          basis="Non-business subscription that entered the book through an expense line. Declared "
                "low/low and flagged for removal at renewal — it is on the register because it is "
                "in the book, not because it belongs in either.",
          declared_by=_DECLARED_BY, declared_on=_DECLARED_ON),
)


# ═════════════════════════════════════════════════════════════════ the inventory defects
#
# Nine rows that are in the book and are not relationships. NONE carries a declaration, and
# `_validate` refuses one: an exposure declared against a typo is a fabricated relationship, and it
# would count toward the declaration rate exactly like a real one.

_NOT_RELATIONSHIPS: tuple[Entry, ...] = (
    Entry("aatlassian", "not_a_relationship",
          note="Typo of `atlassian`, scored in full. Supersede with the correctly-spelled record; "
               "the score row stays readable because the store is append-only."),
    Entry("atllassian", "not_a_relationship",
          note="Second typo of `atlassian`, and it REFUSED for thin evidence — which is the "
               "correct outcome for a domain that does not exist. Retire."),
    Entry("http://servicenow", "not_a_relationship",
          note="Malformed ref: a URL scheme leaked into the vendor key. Duplicate of `servicenow`. "
               "Retire, and note that ref normalisation let this through."),
    Entry("mondayservice", "not_a_relationship",
          note="Duplicate of `monday` created by a different search name. Retire."),
    Entry("archiveirm", "not_a_relationship",
          note="Typo of `archerirm`. Retire."),
    Entry("jira", "not_a_relationship",
          note="A PRODUCT, not a vendor — Jira is Atlassian, which is on the register separately. "
               "Scoring products alongside their vendors double-counts the same exposure. Also "
               "currently blocked on a sanctions match, which will never be adjudicable because "
               "there is no entity behind the ref."),
    Entry("claude", "not_a_relationship",
          note="A PRODUCT, not a vendor — Claude is Anthropic, which is on the register separately."),
    Entry("effectiverm", "not_a_relationship",
          note="THE BUYER'S OWN DOMAIN. A firm is not its own third party; scoring itself puts a "
               "self-assessment in the same table as its suppliers, where a reader has no way to "
               "tell them apart. Useful as an internal posture check — on a different page."),
    Entry("effectiveriskmanagement", "not_a_relationship",
          note="The buyer's own domain again, under a second ref. Same finding as `effectiverm`."),
)


def _corpus_entry(ref: str) -> Entry:
    """A seeded benchmarking vendor. No relationship, so nothing to declare — and this is a
    REFUSAL, not an omission. The seeded corpus exists so E11's cohorts have a population; giving
    those vendors a criticality would be inventing a commercial relationship to move a metric."""
    return Entry(ref, "corpus",
                 note="Scored by `seed_cohorts` to give E11's peer cohorts a population. There is "
                      "no commercial relationship, so there is no inherent exposure to declare.")


def _corpus_refs() -> frozenset[str]:
    """The seed list's refs, resolved the same way the seeder resolves them.

    Derived rather than hardcoded: a second hand-maintained copy of the seed list would drift, and
    the failure would be silent — a corpus vendor quietly counted as an undeclared relationship,
    which is precisely the denominator error this module exists to fix.
    """
    from .pipeline import resolve_vendor
    from .seed_cohorts import SEED_SETS

    return frozenset(
        resolve_vendor(name=sv.name, domain=sv.domain).ref
        for members in SEED_SETS.values() for sv in members
    )


# ═════════════════════════════════════════════════════════════════ validation


def _validate(entries: tuple[Entry, ...]) -> None:
    """Refuse a register that cannot be published as written. Runs at import, not at apply time.

    The two rules that matter:
      * A RELATIONSHIP MUST CARRY A DECLARATION, a basis, an author and a date. A relationship row
        with no exposure on it is the same 0.0% this file exists to fix, moved one layer up.
      * A NON-RELATIONSHIP MUST NOT CARRY ONE. Declaring an exposure against a typo or a seeded
        corpus vendor fabricates a relationship, and it would count toward the declaration rate
        indistinguishably from a real one.
    """
    seen: set[str] = set()
    for e in entries:
        if e.ref in seen:
            raise RegisterError(f"{e.ref}: listed twice — the inventory of record cannot be ambiguous")
        seen.add(e.ref)

        if e.declarable:
            if not e.declared:
                raise RegisterError(
                    f"{e.ref}: a relationship with neither criticality nor data access scope. "
                    f"Either declare one, or reclassify the row.")
            if len(e.basis) < 80:
                raise RegisterError(
                    f"{e.ref}: a declaration needs a written basis a relationship owner can argue "
                    f"with. {len(e.basis)} characters is a label, not a basis.")
            if not e.declared_by or not e.declared_on:
                raise RegisterError(f"{e.ref}: a declaration needs an author and a date")
        else:
            if e.declared or e.substitutability:
                raise RegisterError(
                    f"{e.ref}: classified `{e.classification}` but carries a declaration. There is "
                    f"no relationship here, so there is no exposure — declaring one would "
                    f"fabricate the relationship and count toward the declaration rate.")
            if not e.note:
                raise RegisterError(
                    f"{e.ref}: excluded from the declarable population with no reason given. An "
                    f"unexplained exclusion is how a denominator gets quietly trimmed.")


_STATIC: tuple[Entry, ...] = _RELATIONSHIPS + _NOT_RELATIONSHIPS
_validate(_STATIC)
_BY_REF: dict[str, Entry] = {e.ref: e for e in _STATIC}


# ═════════════════════════════════════════════════════════════════ reading the register


def entries() -> tuple[Entry, ...]:
    """Every hand-written row. Corpus rows are NOT included — they are derived from the seed list
    by `entry_for` / `classify`, so the two can never disagree."""
    return _STATIC


def relationships() -> tuple[Entry, ...]:
    return _RELATIONSHIPS


def entry_for(ref: str) -> Entry | None:
    """This ref's register row, deriving the corpus rows from the seed list. `None` means a vendor
    that is in the book and on nobody's inventory — which is a finding, not a default."""
    if ref in _BY_REF:
        return _BY_REF[ref]
    if ref in _corpus_refs():
        return _corpus_entry(ref)
    return None


def classify(ref: str) -> Classification | None:
    entry = entry_for(ref)
    return entry.classification if entry else None


def coverage(store: Any) -> dict[str, Any]:
    """The three populations, counted against what is actually in the book AND actually in the store.

    THIS IS THE CORRECTED DENOMINATOR. `declaration_rate` is declared relationships over
    relationships — not over every scored row — because a seeded benchmarking vendor has no
    exposure to declare and counting it as undeclared makes the programme look negligent about a
    question that does not apply to it.

    **`declared` MEANS THE STORE HAS IT, NOT THAT THE REGISTER CLAIMS IT.** This was the first thing
    this function got wrong: counting the register's own rows made it report 100% the moment the
    file was written and before a single declaration had been applied — a metric measuring its own
    input. What downstream reads is the profile and the attribute row, so that is what is counted,
    and `unapplied` names any row the register declares that the store has not received.

    `unregistered` is the number that should never be non-zero for long: a vendor in the book that
    nobody has classified as anything. It is reported separately rather than folded into
    `relationship`, because assuming an unknown row is a relationship and assuming it is not are
    both guesses, and only one of them is visible.
    """
    refs = sorted({s.vendor_ref for s in store.latest_scores_all()})
    # Two queries for the book rather than two per declarable entry. Same rows, same `.get`-returns
    # -None semantics as the per-vendor calls this replaced — an absent profile still reads as
    # undeclared, which is the distinction this whole function exists to keep.
    profiles = store.latest_profiles_all()
    attrs_all = store.latest_supplier_attributes_all()
    buckets: dict[str, list[str]] = {
        "relationship": [], "corpus": [], "not_a_relationship": [], "unregistered": [],
    }
    declared, confirmed, provisional, unapplied = [], [], [], []

    for ref in refs:
        entry = entry_for(ref)
        if entry is None:
            buckets["unregistered"].append(ref)
            continue
        buckets[entry.classification].append(ref)
        if not entry.declarable:
            continue

        profile = profiles.get(ref)
        attrs = attrs_all.get(ref) or {}
        in_store = bool((profile and profile.criticality) or attrs.get("data_access_scope"))
        if in_store:
            declared.append(ref)
            # Provisionality is a fact about the STORED declaration, for the same reason: the
            # register may have been confirmed since it was last applied.
            is_prov = bool(profile and getattr(profile, "inherent_provisional", False))
            (provisional if is_prov else confirmed).append(ref)
        elif entry.declared:
            unapplied.append(ref)

    n = len(buckets["relationship"])
    return {
        "in_book": len(refs),
        "relationships": n,
        "corpus": len(buckets["corpus"]),
        "not_a_relationship": len(buckets["not_a_relationship"]),
        "unregistered": buckets["unregistered"],
        "declared": len(declared),
        "confirmed": len(confirmed),
        "provisional": len(provisional),
        "undeclared": sorted(set(buckets["relationship"]) - set(declared)),
        "unapplied": sorted(unapplied),
        "declaration_rate": round(len(declared) / n, 3) if n else None,
        "confirmed_rate": round(len(confirmed) / n, 3) if n else None,
    }


# ═════════════════════════════════════════════════════════════════ writing it to the store


@dataclass
class Applied:
    ref: str
    wrote_profile: bool
    wrote_attributes: bool
    tier: str | None
    note: str = ""


def apply_entry(store: Any, entry: Entry, *, dry_run: bool = False) -> Applied:
    """Append one declaration. Two rows, because the two inputs live in two places by design.

    `criticality` and `substitutability` ride on the vendor profile; `data_access_scope` rides on
    the benchmarking attribute row, where EB deliberately kept it out of the cohort key. Both stores
    are append-only, so this SUPERSEDES rather than edits — the profile the score was read against
    stays exactly as it was, and the declaration is a new fact with its own timestamp.

    NOTHING HERE TOUCHES A POSTURE. The score row is not read, not rewritten and not invalidated.
    That is the E10b invariant: inherent exposure and observed posture run on different clocks, and
    a contract change must never look like a security event.
    """
    from .benchmarking.models import SupplierFirmographics
    from .benchmarking.service import firmographics_of, record_attributes
    from .models import VendorProfile, utcnow
    from .residual_risk import inherent_tier

    if not entry.declarable:
        return Applied(entry.ref, False, False, None, "not a relationship — nothing to declare")

    profile = store.latest_profile(entry.ref)
    if profile is None:
        # A blocked vendor can reach the store with a score and no profile. The exposure is still
        # declarable — it is a fact about the RELATIONSHIP, and it does not need the vendor to have
        # been successfully observed. A minimal profile carries the declaration and nothing else.
        profile = VendorProfile(vendor_ref=entry.ref)
        note = "no prior profile — declaration written onto a minimal one"
    else:
        profile = profile.model_copy(deep=True)
        note = ""

    profile.criticality = entry.criticality
    profile.substitutability = entry.substitutability
    profile.inherent_provisional = not entry.confirmed
    profile.computed_at = utcnow()

    # COHORT INPUTS: MERGE, NEVER INHERIT AN EMPTINESS.
    #
    # This used to fall back to the profile ONLY when no attribute row existed at all, and take the
    # stored row wholesale otherwise. Both halves failed together on the common case: a relationship
    # declared BEFORE the vendor was ever scored has no profile, so the block above fabricates a
    # minimal one, every firmographic reads `None`, and an empty cohort row is written. From then on
    # `firmographics_of` returns that empty row, so re-running the register after the vendor IS
    # scored re-writes the same emptiness — the blank is sticky and the profile is never consulted
    # again. 19 of 23 suppliers in the book had no sector for exactly this reason, which left the
    # v2 peer groups too thin to place anybody.
    #
    # So: take each field from the stored row where it has one, and from the profile otherwise.
    # Neither source is authoritative on its own — the stored row may carry a client correction or a
    # delivery model no collector can see, and the profile carries firmographics the client never
    # supplies.
    def _profile_value(field: Any) -> Any:
        return field.value if field is not None else None

    stored = firmographics_of(store, entry.ref)
    from_profile = {
        "sector": _profile_value(profile.sector),
        "employees": _profile_value(profile.employees),
        "revenue": _profile_value(profile.revenue),
        "revenue_currency": _profile_value(profile.revenue_currency),
    }
    if stored is None:
        firmographics = SupplierFirmographics(supplier_ref=entry.ref, **from_profile)
    else:
        filled = {k: v for k, v in from_profile.items() if getattr(stored, k, None) is None}
        firmographics = stored.model_copy(update=filled)

    # The one field this path is authoritative for: it is the declaration being applied.
    firmographics = firmographics.model_copy(
        update={"data_access_scope": entry.data_access_scope})

    tier = inherent_tier(entry.criticality, entry.data_access_scope).tier
    if dry_run:
        return Applied(entry.ref, False, False, tier, note or "dry run")

    store.put_profile(profile)
    record_attributes(store, firmographics, source="client_supplied")
    return Applied(entry.ref, True, True, tier, note)


def apply_all(store: Any, *, dry_run: bool = False) -> list[Applied]:
    return [apply_entry(store, e, dry_run=dry_run) for e in _RELATIONSHIPS]


# ═════════════════════════════════════════════════════════════════ CLI


def main() -> None:
    parser = argparse.ArgumentParser(
        description="The inventory of record: classify the book, declare inherent exposure.")
    parser.add_argument("--status", action="store_true",
                        help="the three populations and the declaration rate, writing nothing")
    parser.add_argument("--apply", action="store_true", help="append the declarations to the store")
    parser.add_argument("--dry-run", action="store_true",
                        help="what --apply would write, writing nothing")
    args = parser.parse_args()
    setup_logging()

    from .storage import get_store

    store = get_store()

    if args.status or not (args.apply or args.dry_run):
        cov = coverage(store)
        print(f"\n{cov['in_book']} vendors in the book:")
        print(f"  {cov['relationships']:>4}  relationships      — an exposure to declare")
        print(f"  {cov['corpus']:>4}  corpus             — seeded for E11 cohorts, no relationship")
        print(f"  {cov['not_a_relationship']:>4}  inventory defects  — typos, products, own domains")
        if cov["unregistered"]:
            print(f"  {len(cov['unregistered']):>4}  UNREGISTERED       — on nobody's inventory: "
                  f"{', '.join(cov['unregistered'])}")
        rate = cov["declaration_rate"]
        print(f"\ndeclaration rate  {rate:.1%} ({cov['declared']} of {cov['relationships']} "
              f"relationships)" if rate is not None else "\nno relationships in the book")
        print(f"  confirmed       {cov['confirmed']}")
        print(f"  PROVISIONAL     {cov['provisional']}  — declared, not yet confirmed by the "
              f"relationship owner")
        if cov["unapplied"]:
            print(f"  UNAPPLIED       {len(cov['unapplied'])}  — on the register, never written to "
                  f"the store. Run --apply: {', '.join(cov['unapplied'])}")
        if cov["undeclared"]:
            print(f"  undeclared      {', '.join(cov['undeclared'])}")
        return

    results = apply_all(store, dry_run=args.dry_run)
    verb = "would declare" if args.dry_run else "declared"
    for r in results:
        suffix = f"  ({r.note})" if r.note else ""
        print(f"  {verb} {r.ref:<24} inherent tier {r.tier or '-':<9}{suffix}")
    print(f"\n{len(results)} relationships {verb}. Every one is PROVISIONAL until the relationship "
          f"owner confirms it.")


if __name__ == "__main__":
    main()
