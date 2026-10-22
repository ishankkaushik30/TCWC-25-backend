"""
Enterprise test suite for Plan Your Future Calculation Engine,
Data Contracts, Caching Layer, and Boundary Validations.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import (
    PlanFutureRequest,
    PlanQuestionType,
    ContributionMode,
    GoalBasis,
    PlanFutureEnterpriseRequest,
    PlanCalculationMode,
    ScenarioInputs,
    ScenarioAssumptions,
    ScenarioMeta
)
from app.services.calculator_service import FinancialCalculatorService
from app.services.cache_service import plan_future_cache

client = TestClient(app)


def test_positive_expense_and_goal_validation():
    # Expenses must be > 0
    try:
        PlanFutureRequest(
            profile_age=30,
            question_type=PlanQuestionType.EXPENSES_STATE_A,
            monthly_expenses_today=0
        )
        assert False, "Should have raised ValueError on zero expenses"
    except ValueError as e:
        assert "strictly greater than 0" in str(e)

    # Goal amount must be > 0
    try:
        PlanFutureRequest(
            profile_age=30,
            question_type=PlanQuestionType.INVESTMENT_STATE_B,
            target_goal_amount=-50000
        )
        assert False, "Should have raised ValueError on negative goal"
    except ValueError as e:
        assert "strictly greater than 0" in str(e)


def test_reverse_mode_contribution_or_savings_validation():
    # Reverse mode without savings or contribution must fail
    try:
        PlanFutureRequest(
            profile_age=30,
            question_type=PlanQuestionType.REACH_GOAL_STATE_C,
            target_goal_amount=1000000,
            existing_savings=0,
            monthly_contribution=0,
            lump_sum_contribution=0
        )
        assert False, "Should have raised ValueError on reverse mode with zero savings and contributions"
    except ValueError as e:
        assert "must provide existing savings" in str(e)


def test_goal_basis_cost_today_vs_future_amount():
    # Cost Today: Inflation compounding applied to target
    req_today = PlanFutureRequest(
        profile_age=48,
        target_age=55,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        goal_basis=GoalBasis.COST_TODAY,
        target_goal_amount=1000000.0,
        inflation_rate=0.06,
        expected_cagr=0.10,
        investment_mode=ContributionMode.ONE_TIME
    )
    res_today = FinancialCalculatorService.calculate_plan_future(req_today)

    # Future Amount: 0% inflation compounding applied to target
    req_future = PlanFutureRequest(
        profile_age=48,
        target_age=55,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        goal_basis=GoalBasis.AMOUNT_IN_FUTURE,
        target_goal_amount=1000000.0,
        inflation_rate=0.06,
        expected_cagr=0.10,
        investment_mode=ContributionMode.ONE_TIME
    )
    res_future = FinancialCalculatorService.calculate_plan_future(req_future)

    # Cost Today effective target must be higher than Future Amount fixed target
    assert res_today.breakdown["effective_target_goal"] > res_future.breakdown["effective_target_goal"]
    assert res_future.breakdown["effective_target_goal"] == 1000000.0
    # 1,000,000 * (1.06)^7 = 1,503,630.26
    assert abs(res_today.breakdown["effective_target_goal"] - 1503630.26) < 1.0


def test_contribution_mode_both_and_distinct_p0_pnew():
    # Test that existing savings P_0 and new one-time P_new are distinct and compounded
    req = PlanFutureRequest(
        profile_age=40,
        target_age=50,
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        goal_basis=GoalBasis.AMOUNT_IN_FUTURE,
        target_goal_amount=5000000.0,
        existing_savings=1000000.0,      # P_0
        lump_sum_contribution=500000.0,  # P_new
        investment_mode=ContributionMode.BOTH,
        expected_cagr=0.10
    )
    res = FinancialCalculatorService.calculate_plan_future(req)
    breakdown = res.breakdown
    assert breakdown["existing_savings_p0"] == 1000000.0
    assert breakdown["one_time_contribution_pnew"] == 500000.0
    # P_0 and P_new both compound for 10 years at 10%
    assert breakdown["projected_existing_savings_fv"] > 1000000.0
    assert breakdown["projected_one_time_fv"] > 500000.0
    assert breakdown["required_investment"] > 0


def test_deterministic_caching_and_invalidation():
    plan_future_cache.clear()

    req = PlanFutureRequest(
        profile_age=48,
        target_age=55,
        question_type=PlanQuestionType.EXPENSES_STATE_A,
        monthly_expenses_today=45000.0,
        inflation_rate=0.06
    )

    # Run 1: Cache Miss
    res1 = FinancialCalculatorService.calculate_plan_future(req)
    assert res1.cached is False
    assert res1.scenario_hash is not None

    # Run 2: Exact same inputs -> Cache Hit
    res2 = FinancialCalculatorService.calculate_plan_future(req)
    assert res2.cached is True
    assert res2.scenario_hash == res1.scenario_hash

    # Run 3: Modify inflation rate -> Invalidation (different SHA-256 hash)
    req_modified = PlanFutureRequest(
        profile_age=48,
        target_age=55,
        question_type=PlanQuestionType.EXPENSES_STATE_A,
        monthly_expenses_today=45000.0,
        inflation_rate=0.07  # changed
    )
    res3 = FinancialCalculatorService.calculate_plan_future(req_modified)
    assert res3.cached is False
    assert res3.scenario_hash != res1.scenario_hash


def test_product_tenure_lock_in_warnings():
    # PPF with tenure < 15 years must include statutory warning
    req_ppf = PlanFutureRequest(
        profile_age=40,
        target_age=47,  # 7 years < 15 years
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        product_id="ppf",
        target_goal_amount=1000000.0
    )
    res_ppf = FinancialCalculatorService.calculate_plan_future(req_ppf)
    assert any("15 years" in w for w in res_ppf.warnings)

    # Fixed Deposit with tenure > 10 years must include reinvestment warning
    req_fd = PlanFutureRequest(
        profile_age=40,
        target_age=55,  # 15 years > 10 years
        question_type=PlanQuestionType.INVESTMENT_STATE_B,
        product_id="fixed_deposit",
        target_goal_amount=1000000.0
    )
    res_fd = FinancialCalculatorService.calculate_plan_future(req_fd)
    assert any("reinvestment" in w.lower() for w in res_fd.warnings)


def test_reverse_goal_search_limit_and_attainment():
    # Small monthly contribution toward huge goal hits 600 months limit with warning
    req_unreachable = PlanFutureRequest(
        profile_age=30,
        question_type=PlanQuestionType.REACH_GOAL_STATE_C,
        target_goal_amount=100000000.0,  # 10 Crores
        existing_savings=1000.0,
        monthly_contribution=100.0,      # Only ₹100/mo
        expected_cagr=0.08
    )
    res_unreachable = FinancialCalculatorService.calculate_plan_future(req_unreachable)
    assert res_unreachable.raw_computed_value == 600.0
    assert any("50 years" in w or "600 months" in w for w in res_unreachable.warnings)


def test_official_cpi_benchmark_and_cache_routes():
    # Benchmark API
    cpi_res = client.get("/api/v1/plan-future/cpi-benchmark")
    assert cpi_res.status_code == 200
    data = cpi_res.json()
    assert "MoSPI" in data["source"]
    assert len(data["index_points"]) == 6
    assert data["annualized_5y_rate"] == 0.0535

    # Cache Stats API
    stats_res = client.get("/api/v1/plan-future/cache/stats")
    assert stats_res.status_code == 200
    assert "active_cached_scenarios" in stats_res.json()


def test_enterprise_contract_endpoint():
    payload = {
        "mode": "EXPENSES_PROJECTION",
        "profile_version": "v1.0",
        "inputs": {
            "age": 48,
            "target_age": 55,
            "duration_months": 84,
            "goal_basis": "cost_today",
            "currency": "INR",
            "amounts": {
                "current_expenses": 40000.0
            },
            "contribution_timing": "beginning_of_period",
            "contribution_mode": "monthly",
            "product_id": "equity_mf"
        },
        "assumptions": {
            "inflation_rate": 0.06,
            "return_rates": {"cagr": 0.10, "compounding_frequency": 1},
            "product_rules_version": "2026.1"
        },
        "meta": {
            "prompt_version": "v1.2",
            "model": "deterministic_engine_v1",
            "data_version": "cpi_mospi_combined_2024"
        }
    }

    res = client.post("/api/v1/plan-future/enterprise", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["success", "warning"]
    assert "60,145" in data["outputs"]["formatted_headline"]
    assert len(data["source_references"]) >= 1
    assert data["source_references"][0]["rate"] == 0.0535
