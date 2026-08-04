"""E14 — Gap analysis & recommendations: a third audience view whose renderer is a language model.

INHERITS `app/summariser.py`'S ONE RULE AND MUST NOT WEAKEN IT: **the LLM is a read layer over the
finished record.** It never computes, adjusts, re-weights or second-guesses a score. Posture,
confidence, assurity, the inherent tier and the residual cell are all formed upstream by
deterministic code and handed to the model as GIVEN FACTS. A model that writes "the 72 posture
understates their real risk" has silently produced a second, unauditable score — and it is the one
the reader will remember. `_SYSTEM` states this as a hard rule and the output shape gives the model
nowhere to put a re-score even if it tried: there is no field for one.

WHY THIS IS A THIRD `audience_views.py` VIEW, NOT A FOURTH SOURCE OF TRUTH. `assemble_context` holds
no arithmetic of its own — every figure is copied from the module that owns it (the same discipline
`audience_views.procurement_dossier` and `security_dossier` follow), so this file cannot become a
place where a posture, a residual tier or a compliance gap is computed a second, slightly different
way. The one thing genuinely new here is the model's PROSE about the assembled facts, and prose is
kept structurally apart from findings: `evidence_finding_ids[]` on every gap and recommendation is a
citation into the hash-stamped record, not a substitute for one.

A RECOMMENDATION IS NOT A FINDING. Findings are hash-stamped observations with a band, a penalty and
a re-check date. Recommendations are prose, marked AI-generated, disposable and regenerable — they
travel in a different part of the response and must never be merged into the findings list.

THE PROVIDER CHAIN FALLS BACK ON TRANSPORT FAILURE, NEVER ON CONTENT (`generate`'s design rule,
verbatim from the phase plan): a 429, a 5xx, a timeout or a connection error tries the next
provider; a 200 whose content reads poorly is returned or the whole call fails — never retried
until it "looks better", which is how a system acquires an unrecorded editorial policy. Exhausting
the chain is a 503 (`GapAnalysisExhausted`), never a template: a hand-assembled fallback would be
indistinguishable on the page from a real answer, and the reader would have no way to know which
they were trusting.

`limitations` IS COPIED FROM P2'S COVERAGE STATEMENT, NEVER GENERATED. The model is not even asked
for it — the honest sentence about what the assessment could not see already exists, and asking a
model to paraphrase it is a chance for it to soften it, which is the version that gets read.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from .canonical import canonical_json, sha256
from .config import get_settings
from .logging_config import get_logger
from .models import utcnow

log = get_logger("gap_analysis")

#: Bumped whenever `_SYSTEM` or the requested output shape changes — carried on every generated
#: record's provenance so a reader can tell which prompt produced it (design rule 3: identical
#: context and prompt across providers; the version is what makes a LATER change to the prompt
#: distinguishable from a provider disagreement).
PROMPT_VERSION = "e14-v1"

_CONFIDENCE_FLOOR_BAND = "Low"

_SYSTEM = (
    "You are a TPRM analyst's assistant. You are given a finished, deterministic vendor "
    "assessment — posture, confidence, assurity, continuity, compliance and expectation gaps, "
    "inherent and residual risk, and the charged findings that produced them — ALL ALREADY "
    "COMPUTED. Your job is to explain the gap between what this vendor's exposure calls for and "
    "what was observed, and to propose prioritised, actionable recommendations.\n\n"
    "Hard rules, in order of how badly breaking them damages this product:\n"
    "1. NEVER comment on, re-weight, or second-guess a score. Do not write that a number seems "
    "high, low, generous or harsh. Every number in the context is a GIVEN FACT, not a suggestion.\n"
    "2. Every gap and every recommendation MUST cite evidence_finding_ids drawn ONLY from the "
    "finding ids listed in the context. Do not invent an id. If a point has no citable finding, "
    "leave evidence_finding_ids empty rather than making one up.\n"
    "3. Do NOT write a 'limitations' section — it is attached separately from the coverage "
    "statement and your version would only be a weaker paraphrase of the real one.\n"
    "4. Ground every claim in the context provided. Do not invent findings, breaches, frameworks "
    "or sources that are not present.\n"
    "5. Respond with ONLY a single JSON object, no prose outside it and no markdown fences, "
    "matching exactly this shape:\n"
    '{"executive_summary": "2-4 sentences: what this vendor is, what the exposure is, where the '
    'gap is concentrated", '
    '"gaps": [{"theme": "...", "what_we_observed": "...", "what_we_expected": "...", '
    '"why_it_matters": "...", "evidence_finding_ids": ["..."], "confidence_caveat": "..."}], '
    '"recommendations": [{"priority": "high|medium|low", "recommendation": "...", '
    '"rationale": "...", "effort": "low|medium|high", "owner_hint": "...", '
    '"contract_flowdown_ref": null, "evidence_finding_ids": ["..."], "addresses_gap": "..."}]}'
)


class GapAnalysisUnavailable(RuntimeError):
    """No provider in the chain is configured. Opt-in; the endpoint maps this to 503 — the
    summariser's rule (inert when unconfigured), not a template pretending to be one."""


