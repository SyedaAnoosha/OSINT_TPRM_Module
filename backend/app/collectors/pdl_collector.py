"""PDL collector — OFFLINE firmographics fallback: industry, size, country by domain.

WHY. About one vendor in four is classified by no public register and carries no Wikidata industry
or headcount (asana, okta, box, canva all came back with nothing), so no peer cohort forms and the
benchmark cannot render. The People Data Labs Free Company Dataset is a static, domain-keyed dump
that fills exactly those gaps — and being a downloadable snapshot, the answer is reconstructible in
a way a live enrichment API is not.

IT EMITS NO FINDINGS — like the `firmographics` collector, and for the same reason. A finding is the
unit that becomes a penalty; a collector that emitted them would let size or industry move a score,
re-admitting the §7.3 size bias one level up. It returns `raw` only. Zero findings also means zero
effect on the CONFIDENCE axis — a thin profile weakens the COMPARISON, never the score.

IT IS A FALLBACK, NOT A SOURCE OF RECORD. `profile.py` reads it LAST, after GLEIF, the ABR, Wikidata
and RDAP, and only fills fields those left empty. A live register or a domain-verified Wikidata
entity always wins; PDL speaks only where they were silent.

OPT-IN AND GRACEFUL. With no index file present the collector returns `empty` — the source was not
consulted, which lowers coverage and therefore confidence, and never touches posture. The app runs
unconfigured, exactly like the other keyed collectors. Building the index is the operator's step,
and confirming the dataset's licence (commercial use, redistribution, retention) is theirs too.
"""
from __future__ import annotations

from typing import Any

from .. import pdl_index
from ..models import CollectorResult, Vendor
from .base import Collector, CollectorContext


class PdlCollector(Collector):
    source = "pdl"
    # A static third-party snapshot: below a live register or a domain-verified Wikidata match, and
    # it never scores anyway. It only fills a cohort dimension no other source could supply.
    reliability = 0.55
    timeout_s = 10.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        index_path = ctx.settings.pdl_index_path
        if not pdl_index.index_present(index_path):
            return self.result(
                vendor, "empty",
                notes="PDL index not present — build it with "
                      "`python -m app.pdl_index build --csv <dump>` (opt-in). Not consulted; "
                      "lowers coverage, never posture.",
            )
        if not vendor.domain:
            return self.result(vendor, "empty", notes="no domain — PDL is domain-keyed")

        row = pdl_index.lookup(index_path, vendor.domain)
        if row is None:
            return self.result(
                vendor, "empty",
                raw={"domain": pdl_index.registrable(vendor.domain)},
                notes="no PDL row for this domain — the dump does not cover it",
            )

        version = pdl_index.dataset_version(index_path) or "unknown"
        raw: dict[str, Any] = {
            "matched_domain": row.get("domain"),
            "name": row.get("name"),
            "industry": row.get("industry"),
            "size_range": row.get("size_range"),
            "employees": row.get("employees"),
            "country": row.get("country"),
            "dataset_version": version,
        }
        return self.result(
            vendor, "ok", raw=raw, source_version=f"PDL {version}",
            notes="firmographic context ONLY — no findings emitted, so it cannot move the posture or "
                  "the confidence axis. Fallback: fills only what registers/Wikidata left empty.",
        )
