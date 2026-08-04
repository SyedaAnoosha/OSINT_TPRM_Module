"""The controlled sector vocabulary — one list, shared by cohorts and compliance obligations.

WHY THIS FILE EXISTS. Two subsystems key off "sector" and, until this module, they used different
words for the same industry. `benchmarks.yaml` groups `financial_services` under
`regulated_services`; `scoring.yaml` claimed APRA applies to `[financial_services, banking,
insurance, superannuation]`. Three of those four are not sectors this system knows. A client
answering "banking" got the APRA framework and no peer cohort; a client answering
`financial_services` got both. Same vendor, same obligation, two different reports depending on
which word the intake form happened to capture.

That is worse than it sounds, because the failure is SILENT IN THE SAFE DIRECTION for cohorts (a
cohort simply refuses, and refusal is the designed behaviour) and SILENT IN THE UNSAFE DIRECTION
for compliance (no gaps found, which a reader takes as "no obligations breached").

THE VOCABULARY IS BENCHMARKING'S, NOT A SECOND ONE. `benchmarking.sector_groups` is already a
load-validated partition — every sector appears in exactly one group, enforced because
`sector_group_of` would otherwise be order-dependent. That makes it the only list in the codebase
with a uniqueness guarantee already attached, so it is the list, and this module reads it rather
than restating it. E9c's open design question 2 said "reuse it rather than inventing a second";
this is that, honoured literally.

ALIASES ARE INPUT HANDLING, NOT VOCABULARY. `banking` and `superannuation` are real words a client
will type, and rejecting them outright moves the failure to the intake form where nobody is
watching. They resolve to `financial_services` — the canonical term — and the alias table is
deliberately small and explicit. An alias is never a new sector: it can only point at one that
already exists, and `_validate_aliases` refuses one that does not.
"""

from __future__ import annotations

from functools import lru_cache

# Words clients actually use, mapped to the canonical sector they mean. Every VALUE here must be a
# member of the benchmarking partition; that is asserted at load, so a typo fails loudly rather
# than silently creating an eighteenth sector nobody can be compared against.
#
# Kept intentionally short. A long alias table is a sign the canonical list is wrong, not a sign the
# aliases are working.
_ALIASES: dict[str, str] = {
    # financial services
    "banking": "financial_services",
    "bank": "financial_services",
    "superannuation": "financial_services",
    "super": "financial_services",
    "fintech": "financial_services",
    "finance": "financial_services",
    "financial services": "financial_services",
    "payments": "financial_services",
    # health
    "health": "healthcare",
    "medical": "healthcare",
    "aged_care": "healthcare",
    "aged care": "healthcare",
    "hospital": "healthcare",
    "pharma": "healthcare",
    # technology
    "tech": "technology",
    "saas": "technology",
    "software": "technology",
    "it": "technology",
    "telco": "telecommunications",
    "telecoms": "telecommunications",
    # public sector
    "govt": "government",
    "gov": "government",
    "public_sector": "government",
    "public sector": "government",
    "defence": "government",
    # other common intake spellings
    "energy": "utilities",
    "water": "utilities",
    "power": "utilities",
    "transport": "logistics",
    "shipping": "logistics",
    "freight": "logistics",
    "consulting": "professional_services",
    "legal": "professional_services",
    "accounting": "professional_services",
}


class SectorVocabularyError(ValueError):
    """Raised at load time when an alias points at a sector that does not exist."""


@lru_cache
def known_sectors() -> frozenset[str]:
    """Every canonical sector, read from the benchmarking partition.

    Imported lazily inside the function on purpose: `scoring_config` validates against this list,
    and a module-level import would make a broken `benchmarks.yaml` stop the scoring model from
    loading. The coupling is one-directional and read-only — benchmarking has no write path into a
    score, and this does not create one.
    """
    from .benchmarking.config import get_benchmarking_config

    cfg = get_benchmarking_config()
    sectors = {s for members in cfg.sector_groups().values() for s in members}
    unknown = {v for v in _ALIASES.values() if v not in sectors}
    if unknown:
        raise SectorVocabularyError(
            f"sector aliases point at sectors that are not in the benchmarking partition: "
            f"{sorted(unknown)}. An alias may only redirect to a sector that already exists — "
            f"otherwise it silently creates a peer group of one."
        )
    return frozenset(sectors)


def canonical_sector(raw: str | None) -> str | None:
    """The canonical sector for whatever the client typed, or None if we do not recognise it.

    None is a real answer and callers must treat it as one. An unrecognised sector means the
    obligations are UNKNOWN, not absent — `compliance_gaps` says so in a caveat rather than
    returning a clean report, because "we do not model your industry" and "your vendor breaches
    nothing" look identical on a page and only one of them is true.
    """
    if not raw:
        return None
    key = raw.strip().lower().replace("-", "_")
    if key in known_sectors():
        return key
    spaced = key.replace("_", " ")
    resolved = _ALIASES.get(key) or _ALIASES.get(spaced)
    return resolved if resolved in known_sectors() else None


def sector_aliases() -> dict[str, str]:
    """The alias table, for disclosure. Published so a client can see how their word was read."""
    return dict(_ALIASES)
