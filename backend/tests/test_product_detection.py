"""Tests for product vs vendor detection module."""

import pytest

from app.product_detection import (
    add_product_mapping,
    detect_product,
    get_vendor_domain_for_product,
    should_block_scoring,
)


def test_detect_known_product_jira():
    """Test detection of known product Jira."""
    result = detect_product("jira.com")
    assert result.is_product is True
    assert result.company_domain == "atlassian.com"
    assert result.product_name == "Jira"
    assert result.confidence == "high"


def test_detect_known_company_atlassian():
    """Test detection of known company Atlassian."""
    result = detect_product("atlassian.com")
    assert result.is_product is False
    assert result.company_domain == "atlassian.com"
    assert result.confidence == "high"


def test_detect_effectiverm_products():
    """Test detection of EffectiveRM products."""
    # RiskBridge
    result = detect_product("riskbridge.io")
    assert result.is_product is True
    assert result.company_domain == "effectiverm.com"
    assert result.product_name == "RiskBridge"
    
    # MaturityOne
    result = detect_product("maturityone.io")
    assert result.is_product is True
    assert result.company_domain == "effectiverm.com"
    assert result.product_name == "MaturityOne"
    
    # WahidAI
    result = detect_product("wahidai.com")
    assert result.is_product is True
    assert result.company_domain == "effectiverm.com"
    assert result.product_name == "WahidAI"


def test_detect_known_company_effectiverm():
    """Test detection of EffectiveRM as company."""
    result = detect_product("effectiverm.com")
    assert result.is_product is False
    assert result.company_domain == "effectiverm.com"
    assert result.confidence == "high"


def test_detect_unknown_domain():
    """Test detection of unknown domain (treated as vendor)."""
    result = detect_product("unknown-vendor.com")
    assert result.is_product is False
    assert result.company_domain == "unknown-vendor.com"
    assert result.confidence == "low"


def test_should_block_scoring_product():
    """Test that product domains are blocked from scoring."""
    should_block, reason = should_block_scoring("jira.com")
    assert should_block is True
    assert reason is not None
    assert "Jira" in reason
    assert "atlassian.com" in reason


def test_should_not_block_scoring_vendor():
    """Test that vendor domains are not blocked."""
    should_block, reason = should_block_scoring("atlassian.com")
    assert should_block is False
    assert reason is None


def test_should_not_block_scoring_unknown():
    """Test that unknown domains are not blocked (low confidence)."""
    should_block, reason = should_block_scoring("some-company.com")
    assert should_block is False
    assert reason is None


def test_get_vendor_domain_for_product():
    """Test getting vendor domain for product."""
    vendor = get_vendor_domain_for_product("jira.com")
    assert vendor == "atlassian.com"
    
    vendor = get_vendor_domain_for_product("riskbridge.io")
    assert vendor == "effectiverm.com"


def test_get_vendor_domain_for_non_product():
    """Test getting vendor domain for non-product returns None."""
    vendor = get_vendor_domain_for_product("atlassian.com")
    assert vendor is None


def test_add_product_mapping():
    """Test adding a new product mapping."""
    # Add a new mapping
    add_product_mapping("newproduct.com", "newvendor.com", "NewProduct")
    
    # Verify it works
    result = detect_product("newproduct.com")
    assert result.is_product is True
    assert result.company_domain == "newvendor.com"
    assert result.product_name == "NewProduct"
    
    # Verify the company is recognized
    result = detect_product("newvendor.com")
    assert result.is_product is False
    assert result.company_domain == "newvendor.com"


def test_case_insensitivity():
    """Test that domain detection is case-insensitive."""
    result1 = detect_product("JIRA.COM")
    result2 = detect_product("jira.com")
    assert result1.company_domain == result2.company_domain
    assert result1.is_product == result2.is_product


def test_domain_normalization():
    """Test that domains are normalized (whitespace stripped)."""
    result = detect_product("  jira.com  ")
    assert result.is_product is True
    assert result.company_domain == "atlassian.com"
