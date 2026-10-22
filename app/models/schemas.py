"""
Pydantic v2 schemas for the TCWC-25 Financial Calculator.
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


class CalculationMode(str, Enum):
    TARGET_DRIVEN = "target_driven"
    PROJECTION = "projection"


class ExpenseFrequency(str, Enum):
    ANNUAL = "annual"
    MONTHLY = "monthly"
    ONE_TIME = "one_time"


class ProductMetadata(BaseModel):
    id: str
    name: str
    category: str
    default_cagr: float
    compounding_frequency: int
    compounding_label: str
    risk_level: str
    description: str
    tax_note: str


class FormattedMoney(BaseModel):
    raw: float
    formatted_exact: str
    formatted_compact: str


class YearlyMilestone(BaseModel):
    year_offset: int
    age: int
    future_expenditure_nominal: float
    future_expenditure_formatted: str
    projected_corpus_nominal: float
    projected_corpus_formatted: str
    real_purchasing_power: float
    real_purchasing_power_formatted: str
    purchasing_power_retention_pct: float


class CalculatorRequest(BaseModel):
    current_age: int = Field(..., ge=MIN_AGE, le=MAX_AGE - 1, description="Current age in years")
    future_age: int = Field(..., ge=MIN_AGE + 1, le=MAX_AGE, description="Future milestone age in years")
    current_expenditure: float = Field(..., gt=0, description="Current expenditure amount in INR")
    expense_frequency: ExpenseFrequency = Field(
        default=ExpenseFrequency.ANNUAL,
        description="Frequency of current expenditure (annual, monthly, or one_time goal)"
    )
    mode: CalculationMode = Field(
        default=CalculationMode.TARGET_DRIVEN,
        description="Calculation mode: target_driven (required lumpsum) or projection (future corpus with existing P)"
    )
    existing_lumpsum: Optional[float] = Field(
        default=0.0,
        ge=0,
        description="Existing one-time investment deposit P (required in projection mode)"
    )
    product_id: str = Field(
        default="equity_mf",
        description="Investment product identifier (e.g. equity_mf, hybrid_mf, debt_mf, fixed_deposit, ppf, custom)"
    )
    custom_cagr: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional override for annual return rate (e.g., 0.12 for 12%)"
    )
    compounding_frequency: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Compounding frequency per year (1=Annual, 4=Quarterly, 12=Monthly)"
    )
    inflation_rate: Optional[float] = Field(
        default=DEFAULT_INFLATION_RATE,
        ge=MIN_INFLATION_RATE,
        le=MAX_INFLATION_RATE,
        description="Annual inflation rate (default: 5.5% trailing 5-year CPI average)"
    )

    @model_validator(mode="after")
    def validate_horizon(self) -> "CalculatorRequest":
        if self.future_age <= self.current_age:
            raise ValueError(
                f"Future age ({self.future_age}) must be strictly greater than current age ({self.current_age}). "
                f"Tenure must be at least 1 year."
            )
        return self


class CalculatorResponse(BaseModel):
    # Horizon info
    current_age: int
    future_age: int
    tenure_years: int

    # Economic assumptions
    inflation_rate: float
    inflation_rate_formatted: str

    # Product details
    product_id: str
    product_name: str
    product_cagr: float
    product_cagr_formatted: str
    compounding_frequency: int
    compounding_label: str
    effective_annual_rate: float
    effective_annual_rate_formatted: str

    # Mode & core calculations
    mode: CalculationMode
    expense_frequency: ExpenseFrequency
    current_expenditure: FormattedMoney
    future_expenditure: FormattedMoney
    inflation_multiplier: float
    inflation_cost_increase: FormattedMoney

    # Investment outcome
    wealth_multiplier: float
    required_lumpsum: Optional[FormattedMoney] = None
    existing_lumpsum: Optional[FormattedMoney] = None
    projected_nominal_corpus: Optional[FormattedMoney] = None
    goal_gap: Optional[FormattedMoney] = None
    surplus: Optional[FormattedMoney] = None
    goal_achieved_percentage: Optional[float] = None

    # Real purchasing power & fine print
    real_purchasing_power: FormattedMoney
    purchasing_power_erosion: FormattedMoney
    purchasing_power_retention_pct: float
    fine_print_disclaimer: str

    # Trajectory for charts and visualizations
    yearly_trajectory: List[YearlyMilestone]


# Re-export Plan Your Future schemas from the dedicated schemas/plan_future module
from app.schemas.plan_future import (
    PlanQuestionType,
    PlanCalculationMode,
    GoalBasis,
    ContributionMode,
    ContributionTiming,
    InvestmentMode,
    FinancialProjectionToolInput,
    FinancialProjectionToolOutput,
    PlanFutureRequest,
    PlanFutureResponse,
    ScenarioInputs,
    ScenarioAssumptions,
    ScenarioMeta,
    SourceReference,
    ScenarioOutputs,
    PlanFutureEnterpriseRequest,
    PlanFutureEnterpriseResponse
)
from app.schemas.when_reach_goal import (
    WhenReachGoalRequest,
    WhenReachGoalResponse
)



