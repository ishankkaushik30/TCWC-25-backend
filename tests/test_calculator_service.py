"""
Unit tests for FinancialCalculatorService.
Validates mathematical precision, edge cases, compounding frequencies, and purchasing power.
"""

import pytest
from app.models.schemas import CalculatorRequest, CalculationMode, ExpenseFrequency
from app.services.calculator_service import FinancialCalculatorService


def test_tenure_validation_equal_age():
    with pytest.raises(ValueError, match="must be strictly greater than current age"):
        CalculatorRequest(
            current_age=30,
            future_age=30,
            current_expenditure=50000
        )


def test_tenure_validation_negative_horizon():
    with pytest.raises(ValueError, match="must be strictly greater than current age"):
        CalculatorRequest(
            current_age=45,
            future_age=40,
            current_expenditure=50000
        )


def test_target_driven_mode_mathematical_precision():
    """
    Current Age: 30, Future Age: 40 -> N = 10
    Current Exp: ₹1,00,000
    Inflation: 5.5% (0.055)
    Product: Equity MF (12.0% annual)

    Future Exp = 100000 * (1.055)^10 = 100000 * 1.708144458 = ~1,70,814.45
    Growth Factor = (1.12)^10 = ~3.105848208
    Required Lumpsum = Future Exp / Growth Factor = 170814.4458 / 3.105848208 = ~54,997.68
    """
    req = CalculatorRequest(
        current_age=30,
        future_age=40,
        current_expenditure=100000,
        inflation_rate=0.055,
        product_id="equity_mf",
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)

    assert res.tenure_years == 10
    assert res.current_age == 30
    assert res.future_age == 40
    # Future expenditure check
    expected_future_exp = 100000 * (1.055 ** 10)
    assert pytest.approx(res.future_expenditure.raw, rel=1e-3) == round(expected_future_exp, 2)

    # Required lumpsum check
    expected_growth = 1.12 ** 10
    expected_lumpsum = expected_future_exp / expected_growth
    assert res.required_lumpsum is not None
    assert pytest.approx(res.required_lumpsum.raw, rel=1e-3) == round(expected_lumpsum, 2)

    # In target-driven mode, nominal corpus equals future expenditure target
    assert pytest.approx(res.projected_nominal_corpus.raw, rel=1e-3) == res.future_expenditure.raw

    # Real purchasing power of this maturity corpus should equal original current expenditure!
    assert pytest.approx(res.real_purchasing_power.raw, rel=1e-3) == 100000.0


def test_projection_mode_with_shortfall_and_surplus():
    """
    Current Age: 25, Future Age: 35 -> N = 10
    Current Exp: ₹5,00,000
    Inflation: 6% (0.06)
    Future Exp = 500000 * (1.06)^10 = 500000 * 1.7908477 = 895,423.85

    Case 1: Under-invested deposit P = ₹1,00,000 in Hybrid MF (10% annual)
    Nominal Corpus = 100000 * (1.10)^10 = 259,374.25
    Goal Gap / Shortfall = 895,423.85 - 259,374.25 = 636,049.60
    """
    req_shortfall = CalculatorRequest(
        current_age=25,
        future_age=35,
        current_expenditure=500000,
        inflation_rate=0.06,
        product_id="hybrid_mf",
        mode=CalculationMode.PROJECTION,
        existing_lumpsum=100000
    )
    res_shortfall = FinancialCalculatorService.calculate(req_shortfall)
    expected_corp = 100000 * (1.10 ** 10)
    expected_target = 500000 * (1.06 ** 10)

    assert pytest.approx(res_shortfall.projected_nominal_corpus.raw, rel=1e-3) == round(expected_corp, 2)
    assert pytest.approx(res_shortfall.goal_gap.raw, rel=1e-3) == round(expected_target - expected_corp, 2)
    assert res_shortfall.surplus.raw == 0.0
    assert res_shortfall.goal_achieved_percentage < 100.0

    # Case 2: Surplus deposit P = ₹500,000
    req_surplus = CalculatorRequest(
        current_age=25,
        future_age=35,
        current_expenditure=500000,
        inflation_rate=0.06,
        product_id="hybrid_mf",
        mode=CalculationMode.PROJECTION,
        existing_lumpsum=500000
    )
    res_surplus = FinancialCalculatorService.calculate(req_surplus)
    surplus_corp = 500000 * (1.10 ** 10)
    assert res_surplus.goal_gap.raw == 0.0
    assert pytest.approx(res_surplus.surplus.raw, rel=1e-3) == round(surplus_corp - expected_target, 2)
    assert res_surplus.goal_achieved_percentage > 100.0


