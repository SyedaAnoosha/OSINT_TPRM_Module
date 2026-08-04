"""Optional LLM evidence-summariser — a READ LAYER over the finished record.

This is the one place an LLM touches the system, and its boundaries are deliberate
(methodology, "the AI moment"):

  * It NEVER computes or changes a score. It reads the already-published `Score` and the
    already-stored, hash-stamped `Evidence` receipts, and writes prose about them. The risk
    number and the confidence axis are formed by the deterministic engine, upstream, and are
    passed to the model as given facts — not asked for.
  * It NEVER writes to the evidence store. The digest is derived, disposable, and returned
    marked AI-generated. The immutable legal artefact stays the receipts it cites.
  * It is provider-agnostic: any OpenAI-compatible `chat/completions` endpoint works
    (OpenRouter, Groq, Google's OpenAI-compat surface), configured entirely by env — so no
    provider SDK and no vendor lock-in. See `config.Settings.llm_*`.
  * It is opt-in and inert when unconfigured: callers gate on `available()` and the endpoint
    returns 503 rather than pretending.

The context handed to the model is the finished RECORD: the score roll-up PLUS the actual
observations each source returned (the receipts' stored payloads), so the digest is about WHAT
WAS FOUND — not a restatement of the risk/confidence numbers. It is bounded (per-receipt and
total caps) and it is only the already-collected, lawfully-public OSINT the system holds — PII
is minimised at COLLECTION (entity-level / role addresses only), so nothing new is exposed and
egress stays auditable (source_assessment.md §data-egress). The digest cites the hashes and tells
the reader to verify against the receipts.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .config import get_settings
from .logging_config import get_logger
from .models import Evidence, Score

log = get_logger("summariser")

_SYSTEM = (
    "You are a risk analyst's assistant. You are given a vendor's EVIDENCE — the actual, "
    "hash-stamped observations each OSINT source returned (DNS/email-auth config, TLS posture, "
    "HTTP headers, certificate-transparency estate, breach & vulnerability findings, entity and "
    "domain-registration standing, regulator actions) — together with the deterministic scoring "
    "engine's roll-up (a posture 0-100 where 100 is strongest, a letter grade, and a separate "
    "confidence = evidence coverage). Write a short, plain-English brief of WHAT WAS ACTUALLY FOUND for a "
    "busy reviewer.\n\n"
    "Hard rules:\n"
    "- LEAD WITH THE EVIDENCE. Summarise the concrete observations — what each source found (or "
    "found clean, or couldn't reach) — grouped by theme. Do NOT merely restate the risk and "
    "confidence numbers; those are context for the evidence, not the story.\n"
    "- Do NOT recompute, re-weight, second-guess, or 'correct' any score. Report the numbers as "
    "given. You describe the record; you never re-score the vendor.\n"
    "- Treat posture and confidence as two separate axes. A strong-looking posture on LOW "
    "confidence is a 'Ghost' (unassessed, not safe) — say so, don't call it clean.\n"
    "- Ground every claim in the evidence provided. Do not invent findings, breaches, or sources "
    "that are not present. Where a source was empty or errored, say what is therefore unknown.\n"
    "- Be concise: a 2-3 sentence headline of the actual findings, then a few bullets on the "
    "load-bearing evidence, then one line on what would raise confidence. No preamble, no sign-off."
)

# _DISCLAIMER = (
#     "AI-generated summary of the stored record. It does not affect the score and is not itself "
#     "evidence — verify every claim against the cited hash-stamped receipts."
# )


class SummariserUnavailable(RuntimeError):
    """No LLM is configured. The feature is opt-in; the endpoint maps this to 503."""


class SummariserError(RuntimeError):
    """The configured provider was reached but the call failed (network/HTTP/parse)."""


def available() -> bool:
    """True when an OpenAI-compatible endpoint, key, and model are all configured."""
    return get_settings().llm_configured()


def _short(h: str | None) -> str:
    return (h or "")[:8]


# Per-receipt / total caps on how much raw observation text goes to the model — bounded egress:
# enough for the LLM to describe what was found, not an unbounded dump.
_RAW_PER_RECEIPT = 600
_RAW_TOTAL = 8000


def _compact(raw: dict[str, Any] | None) -> str:
    """Flatten a receipt's raw payload to a short, readable one-liner of the actual observations.
    Nested structures are JSON-compacted and clipped so a big estate dump can't blow the prompt."""
    if not raw:
        return ""
    parts: list[str] = []
    for k, v in raw.items():
        if isinstance(v, (dict, list)):
            s = json.dumps(v, separators=(",", ":"), default=str)
            if len(s) > 160:
                s = s[:157] + "…"
        else:
            s = str(v)
        parts.append(f"{k}={s}")
    out = ", ".join(parts)
    return out[:_RAW_PER_RECEIPT] + ("…" if len(out) > _RAW_PER_RECEIPT else "")


