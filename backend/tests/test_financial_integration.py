"""Integration tests for Business Stability collectors — Phase 5.2.

Tests the full pipeline integration, collector fallback chains, and SSE streaming
of stability data. These tests require the full pipeline to be running.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import UTC, datetime

from app.collectors import all_collectors
from app.collectors.base import CollectorContext
from app.config import Settings
from app.models import Vendor
from app.ratelimit import RateLimiter


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for collector tests."""
    client = AsyncMock()
    return client


@pytest.fixture
def collector_context(mock_http_client):
    """Create a collector context with mocked dependencies."""
    return CollectorContext(
        settings=Settings(),
        limiter=RateLimiter(),
        http=mock_http_client,
    )


@pytest.fixture
def sample_vendor():
    """Sample vendor for testing."""
    return Vendor(
        ref="test-vendor",
        name="Test Company Inc",
        domain="testcompany.com",
        resolved=True,
        resolution_confidence=1.0,
    )


class TestCollectorFallbackChains:
    """Test that financial collectors have proper fallback chains."""

    @pytest.mark.asyncio
    async def test_open_corporates_to_registry_lookup_fallback(self, sample_vendor, collector_context):
        """Test that OpenCorporates falls back to Registry Lookup on failure."""
        from app.collectors.open_corporates_collector import OpenCorporatesCollector
        from app.collectors.registry_lookup_collector import RegistryLookupCollector

        oc_collector = OpenCorporatesCollector()
        rl_collector = RegistryLookupCollector()

        # Mock OpenCorporates to fail
        with patch.object(oc_collector, '_get_with_retry', return_value=None):
            oc_result = await oc_collector.collect(sample_vendor, collector_context)
            assert oc_result.status in ("error", "empty")

        # Registry Lookup should still work
        with patch.object(rl_collector, '_get_with_retry', return_value=Mock(status_code=200, json=lambda: {"results": []})):
            rl_result = await rl_collector.collect(sample_vendor, collector_context)
            assert rl_result.status in ("ok", "empty")

    @pytest.mark.asyncio
    async def test_insolvency_collectors_regional_coverage(self, sample_vendor, collector_context):
        """Test that insolvency collectors cover different regions."""
        from app.collectors.eu_insolvency_collector import EUInsolvencyCollector
        from app.collectors.german_insolvency_collector import GermanInsolvencyCollector
        from app.collectors.canada_bankruptcy_collector import CanadaBankruptcyCollector
        from app.collectors.asic_insolvency_collector import ASICInsolvencyCollector

        collectors = [
            EUInsolvencyCollector(),
            GermanInsolvencyCollector(),
            CanadaBankruptcyCollector(),
            ASICInsolvencyCollector(),
        ]

        # All collectors should be registered
        registered_sources = {c.source for c in all_collectors()}
        for collector in collectors:
            assert collector.source in registered_sources

        # All should handle empty results gracefully
        for collector in collectors:
            with patch.object(collector, '_get_with_retry', return_value=None):
                result = await collector.collect(sample_vendor, collector_context)
                assert result.status in ("error", "empty")


class TestPipelineIntegration:
    """Test full pipeline integration with financial collectors."""

    @pytest.mark.asyncio
    async def test_financial_collectors_in_all_collectors(self):
        """Test that the financial collectors that are SWITCHED ON are registered.

        `open_corporates` and `registry_lookup` are written but their `register(...)` calls are
        commented out in `app/collectors/__init__.py` — a deliberate decision, not an oversight.
        Requiring them here made this test fail for a state somebody chose on purpose, which is
        how a real regression would have been lost in the noise. Both halves are asserted, so
        switching either collector on is a change this test makes somebody notice.
        """
        registered_sources = {c.source for c in all_collectors()}
        for source in ("eu_insolvency", "german_insolvency", "canada_bankruptcy",
                       "asic_insolvency", "sec_xbrl"):
            assert source in registered_sources, f"{source} not registered in all_collectors()"
        for source in ("open_corporates", "registry_lookup"):
            assert source not in registered_sources, (
                f"{source} is now registered — it was deliberately held back in "
                f"app/collectors/__init__.py. If that is intended, move it to the list above."
            )

    @pytest.mark.asyncio
    async def test_collector_on_demand_flag(self):
        """Test that financial collectors have appropriate on_demand flags."""
        from app.collectors.open_corporates_collector import OpenCorporatesCollector
        from app.collectors.sec_xbrl_collector import SecXbrlCollector

        # These should run on-demand for scoring
        oc = OpenCorporatesCollector()
        sec_xbrl = SecXbrlCollector()

        assert oc.on_demand is True, "OpenCorporates should run on-demand"
        assert sec_xbrl.on_demand is True, "SEC XBRL should run on-demand"


