"""Entity-resolution tests — the system does NOT infer a domain from a name.

Most collectors are domain-specific, so guessing a domain would risk assessing the wrong
company. A name-only vendor keeps `domain=None`; the API answers with candidate domains for
the user to confirm (`domain_candidates`), and only a supplied domain is scored.
"""

from __future__ import annotations

from app.collectors import all_collectors
from app.collectors.gdelt_collector import GdeltCollector
from app.pipeline import domain_candidates, resolve_vendor


def test_domain_supplied_is_used_verbatim():
    v = resolve_vendor(domain="atlassian.com")
    assert v.domain == "atlassian.com"
    assert v.ref == "atlassian"


def test_name_only_does_not_infer_a_domain():
    """No guessing: a bare name leaves domain=None so the API can ask instead of assessing
    the wrong site."""
    v = resolve_vendor(name="Atlassian")
    assert v.domain is None
    assert v.ref == "atlassian"


def test_explicit_domain_with_name_is_used_verbatim():
    v = resolve_vendor(name="Atlassian", domain="team.atlassian.net")
    assert v.domain == "team.atlassian.net"


def test_domain_candidates_are_a_list_never_a_single_guess():
    cands = domain_candidates("Atlassian")
    assert "atlassian.com" in cands
    assert len(cands) > 1                       # a LIST to choose from, not one pick
    assert all(c.startswith("atlassian.") for c in cands)


def test_domain_candidates_slugify_punctuation_and_spaces():
    assert domain_candidates("O'Neil & Sons, Inc.")[0] == "oneilsonsinc.com"
    assert domain_candidates("My Company")[0] == "mycompany.com"
    assert domain_candidates("!!!") == []       # nothing slug-able -> no candidates


# ---- enrichment vs on-demand (GDELT is not in the hot scoring path) ----

def test_gdelt_is_enrichment_only_not_on_demand():
    """GDELT feeds a held/ai_adjudicated subcategory (0 score) and 429s hard — it must NOT run
    on every synchronous score. It is Phase 5 scheduled enrichment (include_enrichment=True)."""
    assert GdeltCollector.on_demand is False
    on_demand = [c.source for c in all_collectors() if c.on_demand]
    assert "gdelt" not in on_demand           # excluded from the default scoring run
    assert {"dns", "gleif", "hibp"} <= set(on_demand)  # scoring collectors still run


# --------------------------------------------------------------------- P5 · depth


def test_depth_narrows_collection_through_the_one_existing_seam():
    """P5's join. `run_pipeline` must filter the SAME collector list every run already builds —
    not maintain a second one. A parallel list is how a collector ends up running at one depth and
    not at another for no reason anybody wrote down."""
    import ast
    import inspect

    from app import pipeline

    src = inspect.getsource(pipeline.run_pipeline)
    tree = ast.parse(ast.unparse(ast.parse(src)))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "sources_for_depth" in called
    assert "all_collectors" in called
    # One list, filtered twice. Two `all_collectors()` calls would mean two lists.
    assert src.count("all_collectors()") == 1


def test_the_default_depth_is_unchanged_full_collection():
    """Every existing caller must be byte-for-byte unaffected: no score silently gets cheaper.
    A shallower run is a deliberate, per-relationship decision, never a default."""
    import inspect

    from app.pipeline import run_pipeline

    assert inspect.signature(run_pipeline).parameters["depth"].default is None


def test_screening_depth_skips_every_hygiene_collector():
    """The budget saving, stated as the set difference it actually is."""
    from app.assessment_depth import sources_for_depth

    on_demand = {c.source for c in all_collectors() if c.on_demand}
    screening = sources_for_depth("screening")
    assert screening is not None
    skipped = on_demand - screening
    assert {"tls", "headers", "dns", "ct", "nvd", "kev", "hibp"} <= skipped
    assert len(skipped) > len(screening & on_demand)
