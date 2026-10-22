"""
Unit tests for Indian Numbering System currency formatter.
"""

from app.services.formatters import format_inr_exact, format_inr_compact, format_percentage


def test_format_inr_exact_small_numbers():
    assert format_inr_exact(0) == "₹ 0"
    assert format_inr_exact(450) == "₹ 450"
    assert format_inr_exact(999) == "₹ 999"


def test_format_inr_exact_thousands_and_lakhs():
    assert format_inr_exact(1000) == "₹ 1,000"
    assert format_inr_exact(12500) == "₹ 12,500"
    assert format_inr_exact(100000) == "₹ 1,00,000"  # 1 Lakh
    assert format_inr_exact(1234567) == "₹ 12,34,567"  # 12.34 Lakhs
    assert format_inr_exact(10000000) == "₹ 1,00,00,000"  # 1 Crore
    assert format_inr_exact(250000000) == "₹ 25,00,00,000"  # 25 Crores


def test_format_inr_exact_decimals_and_negatives():
    assert format_inr_exact(123456.789, include_decimals=True) == "₹ 1,23,456.79"
    assert format_inr_exact(-50000) == "-₹ 50,000"


def test_format_inr_compact():
    assert format_inr_compact(500) == "₹ 500"
    assert format_inr_compact(1500) == "₹ 1.50 K"
    assert format_inr_compact(75000) == "₹ 75.00 K"
    assert format_inr_compact(100000) == "₹ 1.00 L"
    assert format_inr_compact(1250000) == "₹ 12.50 L"
    assert format_inr_compact(10000000) == "₹ 1.00 Cr"
    assert format_inr_compact(25400000) == "₹ 2.54 Cr"


def test_format_percentage():
    assert format_percentage(0.055) == "5.5%"
    assert format_percentage(0.12) == "12.0%"
    assert format_percentage(0.06975, decimals=2) == "6.98%"