class GapAnalysisExhausted(RuntimeError):
    """Every configured provider failed on a transport or rate-limit basis. Maps to 503, never a
    degraded answer — see the module docstring."""


@dataclass(frozen=True)
class GateResult:
    """Whether the button is enabled, and the stated reason(s) when it is not.

    NEVER SILENTLY ABSENT, NEVER ENABLED-BUT-USELESS (E14 placement/gating). Each reason is a
    complete sentence a user can read on the disabled button, not a code the caller has to look up.
    """

    allowed: bool
    reasons: list[str] = field(default_factory=list)


def gate(*, score: Any, inherent_tier: str | None) -> GateResult:
    """The four stated refusals, plus provider availability. A provisional inherent tier does NOT
    gate — see `GapAnalysisContext`'s exposure block, which annotates it instead."""
    reasons: list[str] = []
    if score is None:
        reasons.append(
            "No published posture — this vendor has not been scored yet. There is no finished "
            "assessment to analyse."
        )
    elif getattr(score, "blocked", False):
        reasons.append(
            "No published posture — this vendor is blocked pending human adjudication. There is "
            "no finished assessment to analyse."
        )
    elif getattr(score, "refused", False):
        reasons.append(
            "No published posture — evidence coverage was below the floor and the score was "
            "refused. A gap analysis over a Ghost record would be an essay about absence, and it "
            "would read as an assessment."
        )
    elif getattr(score, "confidence_band", None) == _CONFIDENCE_FLOOR_BAND or getattr(score, "ghost", False):
        reasons.append(
            f"Confidence is {_CONFIDENCE_FLOOR_BAND} — the same refusal the posture itself makes "
            f"at a harder floor. A recommendation list built on thin coverage is a list of guesses "
            f"about the evidence this assessment could not see."
        )
    if inherent_tier is None:
        reasons.append(
            "Inherent tier is not declared. Recommendations are prioritised by exposure — without "
            "a tier, 'prioritised' means only the order the model happened to write them in."
        )
    if not get_settings().gap_analysis_configured():
        reasons.append(
            "No LLM is configured for gap analysis (set TPRM_GEMINI_*, TPRM_GROK_* or "
            "TPRM_OPENROUTER_* — base_url, api_key and model, all three, for at least one)."
        )
    return GateResult(allowed=not reasons, reasons=reasons)


def _pf(profile_field: Any) -> Any:
    """A `ProfileField`'s `.value`, or None. The provenance (source/locator/fetched_at) is not
    handed to the model — it is not a fact about the vendor, it is a fact about how we know it."""
    return profile_field.value if profile_field is not None else None


