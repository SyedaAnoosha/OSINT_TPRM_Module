"""Disclosures and attribution — what every published record must carry, in one place.

WHY THIS IS A MODULE AND NOT UI COPY. Two of these are legal obligations, not editorial choices:
the NVD notice must appear **verbatim**, and the HIBP licence requires attribution wherever its
data appears (methodology §10 — *"these are UI requirements, not footnotes to add later"*). They
were previously written into the scorecard as JSX and then commented out, which is exactly how an
obligation quietly stops being met. Defining them here means the card and the evidence pack read
from the same source, and a missing one is a test failure rather than a rendering accident.

THE LIMITS BELOW ARE NOT DISCLAIMERS. A reader who believes a clean score means "safe", or that a
strong perimeter means a strong posture, has misread the product. Saying so is part of publishing
the number honestly — and under Finding A it is part of what makes the number defensible.
"""

from __future__ import annotations

from typing import Any

# Mandatory, verbatim. The NVD terms require this exact sentence wherever their data is used.
NVD_NOTICE = "This product uses the NVD API but is not endorsed or certified by the NVD."

ATTRIBUTION: list[dict[str, str]] = [
    {"source": "Have I Been Pwned", "notice": "Breach data via Have I Been Pwned, CC BY 4.0.",
     "url": "https://haveibeenpwned.com"},
    {"source": "NVD", "notice": NVD_NOTICE, "url": "https://nvd.nist.gov"},
    {"source": "GDELT", "notice": "Adverse-media candidates via the GDELT Project.",
     "url": "https://gdeltproject.org"},
    {"source": "GLEIF", "notice": "Legal-entity standing from the GLEIF LEI register (CC0).",
     "url": "https://gleif.org"},
    {"source": "Wikidata", "notice": "Firmographic context from Wikidata (CC0).",
     "url": "https://wikidata.org"},
    {"source": "ABN Lookup", "notice": "Australian entity status sourced from ABN Lookup. "
                                       "Not endorsed by the Commonwealth.",
     "url": "https://abr.business.gov.au"},
]

# The structural limits. These do not close with more sources, and a record that omits them
# overstates what it is.
LIMITS: list[dict[str, str]] = [
    {
        "title": "Coverage tracks size, not risk",
        "detail": "Larger vendors publish more, so they surface more signal. Richer coverage is "
                  "partly an artefact of size rather than proof of better security. Read the "
                  "confidence axis, never the score alone.",
    },
    {
        "title": "Perimeter, not posture",
        "detail": "This measures what a stranger can see from outside. A strong external reading "
                  "is fully compatible with a weak internal one, and cannot see the compensating "
                  "controls a vendor may run behind it.",
    },
    {
        "title": "Absence of evidence is not evidence of absence",
        "detail": "No breach record, no adverse media and no filing is the default state of a "
                  "clean small vendor AND of a badly-run obscure one. We cannot distinguish them; "
                  "we report low confidence honestly instead of guessing.",
    },
    {
        "title": "Not a questionnaire replacement",
        "detail": "Roughly ten of twenty-seven standard due-diligence criteria — access controls, "
                  "security monitoring, data handling, insurance, change management, contract "
                  "terms — are invisible to any lawful external observer. This evidences the "
                  "fraction that is observable and flags contradictions with what a vendor claims.",
    },
]

# Coverage gaps that are true of every record until the underlying source clears.
NOT_ASSESSED: list[dict[str, str]] = [
    {"item": "Australian sanctions (DFAT)",
     "why": "Licence terms unresolved — the US ITA Consolidated Screening List IS screened, "
            "Australian coverage is a stated gap."},
    {"item": "Supply Chain & Dependency",
     "why": "Designed and held — the fourth-party re-feed from DNS/CT/trust is not yet built."},
    {"item": "Data Privacy & Leakage",
     "why": "No lawful free collector (the HIBP domain endpoint is paid)."},
    {"item": "Geopolitical & FOCI",
     "why": "Corporate-registry terms unresolved; a ~mid-2028 SOCI deadline applies to buyers."},
    {"item": "ESG & Ethical",
     "why": "AU Modern Slavery Register licence unresolved."},
    {"item": "Emerging Tech & AI",
     "why": "No lawfully observable external source."},
    {"item": "Open ports and exposed services",
     "why": "No active scanning is performed — a deliberate Terms-of-Service and lawful-access "
            "boundary, not an oversight. Estate visibility needs a licensed provider."},
]


def disclosure_block() -> dict[str, Any]:
    """The full disclosure set, for the scorecard and the evidence pack alike."""
    return {"limits": LIMITS, "not_assessed": NOT_ASSESSED, "attribution": ATTRIBUTION}
