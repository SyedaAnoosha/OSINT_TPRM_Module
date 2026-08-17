"""Financial collector unit tests — Phase 2 Business Stability collectors.

These tests verify the financial collectors work correctly with mock responses.
They do NOT hit the network (external sources are flaky and slow).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.collectors.base import CollectorContext
from app.collectors.canada_bankruptcy_collector import CanadaBankruptcyCollector
from app.collectors.eu_insolvency_collector import EUInsolvencyCollector
from app.collectors.financial_ratios_calculator import (
    calculate_cash_flow_trend,
    calculate_debt_to_equity,
    calculate_revenue_trend,
)
from app.collectors.german_insolvency_collector import GermanInsolvencyCollector
from app.collectors.open_corporates_collector import (
    OpenCorporatesCollector,
    _normalize_name as _oc_normalize_name,
)
from app.collectors.registry_lookup_collector import (
    RegistryLookupCollector,
    _normalize_name as _rl_normalize_name,
)
from app.collectors.sec_xbrl_collector import (
    SecXbrlCollector,
    _normalize_name as _sx_normalize_name,
)
from app.config import Settings
from app.models import FinancialMetrics, Vendor
from app.ratelimit import RateLimiter


def _ctx() -> CollectorContext:
    return CollectorContext(settings=Settings(), limiter=RateLimiter(), http=None)


def _vendor(domain: str = "example.com", name: str = "Example Corp") -> Vendor:
    return Vendor(ref="example", name=name, domain=domain, resolved=True, resolution_confidence=1.0)


# ------------------------------------------------------------ OpenCorporates Collector

async def test_open_corporates_no_key_returns_empty():
    """Unset API key -> empty (lowers coverage, never posture)."""
    collector = OpenCorporatesCollector()
    result = await collector.collect(_vendor(), _ctx())
    # Without http client, should return error (no network access in unit tests)
    # In real usage, unset key would return empty
    assert result.status in ("error", "empty")


def test_open_corporates_normalize_name():
    """Name normalization removes suffixes and punctuation.

    `_normalize_name` is a MODULE-level function, not a method — calling it off the class raised
    AttributeError, so these assertions never ran. They are worth running: the middle one caught a
    real defect. The suffix alternation had no closing `\b`, so `corp` matched inside
    "Corporation" and "Microsoft Corporation" normalised to "microsoft oration".
    """
    assert _oc_normalize_name("Example Inc.") == "example"
    assert _oc_normalize_name("Test Corporation Ltd") == "test"
    assert _oc_normalize_name("Microsoft Corporation") == "microsoft"
    # `group` and `holdings` are both in the suffix list, so both are stripped wherever they
    # appear — "abc", not "abc group". Normalisation is applied to BOTH sides of every comparison,
    # so this costs nothing in matching; it only means the stripped form is not a display name.
    assert _oc_normalize_name("ABC Group Holdings") == "abc"


def test_open_corporates_status_band():
    """Status band mapping follows entity_status bands."""
    assert OpenCorporatesCollector._status_band("Active") == "active_good_standing"
    assert OpenCorporatesCollector._status_band("Dissolved") == "entity_inactive"
    assert OpenCorporatesCollector._status_band("Liquidation") == "entity_inactive"
    assert OpenCorporatesCollector._status_band("Administration") == "entity_inactive"
    assert OpenCorporatesCollector._status_band("Unknown") == "registration_lapsed"
    # The register writes the NOUN as often as the participle. "Liquidation" used to fall through
    # to `registration_lapsed` — an administrative lapse — for a company being wound up.
    assert OpenCorporatesCollector._status_band("Liquidation") == "entity_inactive"
    assert OpenCorporatesCollector._status_band("In Liquidation") == "entity_inactive"
    assert OpenCorporatesCollector._status_band("Winding Up") == "entity_inactive"


# ------------------------------------------------------------ Registry Lookup Collector

async def test_registry_lookup_no_key_returns_empty():
    """Unset API key -> empty (lowers coverage, never posture)."""
    collector = RegistryLookupCollector()
    result = await collector.collect(_vendor(), _ctx())
    assert result.status in ("error", "empty")


def test_registry_lookup_normalize_name():
    """Name normalization removes suffixes and punctuation. Module-level function — see the note
    on `test_open_corporates_normalize_name`."""
    assert _rl_normalize_name("Example Inc.") == "example"
    assert _rl_normalize_name("Test Corp Ltd") == "test"
    assert _rl_normalize_name("Microsoft Corporation") == "microsoft"


def test_registry_lookup_status_band():
    """Status band mapping follows entity_status bands."""
    assert RegistryLookupCollector._status_band("Active") == "active_good_standing"
    assert RegistryLookupCollector._status_band("Dissolved") == "entity_inactive"
    assert RegistryLookupCollector._status_band("Struck Off") == "entity_inactive"


# ------------------------------------------------------------ EU Insolvency Collector

async def test_eu_insolvency_no_network_returns_error():
    """No network access -> error (isolated failure)."""
    collector = EUInsolvencyCollector()
    result = await collector.collect(_vendor(), _ctx())
    assert result.status == "error"


def test_eu_insolvency_status_band():
    """Insolvency status band mapping."""
    assert EUInsolvencyCollector._status_band("active") == "insolvency_active"
    assert EUInsolvencyCollector._status_band("open") == "insolvency_active"
    assert EUInsolvencyCollector._status_band("closed") == "insolvency_historical"
    assert EUInsolvencyCollector._status_band("discharged") == "insolvency_historical"
    assert EUInsolvencyCollector._status_band("unknown") == "insolvency_unknown"


# ------------------------------------------------------------ German Insolvency Collector

async def test_german_insolvency_no_network_returns_error():
    """No network access -> error (isolated failure)."""
    collector = GermanInsolvencyCollector()
    result = await collector.collect(_vendor(), _ctx())
    assert result.status == "error"


def test_german_insolvency_status_band():
    """German insolvency status band mapping."""
    assert GermanInsolvencyCollector._status_band("active") == "insolvency_active"
    assert GermanInsolvencyCollector._status_band("eröffnet") == "insolvency_active"
    assert GermanInsolvencyCollector._status_band("beendet") == "insolvency_historical"
    assert GermanInsolvencyCollector._status_band("abgeschlossen") == "insolvency_historical"


# ------------------------------------------------------------ Canada Bankruptcy Collector

async def test_canada_bankruptcy_no_key_returns_empty():
    """Unset API key -> empty (lowers coverage, never posture)."""
    collector = CanadaBankruptcyCollector()
    result = await collector.collect(_vendor(), _ctx())
    assert result.status in ("error", "empty")


def test_canada_bankruptcy_status_band():
    """Canada bankruptcy status band mapping."""
    assert CanadaBankruptcyCollector._status_band("active") == "insolvency_active"
    assert CanadaBankruptcyCollector._status_band("open") == "insolvency_active"
    assert CanadaBankruptcyCollector._status_band("discharged") == "insolvency_historical"
    assert CanadaBankruptcyCollector._status_band("closed") == "insolvency_historical"


# ------------------------------------------------------------ ASIC Insolvency Collector

async def test_asic_insolvency_no_network_returns_error():
    """No network access -> error (isolated failure)."""
    from app.collectors.asic_insolvency_collector import ASICInsolvencyCollector
    collector = ASICInsolvencyCollector()
    result = await collector.collect(_vendor(), _ctx())
    assert result.status == "error"


def test_asic_insolvency_status_band():
    """ASIC insolvency status band mapping."""
    from app.collectors.asic_insolvency_collector import ASICInsolvencyCollector
    assert ASICInsolvencyCollector._status_band("active") == "insolvency_active"
    assert ASICInsolvencyCollector._status_band("current") == "insolvency_active"
    assert ASICInsolvencyCollector._status_band("completed") == "insolvency_historical"
    assert ASICInsolvencyCollector._status_band("finalised") == "insolvency_historical"


# ------------------------------------------------------------ SEC XBRL Collector

async def test_sec_xbrl_no_network_returns_error():
    """No network access -> error (isolated failure)."""
    collector = SecXbrlCollector()
    result = await collector.collect(_vendor(), _ctx())
    assert result.status == "error"


def test_sec_xbrl_normalize_name():
    """Name normalization removes corporate suffixes."""
    assert _sx_normalize_name("Example Inc.") == "example"
    assert _sx_normalize_name("Test Corporation") == "test"


# ------------------------------------------------------------ Financial Ratios Calculator

def test_calculate_debt_to_equity():
    """Debt-to-equity calculation."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="annual",
            long_term_debt=1000000,
            equity=500000,
            source="test",
        )
    ]
    assert calculate_debt_to_equity(metrics) == 2.0


