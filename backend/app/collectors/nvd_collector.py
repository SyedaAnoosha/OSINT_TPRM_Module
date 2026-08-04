"""NVD collector — CVEs against the vendor's own products.

PRODUCT-SCOPED and narrow on purpose (source_assessment.md §8): NVD scores vendors who
*make software* by their product CVE history. Inferring "vendor is vulnerable" from a
banner is speculation and we do not do it. Commercial use is permitted; a free API key
raises the rate limit. Mandatory UI attribution (not added here — it's a scorecard
requirement): "This product uses the NVD API but is not endorsed or certified by the NVD."

Keyword search by vendor name is coarse — false positives are expected — so findings are
review candidates, and the theoretical (CVSS) nature is why this ranks below KEV in the
directness ladder.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_EPSS_API = "https://api.first.org/data/v1/epss"
_CAT = "breach_compromise_history"
_SUB = "known_vulnerabilities"
# A keyword search is coarse (source_assessment §8): matches are dominated by very old,
# unrelated CVEs. Without CPE product matching, recency is the cheapest relevance proxy —
# so we SCORE only recent candidates and keep at most _MAX_SCORED worst-severity ones. The
# full returned set still goes to the evidence store `raw`, so nothing observed is hidden.
_RECENCY_YEARS = 7
_MAX_SCORED = 25
# EPSS (FIRST, CC0/open, no auth) — probability a CVE is exploited in the next 30 days. It sits
# BETWEEN NVD's theoretical CVSS and KEV's confirmed exploitation (methodology directness ladder).
# A CVE at/above this probability is treated as a PROBABLE exploit — scored above a mere
# critical-unpatched CVSS, because "likely to be exploited" is worse than "severe in theory".
_EPSS_PROBABLE = 0.5


class NvdCollector(Collector):
    source = "nvd"
    reliability = 0.9
    # A clean NVD result is "no recent CVE keyword-matches this vendor" — coarse matching
    # and the recency cut mean it is weak evidence of absence (source_assessment §8).
    clean_reliability = 0.55
    timeout_s = 30.0

    def _clean(self, vendor: Vendor, keyword: str, raw: dict[str, Any]) -> CollectorResult:
        """Clean receipt: reached NVD, nothing recent+relevant to score. Benign, reduced reliability."""
        finding = Finding(
            source=self.source, signal="nvd_cve", subcategory=_SUB, category=_CAT,
            observed="no recent critical/high CVE keyword-match",
            value={"band": "no_critical_cve"},
            locator=f"NVD keywordSearch={keyword}",
            notes="clean receipt — no recent CVE keyword-matches this vendor (coarse match, §5.4.2)",
        )
        return self.result(vendor, "ok", raw=raw, findings=[finding],
                           reliability=self._clean_reliability(),
                           notes="no scorable CVE — recorded as clean receipt (§5.4.2)")

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        keyword = vendor.name or vendor.ref
        headers = {}
        if ctx.settings.nvd_api_key:
            headers["apiKey"] = ctx.settings.nvd_api_key

        await ctx.limiter.acquire("services.nvd.nist.gov")
        try:
            resp = await ctx.http.get(
                _API,
                params={"keywordSearch": keyword, "resultsPerPage": 50},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            return self.result(vendor, "error", notes=f"NVD fetch failed: {type(exc).__name__}: {exc}")
        if resp.status_code == 403:
            return self.result(vendor, "error", notes="NVD 403 — rate limited (add TPRM_NVD_API_KEY)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"NVD returned {resp.status_code}")

        data = resp.json()
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return self._clean(vendor, keyword, {"keyword": keyword, "total": 0})

        scored = [self._summarise(v) for v in vulns]
        scored = [s for s in scored if s]
        raw: dict[str, Any] = {"keyword": keyword, "returned": len(vulns), "summaries": scored[:50]}

        # De-noise: score only recent candidates, worst-severity first, capped. Undated CVEs
        # are kept (we cannot prove them stale). This is where the keyword-match false
        # positives (e.g. 2005 CVEs on a modern SaaS vendor) are dropped from SCORING, not
        # from the evidence store above.
        cutoff = datetime.now(UTC) - timedelta(days=365 * _RECENCY_YEARS)
        kept = [s for s in scored if s["published"] is None or s["published"] >= cutoff]
        kept.sort(key=lambda s: (s["score"] or 0.0), reverse=True)
        kept = kept[:_MAX_SCORED]
        raw["scored_recent"] = len(kept)
        if not kept:
            # Matches existed but all were stale/undated-out — nothing recent to score.
            return self._clean(vendor, keyword, raw)

        # EPSS enrichment: upgrade CVEs likely to be exploited to a higher band than CVSS alone.
        epss = await self._fetch_epss(ctx, [s["cve"] for s in kept if s.get("cve")])
        raw["epss_enriched"] = len(epss)
        for s in kept:
            p = epss.get(s["cve"])
            s["epss"] = p
            if p is not None and p >= _EPSS_PROBABLE:
                s["band"] = "probable_exploit"   # exploitation-likely trumps theoretical CVSS

        findings: list[Finding] = []
        for s in kept:
            epss_note = f"; EPSS {s['epss']:.2f}" if s.get("epss") is not None else ""
            findings.append(
                Finding(
                    source=self.source, signal="nvd_cve", subcategory=_SUB, category=_CAT,
                    observed=f"{s['cve']} {s['severity']} (CVSS {s['score']}{epss_note})",
                    value={"band": s["band"], "cve": s["cve"], "cvss": s["score"],
                           "severity": s["severity"], "epss": s.get("epss")},
                    event_date=s["published"],
                    locator=f"NVD {s['cve']}",
                    notes="keyword-matched — review before attributing to a live product"
                          + (" (EPSS via FIRST, CC0)" if s.get("epss") is not None else ""),
                )
            )
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    async def _fetch_epss(self, ctx: CollectorContext, cve_ids: list[str]) -> dict[str, float]:
        """Batch EPSS lookup (FIRST, no auth). Returns {cve: probability}. Degrades to {} on any
        failure — EPSS is enrichment, so its absence must never break the NVD score."""
        assert ctx.http is not None
        ids = [c for c in cve_ids if c][:100]
        if not ids:
            return {}
        await ctx.limiter.acquire("api.first.org")
        try:
            r = await ctx.http.get(_EPSS_API, params={"cve": ",".join(ids)})
        except httpx.HTTPError:
            return {}
        if r.status_code != 200:
            return {}
        try:
            return {d["cve"]: float(d["epss"]) for d in r.json().get("data", []) if d.get("cve")}
        except (ValueError, KeyError, TypeError):
            return {}

    @staticmethod
    def _summarise(entry: dict[str, Any]) -> dict[str, Any] | None:
        cve = entry.get("cve", {})
        cve_id = cve.get("id")
        metrics = cve.get("metrics", {})
        score = None
        severity = "UNKNOWN"
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                data = metrics[key][0].get("cvssData", {})
                score = data.get("baseScore")
                severity = data.get("baseSeverity") or metrics[key][0].get("baseSeverity", "UNKNOWN")
                break
        if score is None:
            return None
        # Band states the CVSS severity we observed and nothing more. It previously called this
        # bucket "remediated", which was a misnomer — it is simply everything below HIGH, and NVD
        # says nothing about whether a fix was applied. Remediation now travels on
        # Finding.remediation_evidenced, so it is never inferred from severity.
        band = "cvss_critical" if severity == "CRITICAL" else (
            "cvss_high" if severity == "HIGH" else "cvss_medium_or_low"
        )
        published = None
        if cve.get("published"):
            try:
                published = datetime.fromisoformat(cve["published"]).replace(tzinfo=UTC)
            except ValueError:
                published = None
        return {"cve": cve_id, "score": score, "severity": severity, "band": band,
                "published": published}
