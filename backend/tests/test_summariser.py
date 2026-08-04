"""Summariser tests — the LLM read layer.

Locked-down invariants: it is inert when unconfigured, it calls an OpenAI-compatible endpoint,
it cites hash-stamped receipts, and it NEVER streams raw collector payloads out (bounded egress).
No network: an httpx.MockTransport stands in for the provider.
"""

from __future__ import annotations

import httpx
import pytest

from app import summariser
from app.config import Settings
from app.models import CategoryScore, Evidence, Score, utcnow


def _configured() -> Settings:
    return Settings(
        llm_base_url="https://provider.test/v1",
        llm_api_key="sk-test",
        llm_model="test/model-1",
        _env_file=None,
    )


def _unconfigured() -> Settings:
    # Explicit empties + no .env, so the test is hermetic even when a real .env has LLM keys.
    return Settings(llm_base_url="", llm_api_key="", llm_model="", _env_file=None)


def _score() -> Score:
    return Score(
        vendor_ref="acme",
        posture=78,
        grade="B",
        overall_confidence=0.71,
        confidence_band="Medium",
        categories=[
            CategoryScore(category="cyber_hygiene_technical", posture=80, grade="B", penalty=20.0,
                          coverage=0.9, findings=2, contributing_finding_ids=["f1"]),
        ],
    )


def _evidence() -> list[Evidence]:
    return [
        Evidence(
            id="e1", vendor_ref="acme", source="dns", status="ok", fetched_at=utcnow(),
            source_version=None, raw={"dmarc": "p=reject", "spf": "present", "dnssec": "valid"},
            reliability=0.9, notes=None, content_hash="a1b2c3d4e5f6g7h8",
        ),
        Evidence(
            id="e2", vendor_ref="acme", source="hibp", status="empty", fetched_at=utcnow(),
            source_version=None, raw={"breaches": []},
            reliability=0.95, notes="no known public breach", content_hash="99887766aabbccdd",
        ),
    ]


def test_available_reflects_config(monkeypatch):
    monkeypatch.setattr(summariser, "get_settings", _unconfigured)
    assert summariser.available() is False
    monkeypatch.setattr(summariser, "get_settings", _configured)
    assert summariser.available() is True


def test_context_includes_evidence_observations():
    """The digest must be about WHAT WAS FOUND — the actual observations, not just the numbers."""
    ctx, cited = summariser._build_context(_score(), _evidence())
    assert "a1b2c3d4" in ctx and "99887766" in ctx      # short hashes present
    assert "a1b2c3d4" in cited and "99887766" in cited
    assert "p=reject" in ctx and "dnssec=valid" in ctx  # the ACTUAL evidence is included
    assert "POSTURE: 78" in ctx and "CONFIDENCE" in ctx


def test_context_is_bounded_per_receipt():
    """A huge raw payload can't blow the prompt — each receipt's observations are capped."""
    big = Evidence(id="e", vendor_ref="acme", source="ct", status="ok", fetched_at=utcnow(),
                   source_version=None, raw={"subdomains": [f"x{i}.acme.com" for i in range(5000)]},
                   reliability=0.8, notes=None, content_hash="deadbeefdeadbeef")
    ctx, _ = summariser._build_context(_score(), [big])
    ct_line = [ln for ln in ctx.splitlines() if "[deadbeef]" in ln][0]
    assert len(ct_line) < summariser._RAW_PER_RECEIPT + 120  # capped, not the full 5000-item dump


@pytest.mark.asyncio
async def test_unavailable_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(summariser, "get_settings", _unconfigured)
    with pytest.raises(summariser.SummariserUnavailable):
        await summariser.summarise(_score(), _evidence())


@pytest.mark.asyncio
async def test_summarise_happy_path(monkeypatch):
    monkeypatch.setattr(summariser, "get_settings", _configured)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "test/model-1",
            "choices": [{"message": {"content": "Low risk on solid coverage (receipt a1b2c3d4)."}}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        out = await summariser.summarise(_score(), _evidence(), client=client)

    assert seen["url"] == "https://provider.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["model"] == "test/model-1"
    assert out["ai_generated"] is True
    assert "receipt a1b2c3d4" in out["summary"]
    assert out["cited_hashes"] == ["a1b2c3d4", "99887766"]


@pytest.mark.asyncio
async def test_provider_error_raises(monkeypatch):
    monkeypatch.setattr(summariser, "get_settings", _configured)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(summariser.SummariserError):
            await summariser.summarise(_score(), _evidence(), client=client)


@pytest.mark.asyncio
async def test_empty_summary_raises(monkeypatch):
    monkeypatch.setattr(summariser, "get_settings", _configured)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(summariser.SummariserError):
            await summariser.summarise(_score(), _evidence(), client=client)
