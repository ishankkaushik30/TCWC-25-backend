"""
Pydantic v2 schemas for the Plan Your Future Calculator and LLM Orchestration Service.
"""

import uuid
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from app.core.constants import (
    DEFAULT_INFLATION_RATE,
    MIN_AGE,
    MAX_AGE,
    MIN_INFLATION_RATE,
    MAX_INFLATION_RATE,
    MAX_SEARCH_MONTHS,
    PRODUCT_RULES_VERSION,
    PROMPT_VERSION,
    DATA_VERSION
)


class PlanQuestionType(str, Enum):
    EXPENSES_STATE_A = "expenses"       # "What will my expenses be?"
    INVESTMENT_STATE_B = "investment"   # "How much should I invest?"
    REACH_GOAL_STATE_C = "reach_goal"   # "When can I reach my goal?"


class PlanCalculationMode(str, Enum):
    EXPENSES_PROJECTION = "EXPENSES_PROJECTION"
    REQUIRED_INVESTMENT = "REQUIRED_INVESTMENT"
    REVERSE_GOAL_AGE = "REVERSE_GOAL_AGE"


class GoalBasis(str, Enum):
    COST_TODAY = "cost_today"
    AMOUNT_IN_FUTURE = "future_amount"


class ContributionMode(str, Enum):
    MONTHLY = "monthly"
    ONE_TIME = "one_time"
    BOTH = "both"


class ContributionTiming(str, Enum):
    BEGINNING_OF_PERIOD = "beginning_of_period"
    END_OF_PERIOD = "end_of_period"


# Backwards compatibility alias
InvestmentMode = ContributionMode


class FinancialProjectionToolInput(BaseModel):
    mode: str = Field(..., description="Calculation mode: EXPENSES | REQUIRED_INVESTMENT | REACH_WHEN")
    current_age: int = Field(..., ge=MIN_AGE, le=MAX_AGE - 1)
    target_age: Optional[int] = Field(default=None, ge=MIN_AGE + 1, le=MAX_AGE)
    current_expense: float = Field(default=40000.0, gt=0)
    goal_amount: float = Field(default=1000000.0, gt=0)
    goal_basis: str = Field(default="COST_TODAY", description="COST_TODAY or FUTURE_AMOUNT")
    inflation_rate: float = Field(default=DEFAULT_INFLATION_RATE, ge=MIN_INFLATION_RATE, le=MAX_INFLATION_RATE)
    product_key: str = Field(default="equity_mf")
    existing_savings: float = Field(default=0.0, ge=0)
    contribution_type: str = Field(default="monthly", description="monthly | one_time | both")
    monthly_contribution: float = Field(default=0.0, ge=0)
    lump_sum_contribution: float = Field(default=0.0, ge=0)
    custom_cagr: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class FinancialProjectionToolOutput(BaseModel):
    mode: str
    future_expense: float
    required_investment: float
    nominal_maturity_corpus: float
    real_purchasing_power_fine_print: str
    tenure_months: int
    tenure_years: int
    projected_goal_age: int
    headline: str
    highlight_value: str
    subtitle: str
    explanation_footnote: str
    disclaimer: str
    warnings: List[str] = Field(default_factory=list)
    source_references: List[Dict[str, Any]] = Field(default_factory=list)
    breakdown: Dict[str, Any] = Field(default_factory=dict)
    method_summary: str