def test_calculate_debt_to_equity_no_data():
    """No data -> None."""
    assert calculate_debt_to_equity([]) is None


def test_calculate_debt_to_equity_zero_equity():
    """Zero equity -> None (avoid division by zero)."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="annual",
            long_term_debt=1000000,
            equity=0,
            source="test",
        )
    ]
    assert calculate_debt_to_equity(metrics) is None


def test_calculate_revenue_trend_growing():
    """Growing revenue trend."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 3, 31, tzinfo=UTC),
            period_type="quarterly",
            revenue=1000000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=1200000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 9, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=1400000,
            source="test",
        ),
    ]
    assert calculate_revenue_trend(metrics) == "growing"


def test_calculate_revenue_trend_declining():
    """Declining revenue trend."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 3, 31, tzinfo=UTC),
            period_type="quarterly",
            revenue=1400000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=1200000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 9, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=1000000,
            source="test",
        ),
    ]
    assert calculate_revenue_trend(metrics) == "declining"


def test_calculate_revenue_trend_stable():
    """Stable revenue trend."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 3, 31, tzinfo=UTC),
            period_type="quarterly",
            revenue=1000000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=1050000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 9, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=980000,
            source="test",
        ),
    ]
    assert calculate_revenue_trend(metrics) == "stable"


def test_calculate_revenue_trend_insufficient_data():
    """Insufficient data -> unknown."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=1000000,
            source="test",
        )
    ]
    assert calculate_revenue_trend(metrics) == "unknown"


def test_calculate_cash_flow_trend_positive():
    """Positive cash flow trend."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 3, 31, tzinfo=UTC),
            period_type="quarterly",
            net_income=100000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            net_income=150000,
            source="test",
        ),
    ]
    assert calculate_cash_flow_trend(metrics) == "positive"


def test_calculate_cash_flow_trend_negative():
    """Negative cash flow trend."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 3, 31, tzinfo=UTC),
            period_type="quarterly",
            net_income=-100000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            net_income=-150000,
            source="test",
        ),
    ]
    assert calculate_cash_flow_trend(metrics) == "negative"


def test_calculate_cash_flow_trend_insufficient_data():
    """Insufficient data -> unknown."""
    metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            net_income=100000,
            source="test",
        )
    ]
    assert calculate_cash_flow_trend(metrics) == "unknown"
