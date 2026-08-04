"""Wikidata collector — a SECOND, independent register that corroborates GLEIF (lever 2).

WHY a second source. Confidence is meant to reward corroboration: two independent public
registers agreeing that an entity is live is stronger evidence than one. GLEIF (authoritative
LEI register) is source #1 for legal-entity standing; Wikidata is source #2. When both land on
the same subcategory and agree, the engine combines their reliabilities (noisy-OR, §5.4.3), so
a corroborated "active/in-good-standing" reads at higher confidence than GLEIF alone.

Legality (source_assessment.md §13). Wikidata structured data is **CC0 / public domain** — no
attribution, no commercial or automated-access restriction. Wikimedia's one hard condition is a
descriptive, contact-bearing User-Agent (their robot policy 403s generic/library UAs); the
shared client already sends `settings.user_agent`, which carries the contact.

ENTITY RESOLUTION is by DOMAIN, not name — the fix for GLEIF's blind spot. A bare name search is
noisy (searching "Xero" returns a film; "Cochlear" returns the *implant*, not the company). So we
search by name, then keep ONLY a candidate whose official-website (P856) registrable domain
matches the vendor's domain. No domain match -> we emit NOTHING (status "empty"): corroborating
the wrong entity is worse than not corroborating at all. This keeps every emitted finding tied to
the vendor by a hard identifier.

WHAT it reads — entity EXISTENCE + standing only (§4.2: no natural-person data):
  * P576 (dissolved/abolished date) present -> the entity has been wound up: real distress.
  * domain-verified, no P576 -> exists and is live (benign, POSITIVE observation).
Financials, litigation and ownership stay HELD, exactly as for GLEIF — Wikidata is corroboration
of standing, not a new category.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from .. import maturity
from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_SEARCH = "https://www.wikidata.org/w/api.php"
_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
_CAT = "business_financial_stability"
_SUB = "legal_entity_status"
_CANDIDATES = 7      # how many name hits to inspect for a domain match
_P_WEBSITE = "P856"  # official website
_P_DISSOLVED = "P576"  # dissolved, abolished or demolished date
_P_INCEPTION = "P571"  # legal inception / founded date
_HOST = re.compile(r"https?://([^/]+)", re.I)
_WWW = re.compile(r"^www\.", re.I)


class WikidataCollector(Collector):
    source = "wikidata"
    reliability = 0.7  # community-edited, but every emission is domain-verified (§13)
    timeout_s = 25.0
    http_attempts = 2  # public API, occasional 429 — one backoff clears it (lever 1)
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        if not vendor.domain:
            # Resolution here is domain-anchored; without a domain we cannot verify the entity
            # and will not guess. Costs confidence (empty), never risk.
            return self.result(vendor, "empty", notes="no domain — cannot domain-verify a Wikidata entity")
        query = vendor.name or vendor.ref
        target = _registrable(vendor.domain)

        hits = await self._search(ctx, query)
        if hits is None:
            return self.result(vendor, "error", notes="Wikidata search unavailable")

        matched: dict[str, Any] | None = None
        inspected = 0
        for h in hits[:_CANDIDATES]:
            qid = h.get("id")
            if not qid:
                continue
            ent = await self._entity(ctx, qid)
            if ent is None:
                continue
            inspected += 1
            sites = _claim_values(ent, _P_WEBSITE)
            if any(_registrable(_host(s)) == target for s in sites if isinstance(s, str)):
                matched = {"qid": qid, "label": h.get("label"), "sites": sites,
                           "dissolved": bool(_claim_values(ent, _P_DISSOLVED))}
                break

        if matched is None:
            # No candidate's official website matched the vendor domain — no verifiable entity.
            return self.result(
                vendor, "empty",
                raw={"query": query, "target_domain": target, "candidates_inspected": inspected},
                notes="no domain-verified Wikidata entity (no corroboration rather than a wrong match)",
            )

        band = "entity_dissolved" if matched["dissolved"] else "entity_active_confirmed"
        raw: dict[str, Any] = {
            "query": query, "target_domain": target, "candidates_inspected": inspected,
            "qid": matched["qid"], "label": matched["label"],
            "official_website": matched["sites"], "dissolved": matched["dissolved"],
        }
        findings: list[Finding] = [Finding(
            source=self.source, signal="entity_existence", subcategory=_SUB, category=_CAT,
            observed=f"{matched['label']} — {'dissolved' if matched['dissolved'] else 'live'} "
                     f"(domain-verified via official website)",
            value={"band": band, "qid": matched["qid"], "official_website": matched["sites"]},
            locator=f"Wikidata {matched['qid']}",
            notes="CORROBORATION of entity standing — domain-verified (P856 matches vendor domain); "
                  "combines with GLEIF at higher confidence when they agree (§5.4.3)",
        )]

        inception = _claim_time(entity=ent, pid=_P_INCEPTION)
        raw["inception"] = inception.isoformat() if inception else None
        if inception is not None:
            m_band, years = _maturity_band(inception)
            findings.append(Finding(
                source=self.source, signal="entity_maturity", subcategory=_SUB, category=_CAT,
                observed=f"{matched['label']} — operating ~{years:.1f} year(s)",
                # Inception from a curated register is a STRONGER maturity claim than a domain
                # creation date, and `assurance_index` weights it accordingly — see maturity.py.
                value={"band": m_band, "qid": matched["qid"], "inception": raw["inception"],
                       "years": round(years, 2),
                       "maturity_index": maturity.maturity_index(years),
                       "assurance_index": maturity.assurance_index(years, self.source),
                       "evidence_strength": maturity.evidence_strength(self.source)},
                event_date=inception,
                locator=f"Wikidata {matched['qid']} P571",
                notes="ENTITY-level maturity from legal inception; affects business stability and "
                      "assurance only, never technical posture penalties",
            ))

        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    async def _search(self, ctx: CollectorContext, query: str) -> list[dict[str, Any]] | None:
        resp = await self._get_with_retry(
            ctx, _SEARCH, limiter_key="www.wikidata.org",
            params={"action": "wbsearchentities", "search": query, "language": "en",
                    "type": "item", "limit": _CANDIDATES, "format": "json"},
        )
        if resp is None or resp.status_code != 200:
            return None
        try:
            return list(resp.json().get("search", []))
        except (ValueError, AttributeError):
            return None

    async def _entity(self, ctx: CollectorContext, qid: str) -> dict[str, Any] | None:
        resp = await self._get_with_retry(
            ctx, _ENTITY.format(qid=qid), limiter_key="www.wikidata.org",
        )
        if resp is None or resp.status_code != 200:
            return None
        try:
            return resp.json().get("entities", {}).get(qid)
        except (ValueError, AttributeError):
            return None


def _host(url: str) -> str:
    m = _HOST.match(url or "")
    return m.group(1) if m else ""


def _registrable(host_or_domain: str) -> str:
    """Best-effort registrable domain: last two labels, lower-cased, www-stripped.

    Deliberately simple (no PSL): the vendor domains in scope are ordinary second-level
    domains, and this only ever gates an EXACT equality between two hosts, so a coarse rule
    is safe — a mismatch just means 'no corroboration', never a wrong match.
    """
    host = _WWW.sub("", (host_or_domain or "").strip().lower()).rstrip("/")
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _claim_values(entity: dict[str, Any], pid: str) -> list[Any]:
    out: list[Any] = []
    for claim in entity.get("claims", {}).get(pid, []):
        dv = claim.get("mainsnak", {}).get("datavalue", {})
        if "value" in dv:
            out.append(dv["value"])
    return out


def _claim_time(entity: dict[str, Any], pid: str) -> datetime | None:
    """Parse a Wikidata time claim (+YYYY-MM-DD...) into UTC datetime."""
    for claim in entity.get("claims", {}).get(pid, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict):
            raw = str(value.get("time") or "")
            if raw.startswith("+"):
                raw = raw[1:]
            # Keep date precision; UTC midnight is sufficient for maturity banding.
            try:
                return datetime.fromisoformat(raw[:19]).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def _maturity_band(inception: datetime) -> tuple[str, float]:
    """Delegates to `maturity.py`. This used to be a private copy of the same five-rung ladder the
    RDAP collector carried; two collectors independently maintaining one model is how the two
    quietly stop agreeing."""
    years = maturity.years_between(inception, datetime.now(UTC)) or 0.0
    return maturity.maturity_band(years) or "new_lt_1", years