@dataclass(frozen=True)
class GapAnalysisContext:
    """Everything the model sees, assembled ONCE by deterministic code — never by the prompt
    reaching into the store (see the module docstring's boundary rule).

    `as_dict()` is exactly what gets rendered into the prompt and exactly what a reviewer inspects
    to know what the model saw, without running it — the exit criterion this dataclass exists to
    satisfy.
    """

    vendor_ref: str
    identity: dict[str, Any]
    posture: dict[str, Any]
    findings: list[dict[str, Any]]
    confidence: dict[str, Any]
    assurity: dict[str, Any] | None
    continuity: dict[str, Any]
    gaps: dict[str, Any]
    exposure: dict[str, Any]
    context: dict[str, Any]
    coverage_statement: dict[str, Any]

    def finding_ids(self) -> set[str]:
        return {f["evidence_id"] for f in self.findings if f.get("evidence_id")}

    def as_dict(self) -> dict[str, Any]:
        return {
            "vendor_ref": self.vendor_ref,
            "identity": self.identity,
            "posture": self.posture,
            "findings": self.findings,
            "confidence": self.confidence,
            "assurity": self.assurity,
            "continuity": self.continuity,
            "gaps": self.gaps,
            "exposure": self.exposure,
            "context": self.context,
        }

    def content_hash(self) -> str:
        return sha256(canonical_json(self.as_dict()))


def assemble_context(
    *,
    vendor_ref: str,
    profile: Any | None,
    score: Any,
    findings: list[dict[str, Any]],
    penalty_divisor: float,
    coverage_statement: dict[str, Any],
    assurity: Any,
    continuity: Any,
    compliance_gap: Any,
    expectation_gap: Any | None,
    residual: Any,
    concentration: list[str],
    assessment_plan: dict[str, Any],
) -> GapAnalysisContext:
    """Assemble the context from parts every one of which already exists and is already published
    somewhere (the plan's own framing) — copied, never recomputed. Every argument is the SAME
    object `/api/vendors/{ref}/assessment` and `/export` already build; this function only arranges
    them, the way `audience_views.py` arranges the P6 dossiers.

    `findings` is the pre-built row shape `/export` produces (signal, band_key, category, severity,
    observed, effective_penalty, evidence_id, ask_of_vendor, accepts_as_refute, recheck_after,
    dispute_status) — only CHARGED findings are handed to the model, because an uncharged one cost
    nothing and citing it as a "gap" would misstate what was actually found.
    """
    charged = [f for f in findings if float(f.get("effective_penalty") or 0.0) > 0]
    findings_block = [
        {
            "evidence_id": f.get("evidence_id"),
            "signal": f.get("signal"),
            "band": f.get("band_key"),
            "category": f.get("category"),
            "severity": f.get("severity"),
            "observed": f.get("observed"),
            "effective_penalty": f.get("effective_penalty"),
            "ask_of_vendor": f.get("ask_of_vendor"),
            "accepts_as_refute": f.get("accepts_as_refute"),
            "recheck_after": f.get("recheck_after"),
            "dispute_status": f.get("dispute_status"),
        }
        for f in charged
    ]

    identity = {
        "vendor_ref": vendor_ref,
        "legal_name": _pf(getattr(profile, "legal_name", None)) if profile else None,
        "jurisdiction": _pf(getattr(profile, "jurisdiction", None)) if profile else None,
        "sector": _pf(getattr(profile, "sector", None)) if profile else None,
        "employees": _pf(getattr(profile, "employees", None)) if profile else None,
        "revenue_band": (profile.cohort.revenue_band if (profile and profile.cohort) else None),
        "ownership": _pf(getattr(profile, "ownership", None)) if profile else None,
        "inception": _pf(getattr(profile, "inception", None)) if profile else None,
        "domain_age_days": _pf(getattr(profile, "domain_age_days", None)) if profile else None,
    }

    publishable = not (score.blocked or score.refused)
    posture = {
        "posture": score.posture if publishable else None,
        "grade": score.grade if publishable else None,
        "published": publishable,
        "blocked": score.blocked,
        "blocked_reason": score.blocked_reason,
        "refused": score.refused,
        "critical_ceiling_applied": score.critical_ceiling_applied,
        "ceiling_cause": score.ceiling_cause,
        "penalty_divisor": penalty_divisor,
        "categories": [
            {
                "category": c.category, "posture": c.posture, "grade": c.grade,
                "penalty": c.penalty, "coverage": c.coverage, "findings": c.findings,
            }
            for c in (score.categories or [])
        ] if publishable else [],
    }

    confidence = {
        "overall_confidence": score.overall_confidence,
        "confidence_band": score.confidence_band,
        "ghost": score.ghost,
        "coverage": coverage_statement.get("coverage"),
        "statement": coverage_statement.get("statement"),
        "not_collected_this_run": coverage_statement.get("not_collected_this_run"),
        "held_no_lawful_free_source": coverage_statement.get("held_no_lawful_free_source"),
    }

    assurity_block = None if assurity is None or not getattr(assurity, "published", False) else {
        "score": assurity.score,
        "observed_signals": assurity.observed_signals,
        "gap_count": assurity.gap_count,
        "inputs": [i.cited() for i in assurity.inputs],
    }

    continuity_block = {
        "standing": continuity.standing,
        "flags": [f.cited() for f in continuity.flags],
        "age_context": list(continuity.age_context),
    }

    gaps_block = {
        "expectation_gap": None if not (expectation_gap and expectation_gap.published) else {
            "gap": expectation_gap.gap,
            "expected_posture": expectation_gap.expected_posture,
            "n": expectation_gap.n,
            "drivers": [d.cited() for d in expectation_gap.drivers],
        },
        "compliance_gap": {
            "frameworks_considered": list(compliance_gap.frameworks_considered),
            "gaps": [g.cited() for g in compliance_gap.gaps],
        },
    }

    exposure_block = {
        "inherent_tier": residual.inherent.tier,
        "inherent_basis": residual.inherent.basis,
        "inherent_provisional": residual.inherent.provisional,
        "residual": residual.residual,
        "residual_label": residual.residual_label,
        "substitutability": residual.substitutability,
        "escalated_from": residual.escalated_from,
    }

    context_block = {
        "peer_cohort": profile.cohort.key if (profile and profile.cohort) else None,
        "fourth_party_spofs": list(concentration),
        "assessment_plan": assessment_plan,
    }

    return GapAnalysisContext(
        vendor_ref=vendor_ref, identity=identity, posture=posture, findings=findings_block,
        confidence=confidence, assurity=assurity_block, continuity=continuity_block,
        gaps=gaps_block, exposure=exposure_block, context=context_block,
        coverage_statement=coverage_statement,
    )


