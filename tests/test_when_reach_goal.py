"""
Unit and integration tests for the /api/v1/calculator/when-reach-goal endpoint.
Tests discrete monthly compounding, month-end timing, inflation adjustments,
and limit boundaries.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.when_reach_goal import WhenReachGoalRequest
from app.services.math_engine import calculate_when_reach_goal

client = TestClient(app)


def test_when_reach_goal_success_month_41():
    # Benchmark: Goal 10L, Existing 2L, Monthly 20k, 6% inflation, 10% return
    req = WhenReachGoalRequest(
        current_age=48,
        goal_basis="COST_TODAY",
        target_amount=1000000.0,
        existing_savings=200000.0,
        contribution_mode="MONTHLY",
        monthly_investment=20000.0,
        one_time_investment=0.0,
        assumed_annual_return=0.10,
        assumed_annual_inflation=0.06
    )
    res = calculate_when_reach_goal(req)
    assert res.status == "SUCCESS"
    assert res.total_months == 41
    assert res.years == 3
    assert res.months == 5
    assert res.projected_goal_age == 51
    assert round(res.final_corpus) == 1242407
    assert round(res.final_target) == 1220286
    assert round(res.total_invested) == 1020000
    assert round(res.estimated_growth) == 222407
    assert res.assumptions_used["goal_basis"] == "COST_TODAY"
    assert res.assumptions_used["annual_return"] == 0.10
    assert res.assumptions_used["annual_inflation"] == 0.06
    assert len(res.source_references) > 0


def test_when_reach_goal_api_endpoint_success():
    payload = {
        "current_age": 48,
        "goal_basis": "COST_TODAY",
        "target_amount": 1000000.0,
        "existing_savings": 200000.0,
        "contribution_mode": "MONTHLY",
        "monthly_investment": 20000.0,
        "one_time_investment": 0.0,
        "assumed_annual_return": 0.10,
        "assumed_annual_inflation": 0.06
    }
    response = client.post("/api/v1/calculator/when-reach-goal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["total_months"] == 41
    assert data["years"] == 3
    assert data["months"] == 5
    assert data["projected_goal_age"] == 51
    assert round(data["final_corpus"]) == 1242407
    assert round(data["final_target"]) == 1220286
    assert round(data["total_invested"]) == 1020000


def test_when_reach_goal_unreachable_within_limit():
    req = WhenReachGoalRequest(
        current_age=30,
        goal_basis="COST_TODAY",
        target_amount=500000000.0,  # 50 Crore
        existing_savings=100.0,
        contribution_mode="MONTHLY",
        monthly_investment=100.0,
        assumed_annual_return=0.08,
        assumed_annual_inflation=0.06,
        max_search_months=600
    )
    res = calculate_when_reach_goal(req)
    assert res.status == "UNREACHABLE_WITHIN_LIMIT"
    assert res.total_months is None
    assert res.years is None
    assert res.months is None
    assert res.projected_goal_age is None
    assert any("50-year (600 months)" in w for w in res.warnings)


def test_when_reach_goal_invalid_input_zero_savings_and_contrib():
    req = WhenReachGoalRequest(
        current_age=48,
        target_amount=1000000.0,
        existing_savings=0.0,
        contribution_mode="MONTHLY",
        monthly_investment=0.0
    )
    res = calculate_when_reach_goal(req)
    assert res.status == "INVALID_INPUT"
    assert any("provide either existing savings" in w for w in res.warnings)


def test_when_reach_goal_future_amount_fixed():
    # Fixed target without inflation adjustment
    req = WhenReachGoalRequest(
        current_age=48,
        goal_basis="FUTURE_AMOUNT",
        target_amount=1000000.0,
        existing_savings=200000.0,
        contribution_mode="MONTHLY",
        monthly_investment=20000.0,
        assumed_annual_return=0.10,
        assumed_annual_inflation=0.06
    )
    res = calculate_when_reach_goal(req)
    assert res.status == "SUCCESS"
    assert res.final_target == 1000000.0
    # Fixed target is reached earlier than inflation-adjusted target (34 months vs 41 months)
    assert res.total_months < 41


def test_when_reach_goal_both_contribution_mode():
    req = WhenReachGoalRequest(
        current_age=48,
        goal_basis="COST_TODAY",
        target_amount=1000000.0,
        existing_savings=100000.0,
        contribution_mode="BOTH",
        one_time_investment=100000.0,  # total lump sum P = 200,000
        monthly_investment=20000.0,
        assumed_annual_return=0.10,
        assumed_annual_inflation=0.06
    )
    res = calculate_when_reach_goal(req)
    assert res.status == "SUCCESS"
    assert res.total_months == 41
    assert round(res.total_invested) == 1020000


def test_when_reach_goal_new_payload_contract():
    # Tests amount_invested_today and monthly_contribution parameters directly
    payload = {
        "current_age": 48,
        "goal_basis": "COST_TODAY",
        "target_amount": 1000000.0,
        "amount_invested_today": 200000.0,
        "contribution_mode": "MONTHLY",
        "monthly_contribution": 20000.0,
        "assumed_annual_return": 0.10,
        "assumed_annual_inflation": 0.06
    }
    response = client.post("/api/v1/calculator/when-reach-goal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["total_months"] == 41
    assert data["years"] == 3
    assert data["months"] == 5
    assert data["projected_goal_age"] == 51
    assert round(data["final_corpus"]) == 1242407
    assert round(data["total_invested"]) == 1020000


def test_when_reach_goal_already_reached():
    # If initial capital P >= target_amount, status is GOAL_ALREADY_REACHED
    payload = {
        "current_age": 48,
        "goal_basis": "COST_TODAY",
        "target_amount": 500000.0,
        "amount_invested_today": 600000.0,
        "contribution_mode": "ONE_TIME",
        "assumed_annual_return": 0.10,
        "assumed_annual_inflation": 0.06
    }
    response = client.post("/api/v1/calculator/when-reach-goal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "GOAL_ALREADY_REACHED"
    assert data["years"] == 0
    assert data["months"] == 0
    assert data["total_months"] == 0
    assert data["projected_goal_age"] == 48
    assert data["final_corpus"] == 600000.0


def test_when_reach_goal_one_time_mode():
    # Solves when a pure one-time lump sum compounds to reach inflated target
    payload = {
        "current_age": 30,
        "goal_basis": "COST_TODAY",
        "target_amount": 1000000.0,
        "amount_invested_today": 800000.0,
        "contribution_mode": "ONE_TIME",
        "assumed_annual_return": 0.12,
        "assumed_annual_inflation": 0.06
    }
    response = client.post("/api/v1/calculator/when-reach-goal", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["total_months"] is not None
    assert data["total_invested"] == 800000.0

