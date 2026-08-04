"""Industry and size taxonomy — the two dimensions that decide who a vendor may be compared with.

WHY THIS IS A MODULE AND NOT A DICT IN THE COLLECTOR. Sector and size are the load-bearing inputs
to the peer cohort (`benchmark.py`), and a cohort is only as defensible as the classification
behind it. Keeping the mapping in one reviewable place means a client can argue with "we classify
Atlassian as technology, not professional services" by reading a table, not by reading Python.

THREE SOURCES, ONE VOCABULARY. Industry arrives as an ANZSIC division (ABN Lookup), a SIC code
(Companies House) or a free-text Wikidata label ("enterprise software", "cloud computing"). All
three normalise to the same ~12 working sectors so a cohort means the same thing regardless of
which register answered.

WHAT THIS DELIBERATELY DOES NOT DO. It never guesses. An industry we cannot map returns None, the
cohort is not formed, and the vendor gets an absolute grade with NO peer percentile — which is the
honest outcome. A guessed sector produces a confident comparison against the wrong population,
which is worse than no comparison at all.
"""

from __future__ import annotations

import re

# The working sectors. Deliberately few: a taxonomy with 200 leaves never accumulates 8 vendors
# in any one of them, so the cohort gate never opens and benchmarking silently never works.
SECTORS: dict[str, str] = {
    "financial_services": "Financial Services",
    "healthcare": "Healthcare & Life Sciences",
    "technology": "Technology & Software",
    "telecommunications": "Telecommunications",
    "government": "Government & Public Sector",
    "education": "Education & Research",
    "retail": "Retail & Consumer",
    "manufacturing": "Manufacturing & Industrial",
    "food_agriculture": "Food & Agriculture",
    "professional_services": "Professional & Business Services",
    "transport_logistics": "Transport & Logistics",
    "energy_utilities": "Energy & Utilities",
}

# --- ANZSIC (AU, from ABN Lookup) -------------------------------------------------------------
# Keyed by ANZSIC division letter. Division names are the ABS's; the mapping to our sector is ours.
ANZSIC_DIVISIONS: dict[str, str] = {
    "A": "food_agriculture",        # Agriculture, Forestry and Fishing
    "B": "energy_utilities",        # Mining
    "C": "manufacturing",           # Manufacturing
    "D": "energy_utilities",        # Electricity, Gas, Water and Waste Services
    "E": "manufacturing",           # Construction
    "F": "retail",                  # Wholesale Trade
    "G": "retail",                  # Retail Trade
    "H": "retail",                  # Accommodation and Food Services
    "I": "transport_logistics",     # Transport, Postal and Warehousing
    "J": "telecommunications",      # Information Media and Telecommunications
    "K": "financial_services",      # Financial and Insurance Services
    "L": "professional_services",   # Rental, Hiring and Real Estate Services
    "M": "professional_services",   # Professional, Scientific and Technical Services
    "N": "professional_services",   # Administrative and Support Services
    "O": "government",              # Public Administration and Safety
    "P": "education",               # Education and Training
    "Q": "healthcare",              # Health Care and Social Assistance
    "R": "retail",                  # Arts and Recreation Services
    "S": "professional_services",   # Other Services
}

# ANZSIC division M covers "Professional, Scientific and Technical Services", which is where AU
# software companies are usually registered — the code alone would file every AU SaaS vendor as
# professional services. The 4-digit class disambiguates, so where we have one, it wins.
ANZSIC_CLASSES: dict[str, str] = {
    "5910": "telecommunications",  # Internet Service Providers / Web Search Portals
    "5921": "telecommunications",  # Telecommunications Services
    "7000": "technology",          # Computer System Design and Related Services
    "5420": "technology",          # Software Publishing
    "5910 ": "telecommunications",
}

# --- SIC (UK, from Companies House) -----------------------------------------------------------
# Keyed by the 2-digit division of the 5-digit SIC code.
SIC_DIVISIONS: dict[str, str] = {
    "01": "food_agriculture", "02": "food_agriculture", "03": "food_agriculture",
    "05": "energy_utilities", "06": "energy_utilities", "07": "energy_utilities",
    "08": "energy_utilities", "09": "energy_utilities",
    "10": "food_agriculture", "11": "food_agriculture", "12": "manufacturing",
    "13": "manufacturing", "14": "manufacturing", "15": "manufacturing", "16": "manufacturing",
    "17": "manufacturing", "18": "manufacturing", "19": "energy_utilities",
    "20": "manufacturing", "21": "healthcare", "22": "manufacturing", "23": "manufacturing",
    "24": "manufacturing", "25": "manufacturing", "26": "manufacturing", "27": "manufacturing",
    "28": "manufacturing", "29": "manufacturing", "30": "manufacturing", "31": "manufacturing",
    "32": "manufacturing", "33": "manufacturing",
    "35": "energy_utilities", "36": "energy_utilities", "37": "energy_utilities",
    "38": "energy_utilities", "39": "energy_utilities",
    "41": "manufacturing", "42": "manufacturing", "43": "manufacturing",
    "45": "retail", "46": "retail", "47": "retail",
    "49": "transport_logistics", "50": "transport_logistics", "51": "transport_logistics",
    "52": "transport_logistics", "53": "transport_logistics",
    "55": "retail", "56": "retail",
    "58": "technology", "59": "telecommunications", "60": "telecommunications",
    "61": "telecommunications", "62": "technology", "63": "technology",
    "64": "financial_services", "65": "financial_services", "66": "financial_services",
    "68": "professional_services",
    "69": "professional_services", "70": "professional_services", "71": "professional_services",
    "72": "education", "73": "professional_services", "74": "professional_services",
    "75": "healthcare", "77": "professional_services", "78": "professional_services",
    "79": "professional_services", "80": "professional_services", "81": "professional_services",
    "82": "professional_services",
    "84": "government", "85": "education",
    "86": "healthcare", "87": "healthcare", "88": "healthcare",
    "90": "retail", "91": "education", "92": "retail", "93": "retail",
    "94": "professional_services", "95": "professional_services", "96": "professional_services",
}