def _render_value(v: Any) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(",", ":"), default=str)
    return str(v)


def render_prompt(ctx: GapAnalysisContext) -> str:
    """The user message, built ONLY from the assembled context — never from a store query. This
    is the function a reviewer reads to know exactly what the model saw."""
    lines: list[str] = [f"VENDOR: {ctx.vendor_ref}"]
    for section_name, section in (
        ("IDENTITY", ctx.identity), ("POSTURE", ctx.posture), ("CONFIDENCE", ctx.confidence),
        ("ASSURITY", ctx.assurity), ("CONTINUITY", ctx.continuity), ("GAPS", ctx.gaps),
        ("EXPOSURE", ctx.exposure), ("CONTEXT", ctx.context),
    ):
        lines.append("")
        lines.append(f"{section_name}:")
        if section is None:
            lines.append("  (not published)")
            continue
        for k, v in section.items():
            lines.append(f"  {k}: {_render_value(v)}")

    lines.append("")
    lines.append(f"CHARGED FINDINGS ({len(ctx.findings)}) — cite these ids in evidence_finding_ids:")
    for f in ctx.findings:
        lines.append(
            f"  - [{f.get('evidence_id')}] {f.get('signal')}={f.get('band')} "
            f"({f.get('category')}, severity {f.get('severity')}, "
            f"penalty {f.get('effective_penalty')}): {f.get('observed')}"
        )
    return "\n".join(lines)


