"""ITA Consolidated Screening List collector — the sanctions GATE feed.

This is not a scored source. It feeds the gate (scoring.yaml gates.sanctions): a match
routes the whole record to BLOCKED for human adjudication and emits NO score. Under the
Autonomous Sanctions Act s16(7) the screening record — including a CLEAN result — is the
client's statutory-defence evidence (Finding B), so every run is persisted with the list's
publication date as `source_version`, and a clean screen is `empty`-with-a-record.

Tuned for RECALL, not precision (methodology §5.5.1): a missed hit destroys the defence;
a false positive costs an analyst an hour. Matching is deliberately generous and every hit
is a review item with evidence, never an automated conclusion.

Uses the KEYLESS downloadable consolidated list, cached locally and refreshed daily, so
the gate works in a demo without an API key. The full CSL is ~33 MB; we fetch it once.

═══ WHAT A MATCH IS — measured, then narrowed (2026-07-31) ═══

THE POLICY IS NOT LOOSENED HERE AND MUST NOT BE. A possible sanctions match still blocks the
record and goes to a person, always. What changed is what counts as a POSSIBLE MATCH, because
whole-word containment was calling word collisions matches.

The 114-vendor seeding run measured it: **10 of 114 household-name public companies blocked**,
8.8%. The causes, from the real list:

    BT Group      626 hits.  "bt" is two characters and was dropped by a `len >= 3` filter, so the
                             ONLY surviving query word was "group" — which appears in 626 CSL
                             entries. A two-letter company name silently became a match on a
                             generic corporate suffix.
    Line           20 hits.  "ISLAMIC REPUBLIC OF IRAN SHIPPING LINE", "Bestway Line FZCO"
    Wise            9 hits.  "ROBERT WISE", "Infinity Wise Technology Limited"
    Box             2 hits.  "RED BOX ENERGY SERVICES PTE LTD"
    Xero            1 hit.   "CLOUD XERO MANAGEMENT PTE. LTD."

RARITY IS NOT THE DISCRIMINATOR, which was the first idea and it is wrong. "xero" appears in
exactly ONE entry in the whole list and is still a false positive. What separates a hit from a
collision is WHERE the name sits: a company's distinguishing name leads its legal name. "RED BOX
ENERGY SERVICES" is a company called Red Box Energy, not a company called Box.

So a match now requires the query to ACCOUNT FOR the entity's name rather than merely appear
inside it — either the whole name (`full`) or its leading words (`head`) — checked against the
primary name and each alias separately, since a front company's alias is often the real name.

Measured against the same 114 vendors and the real 25,921-entry list: **10 false positives → 5**,
and every survivor is a genuine name correspondence a human should look at (`Experian` →
*Experian Holdings, Inc.*, `Orange` → *ORANGE VOLUNTEERS*). Recall was checked against fifteen
genuinely listed entities — Huawei, ZTE, Kaspersky, Hikvision, Inspur, SMIC, Rosneft, Gazprom,
Sberbank, DJI, Dahua, China Telecom, Megvii — and **every one that matched before still matches**,
with the correct entity ranked first. Dropping the `len >= 3` filter also RECOVERS recall: a real
"BT GROUP PLC" entry would now match, where before "bt" was discarded unread.

A QUERY WITH NOTHING DISTINCTIVE IN IT IS NOT A CLEAN SCREEN. If every word of a name is a generic
corporate term, this collector records `screened: false` with a reason rather than `clean`. A clean
screen IS the s16(7) defence, and recording one we did not earn would be the worst failure available
on this path — worse than a false positive, because nobody ever looks at it again.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_WORD = re.compile(r"[a-z0-9]+")
_DOWNLOAD = "https://data.trade.gov/downloadable_consolidated_screening_list/v1/consolidated.json"
_CACHE_MAX_AGE_H = 24

#: Legal-form tokens stripped from BOTH sides before comparison. "BOX INC" and "Box" are the same
#: name; "RED BOX ENERGY SERVICES PTE LTD" is not, and the suffixes are what obscure that.
_LEGAL_SUFFIX = frozenset({
    "ltd", "limited", "llc", "inc", "incorporated", "plc", "pte", "pty", "gmbh", "ag", "sa", "sas",
    "sarl", "spa", "srl", "bv", "nv", "co", "corp", "corporation", "llp", "lp", "fze", "fzco",
    "ab", "oy", "aps", "as", "kk", "kg", "cjsc", "ojsc", "jsc", "pjsc", "ooo", "zao",
    # LEADING forms matter as much as trailing ones: "AO Kaspersky Lab" is Kaspersky Lab, and
    # without stripping "ao" the head-alignment rule would look at the wrong first word.
    "ao", "oao", "pt", "sp", "doo", "dd", "ad", "eood", "ood",
})

#: Words that cannot be the SOLE basis of a match. Every one is a corporate generic that appears in
#: hundreds of list entries; matching on them alone is how "BT Group" reached 626 hits.
_GENERIC = frozenset({
    "group", "holding", "holdings", "company", "international", "technology", "technologies",
    "service", "services", "system", "systems", "solutions", "industry", "industries", "trading",
    "enterprise", "enterprises", "ventures", "partners", "global", "bank", "energy", "capital",
})


class ItaCollector(Collector):
    source = "ita"
    reliability = 0.95  # official US Government publication (source_assessment.md §5)
    timeout_s = 60.0    # first fetch downloads the full list

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        try:
            payload = await self._list(ctx)
        except (httpx.HTTPError, ValueError) as exc:
            return self.result(vendor, "error", notes=f"ITA list fetch failed: {type(exc).__name__}: {exc}")

        results = payload.get("results", [])
        source_version = self._published_date(payload)
        query = (vendor.name or vendor.ref).lower().strip()
        tokens = {query} | {a.lower() for a in vendor.aliases}

        # A NAME WITH NOTHING DISTINCTIVE IN IT CANNOT BE SCREENED, and saying otherwise would
        # manufacture the statutory defence rather than earn it. `screened: false` is an honest
        # gap a reviewer can act on; a fabricated clean screen is one nobody ever revisits.
        if not any(self._distinctive(self._core(t)) for t in tokens):
            return self.result(
                vendor, "empty", source_version=source_version,
                raw={"query": query, "list_size": len(results), "match_count": 0,
                     "screened": False,
                     "not_screened_reason": (
                         "Every word in this vendor's name is a generic corporate term, so there is "
                         "nothing distinctive to screen on. This is NOT a clean screen and must not "
                         "be recorded as one — supply the registered legal name and re-run.")},
                notes="NOT SCREENED — no distinctive name token; this is not an s16(7) clean record",
            )

        scored = [(r, self._match_strength(r, tokens)) for r in results]
        matches = [(r, s) for r, s in scored if s is not None]

        if not matches:
            # CLEAN SCREEN — recorded, not discarded. This IS the s16(7) defence evidence.
            return self.result(
                vendor, "empty", source_version=source_version,
                raw={"query": query, "list_size": len(results), "match_count": 0, "screened": True,
                     "match_rule": "full-name or head-aligned, per name and per alias"},
                notes=f"clean screen vs {len(results)} CSL entries (retained as s16(7) defence record)",
            )

        raw: dict[str, Any] = {
            "query": query, "list_size": len(results), "match_count": len(matches),
            "screened": True,
            "match_rule": "full-name or head-aligned, per name and per alias",
            "matches": [{"name": m.get("name"), "source": m.get("source"),
                         "programs": m.get("programs"), "type": m.get("type"),
                         "match_strength": s,
                         "alt_names": m.get("alt_names")} for m, s in matches[:50]],
        }
        # A hit is a REVIEW ITEM; the gate (Phase 2) turns any hit into BLOCKED.
        #
        # THE ENTITY TYPE AND MATCH STRENGTH RIDE ON THE OBSERVATION so an adjudicator sees them
        # without opening the payload. "KOGAN, Alexander Borisovich [Individual]" is a five-second
        # adjudication; the same line without `[Individual]` is a research task. The queue this gate
        # feeds is only as good as how fast a human can clear a false positive from it.
        findings = [self._finding(m, s, source_version) for m, s in matches[:50]]
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version=source_version)

    # ------------------------------------------------------------------ helpers

    async def _list(self, ctx: CollectorContext) -> dict[str, Any]:
        """Return the CSL payload, using a local daily cache to avoid re-downloading 33 MB."""
        cache = Path(ctx.settings.data_dir) / "ita_csl_cache.json"
        if cache.exists():
            age_h = (datetime.now(UTC).timestamp() - cache.stat().st_mtime) / 3600
            if age_h < _CACHE_MAX_AGE_H:
                return json.loads(cache.read_text(encoding="utf-8"))

        await ctx.limiter.acquire("data.trade.gov")
        resp = await ctx.http.get(_DOWNLOAD, timeout=self.timeout_s, follow_redirects=True)
        resp.raise_for_status()
        payload = resp.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    @staticmethod
    def _published_date(payload: dict[str, Any]) -> str:
        meta = payload.get("meta", {})
        return str(meta.get("date") or meta.get("published") or "unknown")

    def _finding(self, entry: dict[str, Any], strength: str, source_version: str) -> Finding:
        """One review item, written so an adjudicator can clear or escalate it without digging.

        THE TYPE AND THE STRENGTH ARE ON THE OBSERVATION LINE, not buried in the payload. The
        seeding run's `KOGAN, Alexander Borisovich` is a five-second adjudication once the line says
        `[Individual]`, and a research task without it. A blocking queue is only as safe as the
        speed at which a human can clear a false positive from it — a queue that is slow to clear
        gets rubber-stamped, and a rubber-stamped queue is how a real match gets waved through.
        """
        name = entry.get("name")
        kind = entry.get("type")
        kind_tag = f" [{kind}]" if kind else ""
        why = ("the query is this entity's whole name" if strength == "full"
               else "the query is the leading words of this name")
        return Finding(
            source=self.source, signal="sanctions_screen_hit",
            subcategory="sanctions_watchlists", category="regulatory_legal_sanctions",
            observed=f"POSSIBLE match ({strength}): {name}{kind_tag} [{entry.get('source')}]",
            value={"name": name, "source": entry.get("source"),
                   "programs": entry.get("programs"), "type": kind,
                   "match_strength": strength},
            locator=f"ITA CSL {source_version} :: {name}",
            notes=(f"RECALL-tuned match — adjudicate manually, never auto-conclude. "
                   f"Strength {strength}: {why}."),
        )

    @staticmethod
    def _core(text: Any) -> list[str]:
        """A name reduced to its distinguishing words, in order. Legal forms removed.

        ORDER IS KEPT, and that is the whole point — `head` alignment is only expressible over a
        sequence, and it is the rule that separates "Red Box Energy" from "Box".
        """
        return [w for w in _WORD.findall(str(text).lower()) if w not in _LEGAL_SUFFIX]

    @staticmethod
    def _distinctive(query_core: list[str]) -> bool:
        """False when a query has nothing to screen ON — every word a corporate generic."""
        return bool(query_core) and not all(w in _GENERIC for w in query_core)

    @classmethod
    def _match_strength(cls, entry: dict[str, Any], tokens: set[str]) -> str | None:
        """`"full"`, `"head"`, or None. Checked per NAME, never against a merged bag of words.

        THE BUG THE PER-NAME LOOP FIXES. Pooling the primary name and every alias into one set let a
        query match words drawn from three different names at once — an entity called "Alpha" with
        an alias "Beta Trading" would match the query "alpha trading", which is neither of its
        names. Aliases are checked in their own right because a front company's alias is frequently
        the real name, and they must be checked *as names*.
        """
        names = [entry.get("name") or ""]
        names += [a for a in (entry.get("alt_names") or []) if a]

        for token in tokens:
            q = cls._core(token)
            if not cls._distinctive(q):
                continue
            q_set = set(q)
            for name in names:
                n = cls._core(name)
                if not n:
                    continue
                if q_set == set(n):
                    return "full"          # the query IS this entity's name
                if q_set <= set(n) and n[:len(q)] == q:
                    return "head"          # ...and leads it: "Huawei" -> "HUAWEI TECHNOLOGIES CO LTD"
        return None

    @classmethod
    def _matches(cls, entry: dict[str, Any], tokens: set[str]) -> bool:
        """Whether this entry is a possible match at all. Kept as a bool for the gate's callers."""
        return cls._match_strength(entry, tokens) is not None
