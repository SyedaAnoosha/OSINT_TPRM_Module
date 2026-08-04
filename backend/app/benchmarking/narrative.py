"""Narrative — templated prose for the two audiences, from one dataset.

WHY TEMPLATES AND NOT GENERATION. Every sentence here is a claim about a named company, published to
a buyer who will act on it. A generated sentence cannot be versioned, diffed, or defended in a
dispute, and "the model phrased it that way" is not an answer to a supplier's lawyer. So the prose
lives in `benchmarks.yaml`, is versioned, and every rendering records which version produced it.

THE RULE THAT MAKES IT SAFE: a template whose required field is MISSING refuses to render.

That is the same discipline `scoring_config.py` applies when a penalising band has no plain-English
reason, and it exists for the same reason. The failure mode it prevents is specific and nasty:
Python's `str.format` on a partially-populated dict either raises or — worse, with a defaulted dict —
silently prints an empty string, so *"is below the peer median for  by  points"* ships as a confident
sentence with the numbers quietly removed. A refusal is loud; a blank is not.

TWO AUDIENCES, ONE DATASET:

  * SECURITY wants per-domain comparison: which domains lag, by how much, against how many peers.
  * PROCUREMENT wants a placement and what it means for contracting: the tier, the rank, the action.

Both read the same `BenchmarkPlacement`. Neither gets a number the other does not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import BenchmarkingConfig, get_benchmarking_config

if TYPE_CHECKING:
    from .models import BenchmarkPlacement


class TemplateRefused(ValueError):
    """A template was asked to render without a field it declares as required.

    Raised rather than returned so it cannot be mistaken for prose. Callers that would rather omit a
    line than fail are expected to catch it — `render_security` and `render_procurement` do exactly
    that, and skip the line — but the decision to omit is then explicit at the call site instead of
    hidden inside a formatter.
    """


def render(
    audience: str,
    key: str,
    fields: dict[str, Any],
    cfg: BenchmarkingConfig | None = None,
) -> str:
    """Fill one template, or refuse.

    `requires` is checked BEFORE formatting, against `None` as well as absence: a `None` that reaches
    `str.format` renders the four characters `None` into a sentence, which is worse than a blank
    because it looks deliberate.
    """
    cfg = cfg or get_benchmarking_config()
    template = cfg.template(audience, key)
    if not template:
        raise TemplateRefused(f"no narrative template at {audience}.{key}")

    # `placed` declares its fields under `requires:`; every other template under `<key>_requires:`.
    requires_key = "requires" if key == "placed" else f"{key}_requires"
    required = cfg.template_requires(audience, requires_key)
    missing = [f for f in required if fields.get(f) is None]
    if missing:
        raise TemplateRefused(
            f"{audience}.{key} requires {list(required)}; missing or null: {missing}. Refusing to "
            f"render rather than publish a sentence with the numbers silently removed."
        )

    try:
        return " ".join(template.format(**fields).split())
    except KeyError as exc:  # a placeholder the `requires:` list forgot to declare
        raise TemplateRefused(
            f"{audience}.{key} references {exc} which is not supplied; add it to `requires:` so the "
            f"omission fails at load rather than at render"
        ) from exc


# --------------------------------------------------------------------------- security


def render_security(
    placement: BenchmarkPlacement, cfg: BenchmarkingConfig | None = None
) -> list[str]:
    """Per-domain comparison, worst gap first.

    Skips two classes of domain deliberately:
      * SUPPRESSED ones, where the domain does not vary across the cohort — a line saying a supplier
        is behind peers on a control every peer also fails is simply false, and the fact is carried
        in the placement's caveats instead;
      * domains where the supplier is AT or ABOVE the median and the cohort is unremarkable, because
        a security reader's list is a worklist and a matched control is not work.
    """
    cfg = cfg or get_benchmarking_config()
    lines: list[str] = []

    for dp in placement.domains:
        p = dp.placement
        if dp.suppressed:
            continue
        try:
            if not p.sufficient:
                lines.append(render("security", "insufficient", {
                    "domain_label": dp.label,
                    "n": p.n,
                    "minimum": cfg.min_domain_n(),
                }, cfg))
                continue
            if p.direction in (None, "at", "above"):
                continue
            lines.append(render("security", "placed", {
                "domain_label": dp.label,
                "direction": p.direction,
                "cohort_label": _cohort_label(placement),
                "delta_abs": abs(p.delta_from_median) if p.delta_from_median is not None else None,
                "subject": p.subject,
                "median": p.median,
                "n": p.n,
            }, cfg))
        except TemplateRefused:
            # A domain we cannot describe correctly gets no sentence. The numbers are still on the
            # object for the UI to render; what is withheld is the CLAIM, not the data.
            continue

    return lines


# --------------------------------------------------------------------------- procurement


def render_procurement(
    placement: BenchmarkPlacement, cfg: BenchmarkingConfig | None = None
) -> list[str]:
    """The placement, the rank, and what to do about it.

    The action comes from the deterministic `(placement x data_access_scope)` table — the one and only
    place `data_access_scope` enters the system, and it enters interpretation rather than the cohort
    key. Where no scope was supplied there is no recommendation, because an action chosen without
    knowing what the supplier can reach is a guess wearing a clause number.
    """
    cfg = cfg or get_benchmarking_config()
    p = placement.overall
    name = placement.supplier_name or placement.supplier_ref
    scope = placement.data_access_scope
    action = placement.action or (
        "No data access scope recorded — set it to receive a contracting recommendation."
    )

    lines: list[str] = []
    try:
        if not p.sufficient:
            lines.append(render("procurement", "insufficient", {
                "supplier": name,
                "n": p.n,
                "minimum": cfg.min_quartile_n(),
                "action": action,
            }, cfg))
        else:
            lines.append(render("procurement", "placed", {
                "supplier": name,
                "quartile_label": p.quartile_label,
                "cohort_label": _cohort_label(placement),
                "rank": _rank_phrase(p),
                "n": p.n,
                "action": action,
            }, cfg))
    except TemplateRefused:
        pass

    # The three qualifications procurement must not miss, in the order that matters.
    if placement.disputed:
        lines.append(
            "DISPUTED: this supplier has contested its cohort assignment and the dispute is open. "
            "Treat the placement as provisional until it is resolved."
        )
    if placement.confidence_flagged:
        lines.append(
            f"Limited observable data (confidence {placement.supplier_confidence}): the placement is "
            f"published but may be unreliable. Consider a security questionnaire to close the gap."
        )
    if p.percentile is None and p.sufficient:
        lines.append(
            f"Quartile only — {p.n} peers is below the {cfg.min_percentile_n()} needed before a "
            f"percentile carries meaning."
        )
    if placement.snapshot.is_synthetic:
        lines.append(cfg.synthetic_caveat())
    if scope is None:
        lines.append(
            "No data access scope recorded. Scope drives the contracting recommendation and is "
            "buyer-supplied — it never affects which peers this supplier is compared against."
        )

    return [line for line in lines if line]


# --------------------------------------------------------------------------- shared helpers


def _cohort_label(placement: BenchmarkPlacement) -> str:
    """A cohort described in words a reader can check against the dimensions on the card.

    Built from the resolved dimensions rather than the rung name, so *"technology companies of similar
    size"* can never describe a cohort that was actually widened to sector-only.
    """
    dims = placement.snapshot.dimensions
    parts: list[str] = []
    if dims.get("sector"):
        parts.append(dims["sector"].replace("_", " "))
    elif dims.get("sector_group"):
        parts.append(f"{dims['sector_group'].replace('_', ' ')} (related industries)")
    if dims.get("size_band"):
        parts.append(f"{dims['size_band']}-sized")
    if dims.get("delivery_model"):
        parts.append(dims["delivery_model"].replace("_", "-"))
    return " · ".join(parts) if parts else placement.snapshot.rung_label


def _rank_phrase(p: Any) -> str | None:
    """`rank_of_n` in words, with ties made explicit.

    Ties matter here more than anywhere: "17th of 34" reads as a precise position, and if sixteen
    suppliers share that score the reader is entitled to know before repeating it in a meeting.
    """
    if p.rank_of_n is None:
        return None
    if p.tied_with > 1:
        return f"{p.rank_of_n} (tied with {p.tied_with - 1} other supplier(s))"
    return str(p.rank_of_n)
