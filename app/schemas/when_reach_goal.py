"""
Pydantic v2 schemas for the When Can I Reach My Goal (State C) discrete solver.
"""

import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class WhenReachGoalRequest(BaseModel):
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    mode: str = Field(default="TIME_TO_GOAL")
    scenario_hash: Optional[str] = None
    profile_version: str = Field(default="v1.0")
    current_age: int = Field(default=48, ge=18, le=120)
    goal_basis: str = Field(default="COST_TODAY")  # "COST_TODAY" | "FUTURE_AMOUNT"
    target_amount: float = Field(default=1000000.0)
    amount_invested_today: Optional[float] = Field(default=None, ge=0.0)
    contribution_mode: str = Field(default="MONTHLY")  # "ONE_TIME" | "MONTHLY" | "BOTH"
    monthly_contribution: Optional[float] = Field(default=None, ge=0.0)
    # Legacy fields for backward compatibility
    existing_savings: float = Field(default=0.0, ge=0.0)
    one_time_investment: float = Field(default=0.0, ge=0.0)
    monthly_investment: float = Field(default=0.0, ge=0.0)
    contribution_timing: str = Field(default="MONTH_END")
    assumed_annual_return: float = Field(default=0.10)
    assumed_annual_inflation: float = Field(default=0.06)
    max_search_months: int = Field(default=600)
    prompt_version: str = Field(default="v1.0")
    data_version: str = Field(default="v1.0")


class WhenReachGoalResponse(BaseModel):
    request_id: str
    scenario_hash: str
    status: str  # "SUCCESS" | "UNREACHABLE_WITHIN_LIMIT" | "INVALID_INPUT"
    years: Optional[int] = None
    months: Optional[int] = None
    total_months: Optional[int] = None
    projected_goal_age: Optional[int] = None
    final_corpus: Optional[float] = None
    final_target: Optional[float] = None
    total_invested: Optional[float] = None
    estimated_growth: Optional[float] = None
    assumptions_used: Dict[str, Any]
    source_references: List[Dict[str, Any]] = Field(default_factory=list)
    method_summary: str
    warnings: List[str] = Field(default_factory=list)
    result_id: str
    generated_time: str
