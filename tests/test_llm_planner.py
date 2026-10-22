"""
Test suite for LLM Planner Orchestrator, Math Engine, Tool Calling,
PII Scrubbing, and Graceful Fallback in TCWC-25 Calculator.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.plan_future import (
    PlanFutureRequest,
    PlanQuestionType,
    GoalBasis,
    ContributionMode
)
from app.services.math_engine import calculate_financial_projection
from app.services.llm_planner import LLMPlannerService, scrub_pii
from app.services.cache_service import plan_future_cache

client = TestClient(app)


def test_math_engine_expenses_mode():
    result = calculate_financial_projection(
        mode="EXPENSES",
        current_age=48,
        target_age=55,
        current_expense=40000.0,
        inflation_rate=0.06,
        product_key="equity_mf"
    )
    assert result["mode"] == "EXPENSES"
    assert result["tenure_years"] == 7
    assert result["tenure_months"] == 84
    # 40000 * (1.06)^7 = 60145.21
    assert abs(result["future_expense"] - 60145.21) < 1.0
    assert "60,145" in result["headline"]
    assert "At age 55, you may need" in result["headline"]
    assert "purchasing power" in result["real_purchasing_power_fine_print"]


def test_math_engine_required_investment_monthly():
    result = calculate_financial_projection(
        mode="REQUIRED_INVESTMENT",
        current_age=48,
        target_age=55,
        goal_amount=1000000.0,
        goal_basis="COST_TODAY",
        inflation_rate=0.06,
        product_key="equity_mf",
        existing_savings=100000.0,
        contribution_type="monthly"
    )
    assert result["mode"] == "REQUIRED_INVESTMENT"
    assert result["required_investment"] > 0
    assert "your today's investment will be" in result["headline"]
    assert result["future_value"] is not None
    assert result["breakdown"]["base_goal_amount"] == 1000000.0


def test_math_engine_required_investment_onetime():
    result = calculate_financial_projection(
        mode="REQUIRED_INVESTMENT",
        current_age=48,
        target_age=55,
        goal_amount=1000000.0,
        goal_basis="FUTURE_AMOUNT",
        inflation_rate=0.06,
        product_key="equity_mf",
        existing_savings=0.0,
        contribution_type="one_time"
    )
    assert result["mode"] == "REQUIRED_INVESTMENT"
    assert result["required_investment"] > 0
    assert "your today's investment will be" in result["headline"]
    assert result["future_value"] is not None


def test_math_engine_reach_when():
    result = calculate_financial_projection(
        mode="REACH_WHEN",
        current_age=30,
        goal_amount=1000000.0,
        goal_basis="COST_TODAY",
        inflation_rate=0.055,
        product_key="equity_mf",
        existing_savings=50000.0,
        monthly_contribution=15000.0
    )
    assert result["mode"] == "REACH_WHEN"
    assert result["projected_goal_age"] >= 30
    assert "You can reach your goal in" in result["headline"]


def test_pii_redaction():
    text_with_pii = (
        "Client PAN is ABCDE1234F. Email is client.vip@investor.in. "
        "Phone number is +91 9876543210 and Aadhaar 1234 5678 9012."
    )
    scrubbed = scrub_pii(text_with_pii)
    assert "ABCDE1234F" not in scrubbed
    assert "[REDACTED_PAN]" in scrubbed
    assert "client.vip@investor.in" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "9876543210" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "1234 5678 9012" not in scrubbed
    assert "[REDACTED_AADHAAR]" in scrubbed


def test_direct_api_plan_future_route():
    # Verify the route works on /api/plan-future
    response = client.post(
        "/api/plan-future",
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


def test_llm_function_calling_mocked():
    """
    Tests the complete 4-step LLM function calling loop with a mocked OpenAI provider:
    1. Model returns tool call: calculate_financial_projection
    2. Python executes tool deterministically
    3. Tool output passed back to model
    4. Model returns certified structured response
    """
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_test_123"
    mock_tool_call.function.name = "calculate_financial_projection"
    mock_tool_call.function.arguments = (
        '{"mode": "EXPENSES", "current_age": 48, "target_age": 55, '
        '"current_expense": 40000.0, "inflation_rate": 0.06, "product_key": "equity_mf"}'
    )

    mock_msg_1 = MagicMock()
    mock_msg_1.tool_calls = [mock_tool_call]

    mock_choice_1 = MagicMock()
    mock_choice_1.message = mock_msg_1

    mock_resp_1 = MagicMock()
    mock_resp_1.choices = [mock_choice_1]

    mock_msg_2 = MagicMock()
    mock_msg_2.content = (
        '{"headline": "At age 55, you may need ₹ 60,145 each month", '
        '"subtitle": "Your estimate", '
        '"highlight_value": "₹ 60,145", '
        '"explanation_footnote": "To maintain similar purchasing power.", '
        '"disclaimer": "Illustration only · Returns are not guaranteed"}'
    )

    mock_choice_2 = MagicMock()
    mock_choice_2.message = mock_msg_2

    mock_resp_2 = MagicMock()
    mock_resp_2.choices = [mock_choice_2]

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [mock_resp_1, mock_resp_2]

    with patch("os.getenv", return_value="fake_openai_key"), \
         patch("openai.OpenAI", return_value=mock_client):
        req = PlanFutureRequest(
            profile_age=48,
            question_type=PlanQuestionType.EXPENSES_STATE_A,
            monthly_expenses_today=40000.0,
            target_age=55,
            inflation_rate=0.06
        )
        plan_future_cache.clear()
        res = LLMPlannerService.execute_plan(req)

        assert res.llm_generated is True
        assert res.target_age == 55
        assert "60,145" in res.headline
        assert res.model_name == "fake_openai_key" or "gpt" in str(res.model_name).lower() or res.model_name is not None
        assert mock_client.chat.completions.create.call_count == 2


def test_llm_fallback_on_network_failure():
    """
    Tests graceful degradation when LLM provider throws an exception (timeout / network error).
    The service must catch it and transparently fall back to the deterministic math engine.
    """
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("OpenAI connection timed out")

    with patch("os.getenv", return_value="fake_key"), \
         patch("openai.OpenAI", return_value=mock_client):
        req = PlanFutureRequest(
            profile_age=48,
            question_type=PlanQuestionType.EXPENSES_STATE_A,
            monthly_expenses_today=40000.0,
            target_age=55,
            inflation_rate=0.06
        )
        plan_future_cache.clear()
        res = LLMPlannerService.execute_plan(req)

        # Must not raise an error, gracefully fallback
        assert res.llm_generated is False
        assert res.target_age == 55
        assert "60,145" in res.headline
        assert res.raw_computed_value > 0
