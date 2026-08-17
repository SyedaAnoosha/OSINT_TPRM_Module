"""Financial Ratios Calculator — Compute financial ratios from metrics.

This module calculates financial ratios (debt-to-equity, cash flow trends, etc.)
from raw financial metrics collected by other collectors. These ratios are used
in the Business Stability scoring model.

NOTE: This is a utility module, not a collector. It's called by the Business
Stability scoring engine to compute ratios from collected financial metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..models import FinancialMetrics


def calculate_debt_to_equity(metrics: list[FinancialMetrics]) -> float | None:
    """Calculate debt-to-equity ratio from the most recent financial metrics.

    Returns None if data insufficient.
    """
    if not metrics:
        return None

    # Get most recent metric
    latest = max(metrics, key=lambda m: m.period_end)

    long_term_debt = latest.long_term_debt
    equity = latest.equity

    if long_term_debt is None or equity is None or equity == 0:
        return None

    return long_term_debt / equity


def calculate_current_ratio(metrics: list[FinancialMetrics]) -> float | None:
    """Calculate current ratio (current assets / current liabilities).

    Returns None if data insufficient.
    """
    if not metrics:
        return None

    latest = max(metrics, key=lambda m: m.period_end)

    # Note: current assets and current liabilities would need to be extracted
    # from XBRL data - this is a placeholder for the calculation logic
    current_assets = getattr(latest, "current_assets", None)
    current_liabilities = getattr(latest, "current_liabilities", None)

    if current_assets is None or current_liabilities is None or current_liabilities == 0:
        return None

    return current_assets / current_liabilities


def calculate_revenue_trend(metrics: list[FinancialMetrics]) -> str:
    """Calculate revenue trend from time-series metrics.

    Returns: 'growing', 'stable', 'declining', or 'unknown'
    """
    if len(metrics) < 2:
        return "unknown"

    # Sort by period end (oldest first)
    sorted_metrics = sorted(metrics, key=lambda m: m.period_end)

    # Check last 3 periods for declining trend
    recent = sorted_metrics[-3:] if len(sorted_metrics) >= 3 else sorted_metrics

    revenues = [m.revenue for m in recent if m.revenue is not None]
    if len(revenues) < 2:
        return "unknown"

    # Simple trend: if each consecutive period is lower, it's declining
    declining_count = 0
    growing_count = 0
    for i in range(1, len(revenues)):
        if revenues[i] < revenues[i-1]:
            declining_count += 1
        elif revenues[i] > revenues[i-1]:
            growing_count += 1

    if declining_count == len(revenues) - 1:
        return "declining"
    if growing_count == len(revenues) - 1:
        return "growing"
    return "stable"


def calculate_cash_flow_trend(metrics: list[FinancialMetrics]) -> str:
    """Calculate cash flow trend from time-series metrics.

    Returns: 'positive', 'negative', or 'unknown'
    """
    if len(metrics) < 2:
        return "unknown"

    # Use net_income as proxy for cash flow (simplified)
    sorted_metrics = sorted(metrics, key=lambda m: m.period_end)
    recent = sorted_metrics[-2:]

    net_incomes = [m.net_income for m in recent if m.net_income is not None]
    if len(net_incomes) < 2:
        return "unknown"

    # If both recent periods are negative, it's negative trend
    if all(ni < 0 for ni in net_incomes):
        return "negative"
    if all(ni > 0 for ni in net_incomes):
        return "positive"
    return "unknown"


def calculate_profitability_margin(metrics: list[FinancialMetrics]) -> float | None:
    """Calculate profit margin (net income / revenue).

    Returns None if data insufficient.
    """
    if not metrics:
        return None

    latest = max(metrics, key=lambda m: m.period_end)

    net_income = latest.net_income
    revenue = latest.revenue

    if net_income is None or revenue is None or revenue == 0:
        return None

    return net_income / revenue


def calculate_working_capital(metrics: list[FinancialMetrics]) -> float | None:
    """Calculate working capital (current assets - current liabilities).

    Returns None if data insufficient.
    """
    if not metrics:
        return None

    latest = max(metrics, key=lambda m: m.period_end)

    current_assets = getattr(latest, "current_assets", None)
    current_liabilities = getattr(latest, "current_liabilities", None)

    if current_assets is None or current_liabilities is None:
        return None

    return current_assets - current_liabilities


def summarize_financial_health(metrics: list[FinancialMetrics]) -> dict[str, Any]:
    """Generate a summary of financial health from metrics.

    Returns a dict with key ratios and trends.
    """
    return {
        "debt_to_equity": calculate_debt_to_equity(metrics),
        "revenue_trend": calculate_revenue_trend(metrics),
        "cash_flow_trend": calculate_cash_flow_trend(metrics),
        "profitability_margin": calculate_profitability_margin(metrics),
        "current_ratio": calculate_current_ratio(metrics),
        "working_capital": calculate_working_capital(metrics),
        "metrics_count": len(metrics),
        "most_recent_period": max(m.period_end for m in metrics).isoformat() if metrics else None,
    }
