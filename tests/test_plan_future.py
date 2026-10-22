"""
Tests for Plan Your Future mobile card backend calculations and routes.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import PlanFutureRequest, PlanQuestionType, InvestmentMode
from app.services.calculator_service import FinancialCalculatorService

client = TestClient(app)


def test_plan_future_state_a_expenses():
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.EXPENSES_STATE_A,
        monthly_expenses_today=40000.0,
        target_age=55,
        inflation_rate=0.06
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.profile_age == 48
    assert res.target_age == 55
    assert res.duration_years == 7
    # 40000 * (1.06)^7 = 40000 * 1.5036302589999998 = 60145.21
    assert "₹ 60,145" in res.headline or "60,145" in res.headline
    assert "At age 55, you may need" in res.headline
    assert res.subtitle == "Your estimate"
    assert "purchasing power" in res.explanation_footnote


def test_plan_future_state_b_investment_monthly():
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        target_goal_amount=1000000.0,
        existing_savings=100000.0,
        target_age=55,
        investment_mode=InvestmentMode.MONTHLY,
        expected_cagr=0.10
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.question_type == PlanQuestionType.INVESTMENT_STATE_B
    assert res.duration_years == 7
    assert res.raw_computed_value > 0
    assert "your today's investment will be" in res.headline
    assert res.future_value is not None


def test_plan_future_state_b_investment_onetime():
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        target_goal_amount=1000000.0,
        existing_savings=100000.0,
        target_age=55,
        investment_mode=InvestmentMode.ONE_TIME,
        expected_cagr=0.10
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.question_type == PlanQuestionType.INVESTMENT_STATE_B
    assert "your today's investment will be" in res.headline
    assert res.future_value is not None


def test_plan_future_state_b_pure_compounding_both_outputs():
    # Verify pure TVM formulas with effective monthly compounding:
    # Cost_today = 1,000,000, inflation = 6%, years = 7 -> Inflated Cost = 1,000,000 * (1.06)^7 = 1,503,630.26
    # Existing = 100,000, return_rate = 10% -> FV = 100,000 * (1.10)^7 = 194,871.71
    # Net Corpus Needed = 1,503,630.26 - 194,871.71 = 1,308,758.55
    # Monthly: r_m = (1.10)^(1/12) - 1 = 0.00797414, n = 84 -> PMT = 1,308,758.55 * (r_m / ((1+r_m)^84 - 1)) = ~11,000.41
    # One-time: PV = 1,308,758.55 / (1.10^7) = ~671,599.98
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        target_goal_amount=1000000.0,
        existing_savings=100000.0,
        target_age=55,
        inflation_rate=0.06,
        expected_cagr=0.10
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.monthly_amount is not None
    assert res.one_time_amount is not None
    assert abs(res.monthly_amount - 11000.41) < 2.0
    assert abs(res.one_time_amount - 671600.0) < 2.0
    assert abs(res.net_corpus_needed - 1308758.55) < 2.0

    # Ensure clean explanation and future compounded metrics
    assert "Compounded at" in res.explanation_footnote
    assert "expense today will cost" in res.explanation_footnote


def test_plan_future_state_b_pure_one_time_compounding_with_inflation():
    # Pure One-Time Compounding Tool with Inflation:
    # principal = 100,000, years = 7, return = 10%, inflation = 6%
    req = PlanFutureRequest(
        profile_age=48,
        target_age=55,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        principal=100000.0,
        years=7,
        annual_return=0.10,
        annual_inflation=0.06
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.future_value == 194872
    assert res.inflated_cost == 150363
    assert res.real_gain == 44509
    assert res.principal == 100000
    assert res.years == 7
    assert res.target_age == 55
    assert res.annual_return_pct == 10.0
    assert res.inflation_pct == 6.0
    assert "At age 55, your today's investment will be" in res.headline
    assert "₹ 1,94,872" in res.highlight_value
    assert "Compounded at 10.0% assumed return" in res.explanation_footnote
    assert "A ₹ 1,00,000 expense today will cost ₹ 1,50,363 then at 6.0% inflation" in res.explanation_footnote



def test_plan_future_state_b_production_alignment_exact_9362():
    # Production verification: Goal 10L, Existing 2L, 6% inflation, 10% return over 7 years (84 months)
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        target_goal_amount=1000000.0,
        existing_savings=200000.0,
        target_age=55,
        inflation_rate=0.06,
        expected_cagr=0.10
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert round(res.inflated_target_cost) == 1503630
    assert round(res.net_corpus_needed) == 1113887
    assert round(res.monthly_amount) == 9362
    assert round(res.one_time_amount) == 571600


def test_plan_future_state_b_future_compounded_value_verification():
    # existing_investment = 200,000, monthly_investment = 20,000, years = 7, return = 10%, inflation = 6%
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        existing_investment=200000.0,
        monthly_investment=20000.0,
        years=7,
        annual_return=0.10,
        inflation_rate=0.06
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.future_value == 2769228
    assert res.total_invested == 1880000
    assert res.estimated_gains == 889228
    assert res.inflated_benchmark == 2826825
    assert res.assumed_return_pct == 10.0
    assert res.inflation_pct == 6.0
    assert res.target_age == 55
    assert "At age 55, your today's investment will be" in res.headline


def test_plan_future_state_c_reach_goal():
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.REACH_GOAL_STATE_C,
        target_goal_amount=1000000.0,
        existing_savings=100000.0,
        monthly_contribution=15000.0,
        expected_cagr=0.10
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.question_type == PlanQuestionType.REACH_GOAL_STATE_C
    assert "You can reach your goal in" in res.headline
    assert res.raw_computed_value > 0


def test_plan_future_state_c_exact_solver_break_month_41():
    # Benchmark: Goal 10L, Existing 2L, Monthly 20k, 6% inflation, 10% return
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.REACH_GOAL_STATE_C,
        target_goal_amount=1000000.0,
        existing_savings=200000.0,
        monthly_contribution=20000.0,
        inflation_rate=0.06,
        expected_cagr=0.10
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.breakdown["months_needed"] == 41
    assert res.duration_years == 3
    assert res.duration_months == 5
    assert res.projected_age_years == 51
    assert res.projected_age_months == 5
    assert res.projected_savings == 1242407
    assert res.goal_cost_then == 1220286




def test_plan_future_api_endpoint():
    response = client.post(
        "/api/v1/plan-future",
        json={
            "profile_age": 48,
            "question_type": "expenses",
            "monthly_expenses_today": 40000.0,
            "target_age": 55,
            "inflation_rate": 0.06
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_age"] == 55
    assert "60,145" in data["headline"]
    assert data["subtitle"] == "Your estimate"


def test_plan_future_state_b_exact_1948717():
    # Target Age: 55, Current Age: 48 (Years = 7)
    # Principal = 10,00,000, Return = 10% (0.10), Inflation = 6% (0.06)
    # future_value = 19,48,717, inflated_cost = 15,03,630, net_advantage = 4,45,087
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        target_age=55,
        duration_years=7,
        principal=1000000.0,
        amount_invested_today=1000000.0,
        expected_cagr=0.10,
        inflation_rate=0.06
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.future_value == 1948717
    assert res.inflated_cost == 1503630
    assert res.net_advantage == 445087
    assert res.real_gain == 445087


def test_plan_future_state_b_exact_194872():
    # Target Age: 55, Current Age: 48 (Years = 7)
    # Principal = 1,00,000, Return = 10% (0.10), Inflation = 6% (0.06)
    # future_value = 1,94,872, inflated_cost = 1,50,363, net_advantage = 44,509
    req = PlanFutureRequest(
        profile_age=48,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        target_age=55,
        duration_years=7,
        principal=100000.0,
        amount_invested_today=100000.0,
        annual_return=0.10,
        annual_inflation=0.06
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    assert res.future_value == 194872
    assert res.inflated_cost == 150363
    assert res.net_advantage == 44509
    assert res.real_gain == 44509


