"""Entity-resolution confidence — "is the thing we scored the company you meant?"

The ambiguity gate (`scoring.yaml gates.entity_ambiguous`, block below 0.5) is one of the model's
three differentiators. It was, until now, **unfed**: `resolution_confidence` was an API input
defaulting to 1.0, so the gate could only fire if a caller volunteered a low number. A safety
control that only triggers when asked is not a control.

This module derives it from what the registries ACTUALLY returned. It runs AFTER collection —
which is the only point where the evidence exists — and before scoring, so the engine's gate reads
a number that means something.

WHAT IT WILL AND WON'T BLOCK, stated plainly, because the failure modes are asymmetric:

  * It blocks when we cannot say **what we are assessing** — the domain was guessed from a name
    rather than supplied. Scoring a guessed domain is the one shortcut this system refuses.
  * It does NOT block on **obscurity**. A small vendor absent from GLEIF and Wikidata is not
    ambiguous, it is merely unregistered — and punishing a vendor for being small is exactly the
    "scores well/badly by being invisible" failure the methodology forbids (§5.4). Absence lowers
    confidence toward the unverified band; it does not gate.
  * It does NOT block on **register ambiguity** either, and that took measuring to get right. Four
    separate legal entities are registered as "Snowflake"; GLEIF alone cannot say which owns
    snowflake.com. An earlier draft of this module blocked on that and refused a benchmark vendor.
    The error was conflating two different questions: *which legal entity is this?* (uncertain) and
    *what did we assess?* (certain — the domain the caller supplied). Register ambiguity makes the
    **Business Stability** finding unreliable, so it lowers confidence and is named in the basis;
    it does not invalidate the TLS handshake or the breach search.

An honest consequence: with a supplied domain the gate is **rare by design**. That is the correct
behaviour, not a defect — the identity question is settled by the caller naming the domain, and the
guard that carries the weight in v1 is the pipeline's refusal to infer a domain from a name at all.

Every score carries the basis as text, so a blocked record says WHY in the adjudication queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import CollectorResult, Vendor

# Confidence anchors. Deliberately coarse and few — the same reasoning as the four severity
# penalties: a number a client can challenge beats a curve nobody can defend.
DOMAIN_ONLY = 0.85          # caller named a domain, no name to mis-map — nothing to confuse
DOMAIN_VERIFIED = 0.97      # Wikidata P856 == our domain: a hard identifier tied the two together
REGISTER_MATCH = 0.90       # GLEIF resolved a single strong legal-name match
UNVERIFIED = 0.70           # no register covers this vendor — unverified, but NOT ambiguous
AMBIGUOUS_REGISTER = 0.65   # several companies share this legal name — WHICH entity is uncertain,
                            # WHAT we assessed is not. Scored, flagged, below the Medium band.
WEAK_ATTRIBUTION = 0.65     # a register answered but the winning name barely resembles the query
INFERRED_DOMAIN = 0.40      # the domain was GUESSED from a name — the one case that must block,
                            # because then we genuinely do not know what we assessed

_CORROBORATION_BONUS = 0.02   # RDAP confirming the domain is really registered


@dataclass
class Resolution:
    """The computed confidence plus the plain-English basis for it."""

    confidence: float
    basis: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return "; ".join(self.basis) if self.basis else "no resolution evidence"


def _by_source(results: list[CollectorResult]) -> dict[str, CollectorResult]:
    return {r.source: r for r in results}


def assess(vendor: Vendor, results: list[CollectorResult]) -> Resolution:
    """Derive entity-resolution confidence from collected evidence.

    Returns the confidence the scoring gate reads, plus why — never a bare number.
    """
    by = _by_source(results)
    basis: list[str] = []

    # THE blocking case: we assessed a domain nobody confirmed. Everything else below is a
    # question about which legal entity sits behind a domain we were explicitly told to assess.
    if vendor.domain_source == "inferred":
        basis.append(
            f"the domain {vendor.domain} was guessed from the name '{vendor.name}' and never "
            "confirmed, so we cannot say this is the right company"
        )
        return Resolution(INFERRED_DOMAIN, basis)

    # No name to mis-map: the caller pointed at a domain and we assessed that domain.
    if not vendor.name:
        basis.append(f"domain {vendor.domain} assessed as supplied; no company name to resolve")
        return Resolution(DOMAIN_ONLY, basis)

    wikidata = by.get("wikidata")
    gleif = by.get("gleif")

    # --- strongest evidence: a hard identifier ties the name and the domain together ---
    # The Wikidata collector emits ONLY when a candidate's official-website (P856) registrable
    # domain equals the vendor's, so any finding at all is a domain-verified corroboration.
    if wikidata is not None and wikidata.status == "ok" and wikidata.findings:
        basis.append("Wikidata verified this company's official website matches the domain assessed")
        confidence = DOMAIN_VERIFIED
        if gleif is not None and gleif.status == "ok" and gleif.findings:
            basis.append("GLEIF independently resolved the legal entity")
        return Resolution(_nudge(confidence, by, basis), basis)

    # --- register match on name alone: good, but not domain-anchored ---
    if gleif is not None and gleif.status == "ok" and gleif.findings:
        raw = gleif.raw or {}
        strong = int(raw.get("strong_matches", 0) or 0)
        # ABSENT metadata is not BAD metadata. A record written before attribution quality was
        # recorded cannot be judged on it, and reading "missing" as "poor match" would block
        # vendors for the collector's history rather than for anything about them.
        name_match = raw.get("name_match")
        exact = raw.get("exact_matches")

        # EXACT ties are the ambiguity that matters — several companies registered under the same
        # legal name. Merely *strong* matches are not: "Snowflake" strong-matches 15 records
        # (Snowflake Capital, Snowflake Holdings...) while exactly one IS Snowflake, and blocking
        # on that count would refuse a household name for having a common word in it.
        if exact is not None and int(exact) > 1:
            basis.append(
                f"{exact} different companies are registered under the name '{vendor.name}', so "
                "the legal-entity record attached to this assessment may belong to another of "
                "them — read the Business Stability finding with that in mind"
            )
            return Resolution(AMBIGUOUS_REGISTER, basis)

        if name_match is not None and int(name_match) <= 1:
            basis.append(
                f"the legal entity found does not closely match the name given ('{vendor.name}')"
            )
            return Resolution(WEAK_ATTRIBUTION, basis)

        # No exact match at all, several partials competing.
        if exact is not None and int(exact) == 0 and strong > 1:
            basis.append(
                f"no company is registered under exactly '{vendor.name}' and {strong} partially "
                "matching entities compete, so the legal-entity record may not be this company's"
            )
            return Resolution(AMBIGUOUS_REGISTER, basis)

        basis.append("a single company is registered under this exact name")
        return Resolution(_nudge(REGISTER_MATCH, by, basis), basis)

    # --- no register covers this vendor: unverified, but not ambiguous ---
    basis.append(
        "no legal-entity register covers this company, so the name could not be independently "
        "tied to the domain — unverified, not ambiguous"
    )
    return Resolution(_nudge(UNVERIFIED, by, basis), basis)


def _nudge(confidence: float, by: dict[str, CollectorResult], basis: list[str]) -> float:
    """A small lift where the domain itself is confirmed registered (RDAP). Never enough to
    rescue an ambiguous record — corroborating that a domain exists says nothing about WHOSE."""
    rdap = by.get("rdap")
    if rdap is not None and rdap.status == "ok" and rdap.findings:
        basis.append("the domain is confirmed registered in the public registry")
        return min(0.99, confidence + _CORROBORATION_BONUS)
    return confidence
