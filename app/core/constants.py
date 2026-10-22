"""
Core constants and product definitions for TCWC-25 Financial Calculator.
"""

from typing import Dict, Any

# Predefined investment products as per TCWC-25 requirements
INVESTMENT_PRODUCTS: Dict[str, Dict[str, Any]] = {
    "equity_mf": {
        "id": "equity_mf",
        "name": "Equity Mutual Funds",
        "category": "Market Linked - High Growth",
        "default_cagr": 0.12,  # 12.0%
        "compounding_frequency": 1,  # Annual compounding
        "compounding_label": "Annually",
        "risk_level": "High",
        "description": "Diversified equity portfolio geared for long-term wealth compounding beating inflation.",
        "tax_note": "Long-Term Capital Gains (LTCG) taxed at 12.5% above ₹1.25L exemption limit."
    },
    "hybrid_mf": {
        "id": "hybrid_mf",
        "name": "Hybrid / Balanced Advantage Funds",
        "category": "Market Linked - Balanced",
        "default_cagr": 0.10,  # 10.0%
        "compounding_frequency": 1,  # Annual compounding
        "compounding_label": "Annually",
        "risk_level": "Moderate",
        "description": "Blended equity-debt asset allocation dynamically rebalanced for capital preservation and growth.",
        "tax_note": "Taxation depends on equity allocation threshold (>65% treated as equity)."
    },
    "debt_mf": {
        "id": "debt_mf",
        "name": "Debt Mutual Funds",
        "category": "Fixed Income - Market Traded",
        "default_cagr": 0.07,  # 7.0%
        "compounding_frequency": 1,  # Annual compounding
        "compounding_label": "Annually",
        "risk_level": "Low to Moderate",
        "description": "Corporate bonds, sovereign securities, and money market instruments.",
        "tax_note": "Taxed as per investor's marginal income tax slab."
    },
    "fixed_deposit": {
        "id": "fixed_deposit",
        "name": "Bank Fixed Deposits (FD)",
        "category": "Guaranteed Return",
        "default_cagr": 0.068,  # 6.8%
        "compounding_frequency": 4,  # Quarterly compounding
        "compounding_label": "Quarterly",
        "risk_level": "Very Low",
        "description": "Scheduled commercial bank term deposit with RBI DICGC insurance up to ₹5 Lakhs.",
        "tax_note": "Interest added to total income and taxed at marginal slab rates with TDS.",
        "min_tenure_months": 3,
        "max_tenure_months": 120,  # 10 years maximum standard term
        "statutory_lock_in_months": 0
    },
    "ppf": {
        "id": "ppf",
        "name": "Public Provident Fund (PPF)",
        "category": "Government Guaranteed",
        "default_cagr": 0.071,  # 7.1%
        "compounding_frequency": 1,  # Annual compounding (monthly accrual)
        "compounding_label": "Annually",
        "risk_level": "Sovereign / Nil",
        "description": "15-year statutory government savings vehicle with EEE tax exemption status.",
        "tax_note": "Exempt-Exempt-Exempt (EEE) status; interest and maturity are completely tax-free.",
        "min_tenure_months": 180,  # 15 years
        "max_tenure_months": 600,
        "statutory_lock_in_months": 180  # 15-year statutory block
    },
    "custom": {
        "id": "custom",
        "name": "Custom Investment Portfolio",
        "category": "User Defined",
        "default_cagr": 0.08,  # 8.0%
        "compounding_frequency": 1,
        "compounding_label": "Annually",
        "risk_level": "Custom",
        "description": "User-defined portfolio return rate and compounding frequency.",
        "tax_note": "Custom tax assumptions apply.",
        "min_tenure_months": 1,
        "max_tenure_months": 600,
        "statutory_lock_in_months": 0
    }
}

# Trailing 5-year average CPI inflation in India (default)
DEFAULT_INFLATION_RATE = 0.055  # 5.5%
MIN_INFLATION_RATE = 0.0        # 0.0%
MAX_INFLATION_RATE = 0.30       # 30.0%

MIN_AGE = 0
MAX_AGE = 120
MAX_SEARCH_MONTHS = 600  # 50 years maximum search horizon for reverse goal calculation

# Engine & Rule Versioning
PRODUCT_RULES_VERSION = "2026.1"
PROMPT_VERSION = "v1.2"
DATA_VERSION = "cpi_mospi_combined_2024"

# Official 5-year MoSPI CPI-Combined Historical Benchmark Series
# Measured across 6 endpoint year index levels (Dec 2019 to Dec 2024)
# Formula: (CPI_end / CPI_start)^(1/5) - 1
OFFICIAL_CPI_BENCHMARK = {
    "source": "Ministry of Statistics and Programme Implementation (MoSPI), Government of India",
    "series": "All India Consumer Price Index - Combined (CPI-C, Base 2012=100)",
    "measurement_period": "December 2019 – December 2024 (5 Complete Calendar Years)",
    "index_points": [
        {"calendar_year": 2019, "month": "December", "index_level": 150.4},
        {"calendar_year": 2020, "month": "December", "index_level": 157.3},
        {"calendar_year": 2021, "month": "December", "index_level": 166.1},
        {"calendar_year": 2022, "month": "December", "index_level": 175.6},
        {"calendar_year": 2023, "month": "December", "index_level": 185.5},
        {"calendar_year": 2024, "month": "December", "index_level": 195.2},
    ],
    "cpi_start": 150.4,
    "cpi_end": 195.2,
    "annualized_5y_rate": 0.0535,  # (195.2 / 150.4)**(1/5) - 1 = 5.35%
    "annualized_5y_formatted": "5.35%",
    "benchmark_note": "Official trailing 5-year annualized CPI-Combined inflation rate. Read-only benchmark, strictly separate from user-editable scenario inflation assumption."
}