def _parse_output(text: str) -> tuple[dict[str, Any], str | None]:
    """Best-effort JSON parse. A 200 whose content is not valid JSON is still a 200 — returned as
    the executive summary rather than retried against another provider (design rule 1)."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw[:4].lower() == "json":
            raw = raw[4:]
        raw = raw.strip()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        data = None
    if isinstance(data, dict):
        return data, None
    return (
        {"executive_summary": text.strip()[:4000], "gaps": [], "recommendations": []},
        "the provider's response was not a JSON object; the raw text is shown as the executive "
        "summary and no gaps or recommendations were extracted",
    )


def _drop_invented_citations(parsed: dict[str, Any], finding_ids: set[str]) -> int:
    """Strip any `evidence_finding_ids` the model invented. A validator that silently accepted an
    invented id would make the citation decorative — the drop is counted, never swallowed."""
    dropped = 0
    for bucket in ("gaps", "recommendations"):
        items = parsed.get(bucket)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            ids = item.get("evidence_finding_ids")
            if not isinstance(ids, list):
                continue
            kept = [i for i in ids if i in finding_ids]
            dropped += len(ids) - len(kept)
            item["evidence_finding_ids"] = kept
    return dropped


def _finalise(resp: httpx.Response, provider_name: str, configured_model: str,
             ctx: GapAnalysisContext, context_hash: str) -> dict[str, Any]:
    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        model_reported = data.get("model") or configured_model
    except (ValueError, KeyError, IndexError, TypeError):
        text, model_reported = resp.text, configured_model

    parsed, parse_warning = _parse_output(text or "")
    dropped = _drop_invented_citations(parsed, ctx.finding_ids())

    return {
        "vendor_ref": ctx.vendor_ref,
        "executive_summary": str(parsed.get("executive_summary") or ""),
        "gaps": parsed.get("gaps") or [],
        "recommendations": parsed.get("recommendations") or [],
        # COPIED, NEVER GENERATED — see the module docstring.
        "limitations": ctx.coverage_statement,
        "provenance": {
            "provider": provider_name,
            "model": model_reported,
            "prompt_version": PROMPT_VERSION,
            "context_hash": context_hash,
            "generated_at": utcnow().isoformat(),
        },
        "dropped_evidence_ids": dropped,
        "parse_warning": parse_warning,
        "ai_generated": True,
    }


async def generate(ctx: GapAnalysisContext, *, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    """Walk the provider chain, one attempt each, falling back only on transport failure or a
    non-200 (429s and 5xxs included) — never on content. Raises `GapAnalysisUnavailable` when no
    provider is configured, `GapAnalysisExhausted` when every configured provider failed.

    `client` is a test seam, exactly as `summariser.summarise` uses it: pass an `AsyncClient` (with
    a `MockTransport`) to intercept every call across the whole chain in one test; in production it
    is None and a short-lived client is opened and closed here.
    """
    settings = get_settings()
    chain = settings.gap_analysis_chain()
    if not chain:
        raise GapAnalysisUnavailable(
            "no LLM configured for gap analysis (set TPRM_GEMINI_*, TPRM_GROK_* or "
            "TPRM_OPENROUTER_* — base_url, api_key and model, all three, for at least one)"
        )

    user_prompt = render_prompt(ctx)
    context_hash = ctx.content_hash()

    attempts: list[str] = []
    owned_client: httpx.AsyncClient | None = None
    if client is None:
        owned_client = httpx.AsyncClient(timeout=settings.gap_analysis_timeout_s)
        client = owned_client
    try:
        for name, base_url, api_key, model in chain:
            url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
            }
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                log.warning("gap_analysis provider %s transport error: %s", name, exc)
                attempts.append(f"{name}: transport error ({exc})")
                continue  # DESIGN RULE 1 — fall back on transport failure, one attempt each

            if resp.status_code != 200:
                log.warning("gap_analysis provider %s returned HTTP %s", name, resp.status_code)
                attempts.append(f"{name}: HTTP {resp.status_code}")
                continue  # 429 / 5xx / any non-200 — never a content judgement

            # A 200 IS RETURNED, NOT RETRIED — even when the content reads poorly (design rule 1).
            return _finalise(resp, name, model, ctx, context_hash)

        raise GapAnalysisExhausted(f"every configured provider failed: {'; '.join(attempts)}")
    finally:
        if owned_client is not None:
            await owned_client.aclose()