def _build_context(score: Score, evidence: list[Evidence]) -> tuple[str, list[str]]:
    """Render the record as compact text for the model. Returns (context, cited_hashes).

    Includes the ACTUAL OBSERVATIONS each source returned (so the digest is about the evidence,
    not a restatement of the score), bounded per-receipt and in total. The evidence is the
    already-collected, lawfully-public OSINT the system holds — PII is minimised at collection
    (entity-level / role addresses only), so what the collectors stored is what the reader sees.
    """
    lines: list[str] = []
    lines.append(f"VENDOR: {score.vendor_ref}")
    if score.blocked:
        lines.append(f"STATUS: BLOCKED — {score.blocked_reason or 'human adjudication required'}")
    elif score.refused:
        lines.append(
            f"STATUS: REFUSED (insufficient evidence) — confidence "
            f"{score.overall_confidence:.2f} below floor"
        )
    else:
        lines.append(
            f"POSTURE: {score.posture if score.posture is not None else 'n/a'}/100 "
            f"(grade {score.grade or 'n/a'}) — higher is stronger"
        )
        lines.append(f"CONFIDENCE (evidence coverage): {score.overall_confidence:.2f} ({score.confidence_band})")
        if score.ghost:
            lines.append("NOTE: low confidence — a 'Ghost' (looks clean only for lack of evidence).")
        if score.critical_ceiling_applied:
            cause = score.ceiling_cause or "a directly-observed critical capped the grade"
            lines.append(f"CRITICAL CEILING APPLIED: {cause}")

    if score.categories:
        lines.append("")
        lines.append("SCORE ROLL-UP (context only — do not just restate this):")
        for c in score.categories:
            posture = "n/a" if c.posture is None else f"{c.posture} (grade {c.grade})"
            lines.append(
                f"  - {c.category}: posture {posture} · penalty {c.penalty:.0f} · "
                f"coverage {c.coverage * 100:.0f}% · {c.findings} issue(s)"
            )

    cited: list[str] = []
    if evidence:
        lines.append("")
        lines.append("EVIDENCE — what each source actually found (cite by short hash):")
        budget = _RAW_TOTAL
        for e in evidence:
            short = _short(e.content_hash)
            cited.append(short)
            observed = _compact(e.raw)
            if observed and budget > 0:
                observed = observed[:budget]
                budget -= len(observed)
            else:
                observed = e.notes or ("(reached, nothing found)" if e.status == "empty" else e.status)
            lines.append(f"  - [{short}] {e.source} ({e.status}): {observed}")
    return "\n".join(lines), cited


async def summarise(
    score: Score, evidence: list[Evidence], *, client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """Produce an AI digest of a finished record. Raises SummariserUnavailable when
    unconfigured, SummariserError on any provider failure. Never mutates its inputs.

    `client` is a test seam: pass an AsyncClient (e.g. with a MockTransport) to intercept the
    call; in production it is None and a short-lived client is opened and closed here.
    """
    settings = get_settings()
    if not settings.llm_configured():
        raise SummariserUnavailable("no LLM configured (set TPRM_LLM_BASE_URL / _API_KEY / _MODEL)")

    context, cited = _build_context(score, evidence)
    base = settings.llm_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    # OpenRouter attribution headers — harmless to other providers.
    if settings.llm_referer:
        headers["HTTP-Referer"] = settings.llm_referer
    if settings.llm_title:
        headers["X-Title"] = settings.llm_title

    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Summarise this record:\n\n{context}"},
        ],
    }

    try:
        if client is not None:
            resp = await client.post(url, headers=headers, json=payload)
        else:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as owned:
                resp = await owned.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        log.warning("summariser transport error: %s", exc)
        raise SummariserError(f"could not reach LLM provider: {exc}") from exc

    if resp.status_code != 200:
        body = resp.text[:300]
        log.warning("summariser provider %s: %s", resp.status_code, body)
        raise SummariserError(f"LLM provider returned {resp.status_code}")

    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        model = data.get("model", settings.llm_model)
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        log.warning("summariser parse error: %s", exc)
        raise SummariserError("LLM response was not in the expected shape") from exc

    if not text:
        raise SummariserError("LLM returned an empty summary")

    return {
        "summary": text,
        "model": model,
        "cited_hashes": cited,
        # "disclaimer": _DISCLAIMER,
        "ai_generated": True,
    }