def test_quarterly_compounding_fixed_deposit():
    """
    Fixed Deposit: 6.8% nominal rate compounded quarterly (m=4).
    Growth factor = (1 + 0.068 / 4)^(4 * N)
    Effective Annual Rate (EAR) = (1 + 0.068 / 4)^4 - 1 = (1.017)^4 - 1 = ~6.9753%
    """
    req = CalculatorRequest(
        current_age=30,
        future_age=35,  # N = 5 years
        current_expenditure=100000,
        product_id="fixed_deposit",
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)

    # Verify compounding frequency
    assert res.compounding_frequency == 4
    expected_ear = ((1.0 + (0.068 / 4)) ** 4) - 1.0
    assert pytest.approx(res.effective_annual_rate, rel=1e-4) == expected_ear

    # Verify 5-year growth factor
    expected_growth = (1.0 + (0.068 / 4)) ** (4 * 5)
    assert pytest.approx(res.wealth_multiplier, rel=1e-4) == round(expected_growth, 3)


def test_ppf_compounded_annually():
    """
    PPF: 7.1% compounded annually (m=1).
    """
    req = CalculatorRequest(
        current_age=30,
        future_age=45,  # N = 15 years (statutory PPF period)
        current_expenditure=150000,
        product_id="ppf",
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)

    assert res.compounding_frequency == 1
    assert pytest.approx(res.product_cagr, rel=1e-4) == 0.071
    expected_growth = (1.071) ** 15
    assert pytest.approx(res.wealth_multiplier, rel=1e-3) == round(expected_growth, 3)


def test_zero_inflation_edge_case():
    """
    Zero inflation: Future expenditure nominal must equal current expenditure.
    Real purchasing power must equal nominal corpus.
    """
    req = CalculatorRequest(
        current_age=30,
        future_age=40,
        current_expenditure=200000,
        inflation_rate=0.0,
        product_id="debt_mf",
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)

    assert res.inflation_multiplier == 1.0
    assert res.future_expenditure.raw == 200000.0
    assert res.inflation_cost_increase.raw == 0.0
    assert res.real_purchasing_power.raw == res.projected_nominal_corpus.raw
    assert res.purchasing_power_retention_pct == 100.0


def test_disclaimer_and_fine_print_content():
    """
    Functional Requirement 5: Formatted disclosure / disclaimer string.
    """
    req = CalculatorRequest(
        current_age=30,
        future_age=50,
        current_expenditure=1000000,
        inflation_rate=0.055,
        product_id="equity_mf",
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)

    disclaimer = res.fine_print_disclaimer
    assert "FINE PRINT DISCLOSURE" in disclaimer
    assert "Age 30 → 50" in disclaimer
    assert "5.5%" in disclaimer
    assert "purchasing power retained" in disclaimer


def test_yearly_trajectory_continuity():
    """
    Trajectory milestones must span from year 0 to year N inclusive.
    """
    req = CalculatorRequest(
        current_age=28,
        future_age=38,
        current_expenditure=120000,
        product_id="equity_mf",
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)

    assert len(res.yearly_trajectory) == 11
    # Year 0 milestone
    assert res.yearly_trajectory[0].year_offset == 0
    assert res.yearly_trajectory[0].age == 28
    assert res.yearly_trajectory[0].future_expenditure_nominal == 120000.0
    # Final year milestone
    assert res.yearly_trajectory[-1].year_offset == 10
    assert res.yearly_trajectory[-1].age == 38


def test_custom_product_with_monthly_compounding():
    """
    Custom product: 9.0% nominal rate compounded monthly (m=12).
    EAR = (1 + 0.09 / 12)^12 - 1 = (1.0075)^12 - 1 = ~9.3807%
    """
    req = CalculatorRequest(
        current_age=25,
        future_age=35,
        current_expenditure=50000,
        product_id="custom",
        custom_cagr=0.09,
        compounding_frequency=12,
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)
    assert res.compounding_frequency == 12
    expected_ear = ((1.0 + (0.09 / 12)) ** 12) - 1.0
    assert pytest.approx(res.effective_annual_rate, rel=1e-4) == expected_ear


def test_long_horizon_compounding_precision():
    """
    Long horizon: 40 years (Age 20 -> Age 60).
    Verifies no float overflow or instability over 40 years.
    """
    req = CalculatorRequest(
        current_age=20,
        future_age=60,
        current_expenditure=1000000,
        inflation_rate=0.06,
        product_id="equity_mf",
        mode=CalculationMode.TARGET_DRIVEN
    )
    res = FinancialCalculatorService.calculate(req)
    assert res.tenure_years == 40
    assert len(res.yearly_trajectory) == 41
    # 40-year inflation factor: (1.06)^40 = ~10.2857
    assert pytest.approx(res.inflation_multiplier, rel=1e-3) == round(1.06 ** 40, 3)