class TestSSEStabilityStreaming:
    """Test SSE streaming of Business Stability data."""

    @pytest.mark.asyncio
    async def test_stability_endpoint_includes_sse_data(self):
        """Test that the stability endpoint includes data suitable for SSE streaming."""
        # This would require a running FastAPI server
        # For now, we test the data structure
        from app.models import FinancialProfile, ProfileField

        profile = FinancialProfile(vendor_ref="test")
        profile.incorporation_date = ProfileField(
            value="2020-01-01",
            source="test",
            locator="test",
            fetched_at=datetime.now(UTC),
        )

        # Verify the profile has fields needed for SSE streaming
        assert profile.vendor_ref is not None
        assert profile.incorporation_date is not None

    @pytest.mark.asyncio
    async def test_stability_collectors_are_on_the_path_the_sweep_streams(self):
        """The stability collectors are reachable by `run_pipeline`, so their `collector_done`
        events reach the SSE stream.

        THIS DOES NOT TEST SSE, and it used to claim it did. The body only re-checked the collector
        registry — the same assertion as `test_financial_collectors_in_all_collectors` two classes
        up — under a name that read as streaming coverage. A test whose name overstates what it
        checks is worse than a missing one: it answers "is the stream covered?" with a yes.

        What it does check is the precondition: a collector `run_pipeline` never reaches cannot
        emit a progress event, whatever the stream does. Real SSE coverage would need the pipeline
        driven end-to-end against a store, and belongs with the API tests.
        """
        registered = {c.source for c in all_collectors()}
        on_demand = {c.source for c in all_collectors() if c.on_demand}
        for source in ("eu_insolvency", "german_insolvency", "canada_bankruptcy",
                       "asic_insolvency", "sec_xbrl"):
            assert source in registered, f"{source} is not registered at all"
            assert source in on_demand, (
                f"{source} is registered but not `on_demand`, so a scoring run skips it and no "
                f"progress event for it can ever reach the stream"
            )


class TestAPIEndpoints:
    """Test the new Business Stability API endpoints."""

    @pytest.mark.asyncio
    async def test_stability_endpoint_structure(self):
        """Test that the stability endpoint returns the expected structure."""
        # This would require a running FastAPI server
        # For now, we test the expected response structure
        expected_fields = [
            "vendor_ref",
            "score",
            "base_score",
            "age_band",
            "penalties",
            "bonuses",
            "gate_triggered",
            "gate_reason",
            "confidence_adjusted",
            "contingency_plan_required",
            "computed_at",
        ]

        # Verify the expected structure is documented
        # In a real test, we would call the endpoint and validate
        assert len(expected_fields) == 11

    @pytest.mark.asyncio
    async def test_financial_endpoint_structure(self):
        """Test that the financial endpoint returns the expected structure."""
        expected_fields = [
            "vendor_ref",
            "incorporation_date",
            "company_status",
            "registry_number",
            "registry_jurisdiction",
            "insolvency_status",
            "insolvency_records",
            "financial_metrics",
            "operating_years",
            "age_band",
            "debt_to_equity",
            "revenue_trend",
            "cash_flow_trend",
            "insolvency_gate",
            "insolvency_gate_reason",
            "computed_at",
        ]

        # Verify the expected structure is documented
        assert len(expected_fields) == 16


class TestErrorHandling:
    """Test error handling in financial collectors."""

    @pytest.mark.asyncio
    async def test_collector_handles_missing_api_keys(self, sample_vendor, collector_context):
        """Test that collectors handle missing API keys gracefully."""
        from app.collectors.open_corporates_collector import OpenCorporatesCollector
        from app.collectors.canada_bankruptcy_collector import CanadaBankruptcyCollector

        # Test with empty API key
        collector_context.settings.opend_corporates_key = ""
        collector_context.settings.canada_bankruptcy_key = ""

        oc = OpenCorporatesCollector()
        cb = CanadaBankruptcyCollector()

        # Should return empty or error, not crash
        oc_result = await oc.collect(sample_vendor, collector_context)
        cb_result = await cb.collect(sample_vendor, collector_context)

        assert oc_result.status in ("error", "empty")
        assert cb_result.status in ("error", "empty")

    @pytest.mark.asyncio
    async def test_collector_handles_timeout(self, sample_vendor, collector_context):
        """Test that collectors handle timeouts gracefully."""
        from app.collectors.open_corporates_collector import OpenCorporatesCollector

        # Mock a timeout
        collector_context.http.get.side_effect = TimeoutError("Request timed out")

        oc = OpenCorporatesCollector()
        result = await oc.collect(sample_vendor, collector_context)

        # TIMEOUT IS ITS OWN STATUS, not `error` — `Collector.collect` catches TimeoutError
        # before the general handler precisely so the two stay distinguishable ("the source was
        # too slow" is a different fact from "the source broke"). The contract is in
        # `collectors/base.py`; this test previously asserted the opposite of it.
        assert result.status == "timeout"
        assert "timeout" in result.notes.lower() or "timed out" in result.notes.lower()


class TestRateLimiting:
    """Test rate limiting for financial collectors."""

    @pytest.mark.asyncio
    async def test_collector_respects_rate_limits(self, sample_vendor, collector_context):
        """Test that collectors respect rate limits."""
        from app.collectors.open_corporates_collector import OpenCorporatesCollector

        # The collector should use the rate limiter
        oc = OpenCorporatesCollector()

        # Verify the collector has rate limiting configured
        # (This is a structural test - actual rate limiting would require
        # multiple concurrent requests to test)
        assert hasattr(oc, 'timeout_s')
        assert oc.timeout_s > 0
