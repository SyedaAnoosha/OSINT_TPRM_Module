"""Phase 2 — the evidence pack and the disclosures it must carry.

The exit criterion for the pack is not "it contains a lot of fields". It is that **a reader can
add the findings up and arrive at the number on the front**. A document that cannot do that is a
summary, and under Finding A a score that cannot be reconstructed from what was retained is the
thing this system exists not to produce. `test_pack_reconstructs_the_published_score` is that test.

The attribution tests exist because these lapsed once already: the disclosure block was written
into the scorecard as JSX and then commented out, taking the mandatory NVD notice with it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import app, store_dep
from app.disclosures import NVD_NOTICE
from app.models import CollectorResult, Vendor
from app.pipeline import run_pipeline
from app.scoring_config import get_scoring_config
from tests.test_corpus import load_fixture


@pytest.fixture
def client(store):
    app.dependency_overrides[store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
async def scored(store):
    """A real corpus vendor scored through the REAL pipeline into a temp store — collectors
    stubbed out, so the arithmetic is genuine but nothing touches the network."""
    vendor, results = load_fixture("atlassian")

    class _Stub:
        source = "fixture"
        on_demand = True

        def __init__(self, result: CollectorResult) -> None:
            self._r = result
            self.source = result.source

        async def collect(self, _vendor: Vendor, _ctx: object) -> CollectorResult:
            return self._r

    import app.pipeline as pipeline_mod

    original = pipeline_mod.all_collectors
    pipeline_mod.all_collectors = lambda: [_Stub(r) for r in results]
    try:
        await run_pipeline(vendor, store=store, criticality="high")
    finally:
        pipeline_mod.all_collectors = original
    return vendor.ref


# --------------------------------------------------------------------- the pack


async def test_pack_reconstructs_the_published_score(client, scored):
    """THE exit criterion. Every category's receipts must sum to its published penalty, and the
    formula must re-derive the published posture from those penalties."""
    pack = client.get(f"/api/vendors/{scored}/export").json()
    rec = pack["reconstruction"]

    assert rec["balances"] is True, "the receipts do not add up to the published score"
    for cat in rec["categories"]:
        assert cat["balances"], (
            f"{cat['category']}: receipts {cat['sum_of_receipts']} "
            f"!= published {cat['published_penalty']}"
        )

    # The overall arithmetic, re-run from the pack's own numbers.
    assert abs(rec["computed_posture"] - rec["published_posture"]) < 1.0
    assert rec["penalty_divisor"] == get_scoring_config().penalty_divisor()


async def test_pack_is_self_contained(client, scored):
    pack = client.get(f"/api/vendors/{scored}/export").json()
    for key in ("vendor_ref", "model_version", "profile", "score", "findings",
                "evidence_receipts", "reconstruction", "disclosures", "benchmark"):
        assert key in pack, f"evidence pack is missing {key!r}"
    assert pack["model_version"] == get_scoring_config().version


async def test_every_receipt_carries_a_verifiable_hash(client, scored):
    """The pack indexes receipts rather than inlining payloads — so each row must name the hash a
    reader can pull in full and re-verify against the store."""
    pack = client.get(f"/api/vendors/{scored}/export").json()
    assert pack["evidence_receipts"]
    for r in pack["evidence_receipts"]:
        assert r["content_hash"] and len(r["content_hash"]) == 64
        assert r["fetched_at"] and r["source"]


async def test_findings_carry_reason_and_action(client, scored):
    """A pack that says what is wrong but not what to do hands the reader the translation work."""
    pack = client.get(f"/api/vendors/{scored}/export").json()
    charged = [f for f in pack["findings"] if f["effective_penalty"] > 0]
    assert charged
    for f in charged:
        assert f["reason"], f"{f['signal']}.{f['band_key']} has no reason"
        assert f["action"], f"{f['signal']}.{f['band_key']} has no action"
        assert f["recheck_after"]


async def test_pack_carries_the_recommendation(client, scored):
    pack = client.get(f"/api/vendors/{scored}/export").json()
    rec = pack["score"]["recommendation"]
    assert rec and rec["decision"] and rec["advisory"] is True


async def test_pack_states_what_was_not_assessed(client, scored):
    """A pack that lists only what we found overstates what it is."""
    pack = client.get(f"/api/vendors/{scored}/export").json()
    items = {n["item"] for n in pack["disclosures"]["not_assessed"]}
    assert any("DFAT" in i for i in items)
    assert any("ports" in i or "exposed services" in i for i in items)


def test_export_404s_before_a_score(client):
    assert client.get("/api/vendors/nobody/export").status_code == 404


# --------------------------------------------------------------------- obligations


def test_nvd_notice_is_present_verbatim(client):
    """Required wording. It lapsed once already, when the disclosure block was commented out of
    the scorecard — hence a test rather than a comment."""
    notices = [a["notice"] for a in client.get("/api/disclosures").json()["attribution"]]
    assert NVD_NOTICE in notices
    assert NVD_NOTICE == "This product uses the NVD API but is not endorsed or certified by the NVD."


def test_hibp_attribution_names_its_licence(client):
    attribution = client.get("/api/disclosures").json()["attribution"]
    hibp = next(a for a in attribution if "Pwned" in a["source"])
    assert "CC BY 4.0" in hibp["notice"]
    assert "haveibeenpwned.com" in hibp["url"]


def test_every_attribution_entry_has_a_notice_and_a_url(client):
    for a in client.get("/api/disclosures").json()["attribution"]:
        assert a["notice"].strip() and a["url"].startswith("http")


def test_structural_limits_are_published(client):
    """These do not close with more sources, and a record that omits them overstates itself."""
    titles = " ".join(x["title"] for x in client.get("/api/disclosures").json()["limits"])
    assert "Coverage tracks size" in titles
    assert "Perimeter" in titles
    assert "Absence of evidence" in titles


async def test_card_and_pack_read_the_same_disclosures(client, scored):
    """One source of truth. Drift between the card and the file in the procurement folder is how
    an obligation gets met in one place and not the other."""
    served = client.get("/api/disclosures").json()
    in_pack = client.get(f"/api/vendors/{scored}/export").json()["disclosures"]
    assert served == in_pack