class PlanFutureRequest(BaseModel):
    profile_age: int = Field(default=48, description="User profile static baseline age")
    question_type: PlanQuestionType = Field(default=PlanQuestionType.EXPENSES_STATE_A)

    # Goal Basis handling
    goal_basis: GoalBasis = Field(default=GoalBasis.COST_TODAY, description="cost_today (applies inflation) or future_amount (fixed nominal)")

    # State A inputs
    monthly_expenses_today: Optional[float] = Field(default=40000.0, description="Monthly expense in today's money")
    target_age: Optional[int] = Field(default=55, ge=18, le=120)
    duration_years: Optional[int] = Field(default=7, ge=1, le=100)

    # State B & C inputs
    target_goal_amount: Optional[float] = Field(default=1000000.0, description="Target goal amount in INR")
    existing_savings: Optional[float] = Field(default=0.0, ge=0.0, description="Existing savings / current portfolio P_0")
    investment_mode: Optional[ContributionMode] = Field(default=ContributionMode.MONTHLY)
    monthly_contribution: Optional[float] = Field(default=10000.0, ge=0.0)
    lump_sum_contribution: Optional[float] = Field(default=0.0, ge=0.0, description="New one-time lump sum P_new")
    existing_investment: Optional[float] = Field(default=None, description="Existing lump sum investment")
    monthly_investment: Optional[float] = Field(default=None, description="Monthly SIP investment")
    principal: Optional[float] = Field(default=None, description="One-time principal amount invested today")
    amount_invested_today: Optional[float] = Field(default=None, description="Amount invested today")
    years: Optional[int] = Field(default=None, description="Investment tenure in years")
    annual_return: Optional[float] = Field(default=None, description="Annual expected return rate")
    annual_inflation: Optional[float] = Field(default=None, description="Annual inflation rate")

    # Investment product selection
    product_id: str = Field(default="equity_mf", description="Investment product key")

    # Shared assumptions
    inflation_rate: float = Field(default=0.06, ge=MIN_INFLATION_RATE, le=MAX_INFLATION_RATE)
    expected_cagr: float = Field(default=0.10, ge=0.0, le=0.50)

    # Enterprise & LLM metadata
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_hash: Optional[str] = None
    profile_version: str = Field(default="v1.0")
    notes: Optional[str] = Field(default=None, description="User notes (PII stripped and treated as data)")

    @model_validator(mode="after")
    def validate_plan_rules(self) -> "PlanFutureRequest":
        # Rule 1: Enforce positive expenses or goal amount
        if self.question_type == PlanQuestionType.EXPENSES_STATE_A:
            if self.monthly_expenses_today is not None and self.monthly_expenses_today <= 0:
                raise ValueError("Monthly expenses today must be strictly greater than 0.")
        else:
            if self.target_goal_amount is not None and self.target_goal_amount <= 0:
                raise ValueError("Target goal amount must be strictly greater than 0.")

        # Rule 2: For reverse mode (REACH_GOAL_STATE_C), enforce existing_savings > 0 OR planned contribution
        if self.question_type == PlanQuestionType.REACH_GOAL_STATE_C:
            existing = self.existing_savings or 0.0
            monthly = self.monthly_contribution or 0.0
            lumpsum = self.lump_sum_contribution or 0.0
            if existing <= 0 and monthly <= 0 and lumpsum <= 0:
                raise ValueError(
                    "For 'When can I reach my goal?', you must provide existing savings (> 0) "
                    "or a planned contribution (monthly or one-time lump sum > 0)."
                )

        # Rule 3: Enforce target_age > profile_age
        effective_target = self.target_age or (self.profile_age + (self.duration_years or 7))
        if effective_target <= self.profile_age:
            raise ValueError(
                f"Target age ({effective_target}) must be strictly greater than starting age ({self.profile_age})."
            )

        return self


