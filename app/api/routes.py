"""
FastAPI route handlers for TCWC-25 Financial Calculator.
"""

from typing import List
from fastapi import APIRouter, HTTPException, status
from app.models.schemas import (
    CalculatorRequest,
    CalculatorResponse,
    ProductMetadata,
    PlanFutureRequest,
    PlanFutureResponse,
    PlanFutureEnterpriseRequest,
    PlanFutureEnterpriseResponse,
    WhenReachGoalRequest,
    WhenReachGoalResponse
)
from app.core.constants import OFFICIAL_CPI_BENCHMARK
from app.services.calculator_service import FinancialCalculatorService
from app.services.cache_service import plan_future_cache

router = APIRouter(prefix="/api/v1", tags=["Calculator"])


@router.get("/health", summary="Service Health Check")
def health_check():
    return {
        "status": "healthy",
        "service": "TCWC-25 Financial Calculator Engine",
        "version": "1.0.0"
    }


@router.get("/products", response_model=List[ProductMetadata], summary="Get Supported Investment Products")
def get_products():
    """
    Returns the catalog of supported investment products with predefined default CAGRs,
    compounding frequencies, and tax notes.
    """
    return FinancialCalculatorService.get_supported_products()


@router.post("/calculate", response_model=CalculatorResponse, summary="Calculate Reverse/Forward Age & Expense Mapping")
def calculate_horizon(request: CalculatorRequest):
    """
    Executes core TCWC-25 financial algorithm:
    1. Tenure: N = Future Age - Current Age.
    2. Inflated Goal: Future Expenditure = Current Expenditure * (1 + inflation_rate)^N.
    3. Required Lumpsum or Nominal Maturity Corpus projection.
    4. Real purchasing power decay and regulatory fine print.
    """
    try:
        response = FinancialCalculatorService.calculate(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal calculation error: {str(e)}"
        )


@router.post("/plan-future", response_model=PlanFutureResponse, summary="Plan Your Future Multi-State Mobile Card Calculator")
def plan_future(request: PlanFutureRequest):
    """
    Executes 'Plan your future' calculation across State A (Expenses),
    State B (Investment requirement), or State C (Goal horizon).
    Ensures calculations are performed strictly server-side.
    """
    try:
        response = FinancialCalculatorService.calculate_plan_future(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal plan-future calculation error: {str(e)}"
        )


@router.post("/plan-future/enterprise", response_model=PlanFutureEnterpriseResponse, summary="Enterprise Plan Future Contract Handler")
def plan_future_enterprise(request: PlanFutureEnterpriseRequest):
    """
    Executes Plan Your Future under the full Enterprise contract specification:
    - Privacy enforcement (no PII)
    - Deterministic SHA-256 caching with 24-hr TTL
    - Inflation compounding on Cost Today vs 0% on Future Amount
    - MoSPI CPI official 5-year benchmark citations
    """
    try:
        response = FinancialCalculatorService.calculate_plan_future_enterprise(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enterprise calculation error: {str(e)}"
        )


@router.get("/plan-future/cpi-benchmark", summary="Official MoSPI CPI 5-Year Historical Benchmark")
def get_cpi_benchmark():
    """
    Returns official MoSPI CPI-Combined historical benchmark across 6 endpoint index levels
    for the latest 5 complete calendar years (Dec 2019 – Dec 2024).
    """
    return OFFICIAL_CPI_BENCHMARK


@router.get("/plan-future/cache/stats", summary="Scenario Cache Telemetry")
def get_cache_stats():
    """Returns SHA-256 scenario cache hit/miss ratio, active TTL entries, and history count."""
    return plan_future_cache.get_stats()


@router.get("/plan-future/cache/history", summary="Calculation Execution Audit Log")
def get_cache_history(limit: int = 50):
    """Returns chronological calculation run logs preserving historical estimates."""
    return plan_future_cache.get_history(limit=limit)


@router.post(
    "/calculator/when-reach-goal",
    response_model=WhenReachGoalResponse,
    summary="When Can I Reach My Goal Discrete Solver"
)
def when_reach_goal(request: WhenReachGoalRequest):
    """
    Computes time-to-goal using discrete monthly compounding,
    month-end contribution timing, and target inflation adjustment up to 600 months.
    """
    try:
        response = FinancialCalculatorService.calculate_when_reach_goal(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"When-reach-goal calculation error: {str(e)}"
        )