# --- Free-text labels (Wikidata P452 and friends) ----------------------------------------------
# Ordered: the FIRST match wins, so the specific patterns must precede the general ones. "software
# for banks" is technology, not financial services — the vendor's own industry is what we want,
# not its customers'.
# Entries are STEMS, matched with a trailing `\w*` so "bank" catches "banking", "manufactur"
# catches "manufacturing", and "telecom" catches "telecommunications". Wikidata labels are
# free text and arrive in every inflection; anchoring on whole words would miss most of them.
_LABEL_PATTERNS: list[tuple[str, str]] = [
    # Accounting/banking SOFTWARE is technology — a vendor's own industry, not its customers'.
    # This sits above financial_services deliberately: MYOB sells to accountants and belongs in
    # the software peer group, not the bank one.
    (r"\b(software|saas|cloud comput|computer|information technolog|"
     r"internet|web servic|data warehous|data analytic|cyber ?security|"
     r"artificial intelligence|semiconductor|electronic design)", "technology"),
    (r"\b(telecom|telephon|mobile network|broadband|isp\b|internet service provider)",
     "telecommunications"),
    (r"\b(bank|insur|financ|fintech|payment|superannuat|asset management|"
     r"investment|credit union|securities)", "financial_services"),
    (r"\b(health ?care|hospital|pharmaceutic|biotech|medical|clinic|"
     r"life scien|diagnostic|aged care)", "healthcare"),
    (r"\b(government|public administration|defence|defense|municipal)", "government"),
    (r"\b(universit|education|school|academic|research institut|training)", "education"),
    (r"\b(retail|e-?commerce|supermarket|consumer goods|hospitality|restaurant|"
     r"grocer|apparel|fashion)", "retail"),
    (r"\b(agricultur|farming|food manufactur|food process|food product|beverage|"
     r"dairy|winer|brewer|fisher|forestr)", "food_agriculture"),
    (r"\b(manufactur|industrial|automotive|aerospace|construction|engineering|"
     r"chemical|steel|mining equipment)", "manufacturing"),
    (r"\b(logistic|shipping|freight|airline|transport|courier|rail\b|port operat)",
     "transport_logistics"),
    (r"\b(energy|electric|utilit|oil\b|gas\b|petroleum|renewable|solar|mining|coal)",
     "energy_utilities"),
    (r"\b(consult|legal servic|law firm|advertis|marketing|recruit|"
     r"professional servic|audit|accountanc|architect|real estate)", "professional_services"),
]
_LABEL_RE = [(re.compile(p, re.I), sector) for p, sector in _LABEL_PATTERNS]

# --- Region (regulatory regime, not geography) -------------------------------------------------
# The dimension is which rulebook a vendor answers to, which is why the UK sits with the EU rather
# than with the rest of Europe's neighbours, and why NZ sits with Australia.
_REGIONS: dict[str, str] = {
    **dict.fromkeys(("AU", "NZ"), "anz"),
    **dict.fromkeys(("US", "CA", "MX"), "north_america"),
    **dict.fromkeys((
        "GB", "UK", "IE", "DE", "FR", "NL", "BE", "LU", "ES", "PT", "IT", "AT", "CH",
        "SE", "NO", "DK", "FI", "IS", "PL", "CZ", "SK", "HU", "RO", "BG", "GR", "HR",
        "SI", "EE", "LV", "LT", "CY", "MT",
    ), "uk_eu"),
    **dict.fromkeys((
        "SG", "JP", "KR", "CN", "HK", "TW", "IN", "ID", "MY", "TH", "VN", "PH", "PK", "BD",
    ), "apac"),
}


def sector_from_anzsic(code: str | None) -> str | None:
    """ANZSIC division letter or 4-digit class -> working sector. The class wins when we have one."""
    if not code:
        return None
    code = code.strip().upper()
    if code[:4].isdigit() and code[:4] in ANZSIC_CLASSES:
        return ANZSIC_CLASSES[code[:4]]
    if code[:1].isalpha():
        return ANZSIC_DIVISIONS.get(code[:1])
    return None


def sector_from_sic(code: str | None) -> str | None:
    """UK SIC 2007 code -> working sector, via its 2-digit division."""
    if not code:
        return None
    digits = re.sub(r"\D", "", code)
    return SIC_DIVISIONS.get(digits[:2]) if len(digits) >= 2 else None


def sector_from_label(label: str | None) -> str | None:
    """Free-text industry label -> working sector, or None when nothing matches confidently.

    None is a first-class answer here. An unmapped label means no cohort, which means an absolute
    grade and no percentile — the honest outcome, and far better than filing a vendor into a
    population it does not belong to.
    """
    if not label:
        return None
    for pattern, sector in _LABEL_RE:
        if pattern.search(label):
            return sector
    return None


def region_for(country: str | None) -> str:
    """ISO-2 country -> regulatory region. Unknown countries fall to 'other', never to a guess."""
    if not country:
        return "other"
    return _REGIONS.get(country.strip().upper(), "other")


def sector_label(sector: str | None) -> str | None:
    return SECTORS.get(sector) if sector else None