class PlanFutureResponse(BaseModel):
    question_type: PlanQuestionType
    profile_age: int
    target_age: int
    duration_years: int
    subtitle: str
    headline: str
    highlight_value: str
    explanation_footnote: str
    disclaimer: str
    raw_computed_value: float
    breakdown: dict
    goal_basis: GoalBasis = GoalBasis.COST_TODAY
    warnings: List[str] = Field(default_factory=list)
    source_references: List[dict] = Field(default_factory=list)
    cached: bool = False
    scenario_hash: Optional[str] = None
    request_id: Optional[str] = None
    generated_at: Optional[str] = None
    llm_generated: bool = Field(default=False, description="Whether LLM reasoning generated the narrative")
    model_name: Optional[str] = None
    monthly_amount: Optional[float] = None
    one_time_amount: Optional[float] = None
    inflated_target_cost: Optional[float] = None
    net_corpus_needed: Optional[float] = None
    duration_months: Optional[int] = 0
    projected_age_years: Optional[int] = None
    projected_age_months: Optional[int] = None
    projected_savings: Optional[float] = None
    goal_cost_then: Optional[float] = None
    future_value: Optional[float] = None
    inflated_cost: Optional[float] = None
    real_gain: Optional[float] = None
    net_advantage: Optional[float] = None
    principal: Optional[float] = None
    amount_invested_today: Optional[float] = None
    years: Optional[int] = None
    total_invested: Optional[float] = None
    estimated_gains: Optional[float] = None
    inflated_benchmark: Optional[float] = None
    assumed_return_pct: Optional[float] = None
    annual_return_pct: Optional[float] = None
    inflation_pct: Optional[float] = None


# --- Strict Enterprise API Specifications ---

class ScenarioInputs(BaseModel):
    age: int = Field(..., ge=MIN_AGE, le=MAX_AGE - 1, description="Current / Starting baseline age")
    target_age: Optional[int] = Field(default=None, ge=MIN_AGE + 1, le=MAX_AGE)
    duration_months: int = Field(..., ge=1, le=MAX_SEARCH_MONTHS, description="Tenure in months (Target Age - Current Age) * 12")
    goal_basis: GoalBasis = Field(default=GoalBasis.COST_TODAY, description="Cost today vs Amount needed in the future")
    currency: str = Field(default="INR")
    amounts: Dict[str, float] = Field(
        default_factory=lambda: {
            "current_expenses": 40000.0,
            "target_goal": 1000000.0,
            "existing_savings": 0.0,
            "monthly_contribution": 10000.0,
            "one_time_contribution": 0.0
        }
    )
    contribution_timing: ContributionTiming = Field(default=ContributionTiming.BEGINNING_OF_PERIOD)
    contribution_mode: ContributionMode = Field(default=ContributionMode.MONTHLY)
    product_id: str = Field(default="equity_mf")
    custom_cagr: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ScenarioAssumptions(BaseModel):
    inflation_rate: float = Field(default=DEFAULT_INFLATION_RATE, ge=MIN_INFLATION_RATE, le=MAX_INFLATION_RATE)
    return_rates: Dict[str, Any] = Field(
        default_factory=lambda: {
            "cagr": 0.10,
            "compounding_frequency": 1
        }
    )
    product_rules_version: str = Field(default=PRODUCT_RULES_VERSION)


class ScenarioMeta(BaseModel):
    prompt_version: str = Field(default=PROMPT_VERSION)
    model: str = Field(default="llm_planner_v1")
    data_version: str = Field(default=DATA_VERSION)
    notes: Optional[str] = Field(default=None, description="Treated strictly as unparsed user metadata, never instructions")


class SourceReference(BaseModel):
    source: str
    period: str
    rate: float
    details: Optional[str] = None


class ScenarioOutputs(BaseModel):
    numeric_values: Dict[str, Any]
    currency: str = "INR"
    period: str
    projected_goal_age: Optional[int] = None
    projected_goal_months: Optional[int] = None
    formatted_headline: str
    formatted_highlight: str
    formatted_explanation: str
    formatted_footnote: str


class PlanFutureEnterpriseRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mode: PlanCalculationMode = Field(default=PlanCalculationMode.EXPENSES_PROJECTION)
    scenario_hash: Optional[str] = None
    profile_version: str = Field(default="v1.0")
    inputs: ScenarioInputs
    assumptions: ScenarioAssumptions
    meta: ScenarioMeta = Field(default_factory=ScenarioMeta)


class PlanFutureEnterpriseResponse(BaseModel):
    request_id: str
    scenario_hash: str
    status: str = "success"
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: str
    cached: bool = False
    outputs: ScenarioOutputs
    assumptions_used: Dict[str, Any]
    source_references: List[SourceReference]
    method_summary: str
    warnings: List[str] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)
