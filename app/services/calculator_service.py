"""
TCWC-25 Algorithmic-Reverse Expense & Age Calculator Service.
Implements the core mathematical models, compounding mechanics, inflation adjustments,
and real purchasing power transformations.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from app.core.constants import (
    INVESTMENT_PRODUCTS,
    DEFAULT_INFLATION_RATE,
    OFFICIAL_CPI_BENCHMARK,
    MAX_SEARCH_MONTHS,
    PRODUCT_RULES_VERSION,
    PROMPT_VERSION,
    DATA_VERSION
)
from app.models.schemas import (
    CalculatorRequest,
    CalculatorResponse,
    CalculationMode,
    ExpenseFrequency,
    FormattedMoney,
    YearlyMilestone,
    ProductMetadata,
    PlanFutureRequest,
    PlanFutureResponse,
    PlanQuestionType,
    InvestmentMode,
    PlanCalculationMode,
    GoalBasis,
    ContributionMode,
    ContributionTiming,
    PlanFutureEnterpriseRequest,
    PlanFutureEnterpriseResponse,
    ScenarioOutputs,
    SourceReference,
    WhenReachGoalRequest,
    WhenReachGoalResponse
)
from app.services.formatters import format_inr_exact, format_inr_compact, format_percentage
from app.services.cache_service import plan_future_cache


class FinancialCalculatorService:
    """
    High-precision financial calculation engine for age-expense mapping,
    reverse lumpsum targeting, forward projections, and real purchasing power decay.
    """

    @classmethod
    def get_supported_products(cls) -> List[ProductMetadata]:
        """Returns all configured investment products with metadata."""
        return [
            ProductMetadata(**prod) for prod in INVESTMENT_PRODUCTS.values()
        ]

    @classmethod
    def resolve_product(
        cls,
        product_id: str,
        custom_cagr: float | None = None,
        custom_freq: int | None = None
    ) -> Dict[str, Any]:
        """
        Resolves product configuration, honoring custom overrides.
        """
        base = INVESTMENT_PRODUCTS.get(product_id, INVESTMENT_PRODUCTS["custom"])
        prod = dict(base)

        if custom_cagr is not None:
            prod["default_cagr"] = custom_cagr
        if custom_freq is not None:
            prod["compounding_frequency"] = custom_freq
            if custom_freq == 1:
                prod["compounding_label"] = "Annually"
            elif custom_freq == 4:
                prod["compounding_label"] = "Quarterly"
            elif custom_freq == 12:
                prod["compounding_label"] = "Monthly"
            elif custom_freq == 2:
                prod["compounding_label"] = "Semi-Annually"
            else:
                prod["compounding_label"] = f"{custom_freq}x / Year"

        return prod

    @classmethod
    def calculate_growth_factor(cls, nominal_rate: float, compounding_freq: int, tenure_years: float) -> float:
        """
        Calculates total compound growth multiplier F = (1 + r / m)^(m * N).
        Handles zero-rate edge case gracefully.
        """
        if nominal_rate == 0:
            return 1.0
        return (1.0 + (nominal_rate / compounding_freq)) ** (compounding_freq * tenure_years)

    @classmethod
    def calculate_effective_annual_rate(cls, nominal_rate: float, compounding_freq: int) -> float:
        """
        Calculates Effective Annual Rate (EAR) = (1 + r / m)^m - 1.
        """
        if nominal_rate == 0 or compounding_freq <= 0:
            return nominal_rate
        return ((1.0 + (nominal_rate / compounding_freq)) ** compounding_freq) - 1.0

    @classmethod
    def generate_fine_print_disclaimer(
        cls,
        current_age: int,
        future_age: int,
        tenure: int,
        inflation_rate: float,
        nominal_corpus: float,
        real_corpus: float,
        current_exp: float,
        future_exp: float,
        product_name: str
    ) -> str:
        """
        Builds the regulatory & educational fine print string explaining the divergence
        between nominal maturity corpus and real inflation-adjusted purchasing power.
        """
        c_nominal = format_inr_compact(nominal_corpus)
        c_real = format_inr_compact(real_corpus)
        e_curr = format_inr_compact(current_exp)
        e_fut = format_inr_compact(future_exp)
        inf_pct = format_percentage(inflation_rate, decimals=1)
        power_retention = (real_corpus / nominal_corpus * 100) if nominal_corpus > 0 else 0

        return (
            f"FINE PRINT DISCLOSURE (PURCHASING POWER REALITY): Over your {tenure}-year horizon "
            f"(Age {current_age} → {future_age}), an average annual inflation rate of {inf_pct} "
            f"means that today's expense of {e_curr} will require {e_fut} nominal currency at Age {future_age}. "
            f"While your projected {product_name} portfolio will yield a nominal corpus of {c_nominal}, "
            f"its actual purchasing power in today's baseline money is equivalent to only {c_real} "
            f"({power_retention:.1f}% purchasing power retained). In long-term financial planning, "
            f"always evaluate your retirement and lifestyle targets in real (inflation-adjusted) terms."
        )

    @classmethod
    def calculate(cls, req: CalculatorRequest) -> CalculatorResponse:
        """
        Executes end-to-end calculations conforming to TCWC-25 specifications.
        """
        # 1. Core Mapping & Horizon
        current_age = req.current_age
        future_age = req.future_age
        tenure = future_age - current_age
        if tenure <= 0:
            raise ValueError(f"Tenure must be strictly positive. Future age {future_age} <= current age {current_age}.")

        # 2. Inflation Calculation
        inflation_rate = req.inflation_rate if req.inflation_rate is not None else DEFAULT_INFLATION_RATE
        # Inflated Goal: Future Expenditure = Current Expenditure * (1 + inflation_rate)^N
        inflation_multiplier = (1.0 + inflation_rate) ** tenure
        future_expenditure_raw = req.current_expenditure * inflation_multiplier
        inflation_cost_increase = future_expenditure_raw - req.current_expenditure

        # 3. Product & Compounding Mechanics
        prod = cls.resolve_product(req.product_id, req.custom_cagr, req.compounding_frequency)
        nominal_cagr = prod["default_cagr"]
        compounding_freq = prod["compounding_frequency"]
        effective_annual_rate = cls.calculate_effective_annual_rate(nominal_cagr, compounding_freq)

        # Growth Multiplier: F = (1 + r/m)^(m * N)
        wealth_multiplier = cls.calculate_growth_factor(nominal_cagr, compounding_freq, tenure)

        # Operational Modes
        required_lumpsum_raw: float | None = None
        existing_lumpsum_raw: float | None = None
        projected_nominal_corpus_raw: float
        goal_gap_raw: float | None = None
        surplus_raw: float | None = None
        goal_achieved_pct: float | None = None

        if req.mode == CalculationMode.TARGET_DRIVEN:
            # Mode a) Target-Driven Mode:
            # Required Lumpsum = Future Expenditure / (1 + product_return)^N
            required_lumpsum_raw = future_expenditure_raw / wealth_multiplier
            # If the required lumpsum is invested, the maturity nominal corpus matches future expenditure
            projected_nominal_corpus_raw = future_expenditure_raw
            existing_lumpsum_raw = required_lumpsum_raw
            goal_gap_raw = 0.0
            surplus_raw = 0.0
            goal_achieved_pct = 100.0
        else:
            # Mode b) Projection Mode:
            existing_lumpsum_raw = req.existing_lumpsum or 0.0
            projected_nominal_corpus_raw = existing_lumpsum_raw * wealth_multiplier
            goal_gap_raw = max(0.0, future_expenditure_raw - projected_nominal_corpus_raw)
            surplus_raw = max(0.0, projected_nominal_corpus_raw - future_expenditure_raw)
            if future_expenditure_raw > 0:
                goal_achieved_pct = min(1000.0, (projected_nominal_corpus_raw / future_expenditure_raw) * 100.0)
            else:
                goal_achieved_pct = 100.0

        # 5. Fine Print: Real Purchasing Power in today's money
        # Real Value = Nominal Corpus / (1 + inflation_rate)^N
        real_purchasing_power_raw = projected_nominal_corpus_raw / inflation_multiplier
        purchasing_power_erosion_raw = max(0.0, projected_nominal_corpus_raw - real_purchasing_power_raw)
        retention_pct = (real_purchasing_power_raw / projected_nominal_corpus_raw * 100.0) if projected_nominal_corpus_raw > 0 else 0.0

        # Fine print disclosure string
        disclaimer = cls.generate_fine_print_disclaimer(
            current_age=current_age,
            future_age=future_age,
            tenure=tenure,
            inflation_rate=inflation_rate,
            nominal_corpus=projected_nominal_corpus_raw,
            real_corpus=real_purchasing_power_raw,
            current_exp=req.current_expenditure,
            future_exp=future_expenditure_raw,
            product_name=prod["name"]
        )

        # Yearly Trajectory Milestones
        trajectory: List[YearlyMilestone] = []
        base_invested = required_lumpsum_raw if req.mode == CalculationMode.TARGET_DRIVEN else (req.existing_lumpsum or 0.0)

        for year in range(0, tenure + 1):
            y_age = current_age + year
            y_inf_mult = (1.0 + inflation_rate) ** year
            y_growth_mult = cls.calculate_growth_factor(nominal_cagr, compounding_freq, year)

            y_exp_nom = req.current_expenditure * y_inf_mult
            y_corp_nom = base_invested * y_growth_mult
            y_real_power = y_corp_nom / y_inf_mult if y_inf_mult > 0 else y_corp_nom
            y_retention = (1.0 / y_inf_mult * 100.0) if y_inf_mult > 0 else 100.0

            trajectory.append(
                YearlyMilestone(
                    year_offset=year,
                    age=y_age,
                    future_expenditure_nominal=round(y_exp_nom, 2),
                    future_expenditure_formatted=format_inr_compact(y_exp_nom),
                    projected_corpus_nominal=round(y_corp_nom, 2),
                    projected_corpus_formatted=format_inr_compact(y_corp_nom),
                    real_purchasing_power=round(y_real_power, 2),
                    real_purchasing_power_formatted=format_inr_compact(y_real_power),
                    purchasing_power_retention_pct=round(y_retention, 1)
                )
            )

        # Helper to construct FormattedMoney
        def make_money(val: float | None) -> FormattedMoney | None:
            if val is None:
                return None
            return FormattedMoney(
                raw=round(val, 2),
                formatted_exact=format_inr_exact(val),
                formatted_compact=format_inr_compact(val)
            )

        return CalculatorResponse(
            current_age=current_age,
            future_age=future_age,
            tenure_years=tenure,
            inflation_rate=inflation_rate,
            inflation_rate_formatted=format_percentage(inflation_rate),
            product_id=prod["id"],
            product_name=prod["name"],
            product_cagr=nominal_cagr,
            product_cagr_formatted=format_percentage(nominal_cagr),
            compounding_frequency=compounding_freq,
            compounding_label=prod["compounding_label"],
            effective_annual_rate=round(effective_annual_rate, 6),
            effective_annual_rate_formatted=format_percentage(effective_annual_rate, decimals=2),
            mode=req.mode,
            expense_frequency=req.expense_frequency,
            current_expenditure=make_money(req.current_expenditure), # type: ignore
            future_expenditure=make_money(future_expenditure_raw), # type: ignore
            inflation_multiplier=round(inflation_multiplier, 3),
            inflation_cost_increase=make_money(inflation_cost_increase), # type: ignore
            wealth_multiplier=round(wealth_multiplier, 3),
            required_lumpsum=make_money(required_lumpsum_raw),
            existing_lumpsum=make_money(existing_lumpsum_raw),
            projected_nominal_corpus=make_money(projected_nominal_corpus_raw),
            goal_gap=make_money(goal_gap_raw),
            surplus=make_money(surplus_raw),
            goal_achieved_percentage=round(goal_achieved_pct, 1) if goal_achieved_pct is not None else None,
            real_purchasing_power=make_money(real_purchasing_power_raw), # type: ignore
            purchasing_power_erosion=make_money(purchasing_power_erosion_raw), # type: ignore
            purchasing_power_retention_pct=round(retention_pct, 1),
            fine_print_disclaimer=disclaimer,
            yearly_trajectory=trajectory
        )

    @classmethod
    def calculate_plan_future(cls, req: PlanFutureRequest) -> PlanFutureResponse:
        """
        Calculates responses for the 'Plan your future' multi-state module.
        Powers calculations via the LLM planner service with function calling
        and deterministic math engine fallback:
        1. Validation: positive amounts, valid reverse mode criteria.
        2. Goal Basis: inflation compounding only on 'cost_today'; 0% inflation on 'future_amount'.
        3. Contribution combinations: Monthly, One-time, and Both.
        4. Horizon & Product rules: 600 months limit, lock-ins, and non-reinvestment notices.
        5. Deterministic SHA-256 caching with 24-hr TTL and audit logging.
        6. Official MoSPI CPI-Combined 5-year benchmark comparison references.
        """
        from app.services.llm_planner import LLMPlannerService
        return LLMPlannerService.execute_plan(req)

    @classmethod
    def calculate_plan_future_enterprise(
        cls,
        req: PlanFutureEnterpriseRequest
    ) -> PlanFutureEnterpriseResponse:
        """
        Enterprise contract execution handler implementing strict privacy,
        deterministic SHA-256 caching, MoSPI benchmarks, and warnings.
        """
        # Map enterprise request to internal execution parameters
        mode_map = {
            PlanCalculationMode.EXPENSES_PROJECTION: PlanQuestionType.EXPENSES_STATE_A,
            PlanCalculationMode.REQUIRED_INVESTMENT: PlanQuestionType.INVESTMENT_STATE_B,
            PlanCalculationMode.REVERSE_GOAL_AGE: PlanQuestionType.REACH_GOAL_STATE_C
        }
        question_type = mode_map.get(req.mode, PlanQuestionType.EXPENSES_STATE_A)

        duration_years = max(1, req.inputs.duration_months // 12)
        target_age = req.inputs.target_age or (req.inputs.age + duration_years)

        internal_req = PlanFutureRequest(
            profile_age=req.inputs.age,
            question_type=question_type,
            goal_basis=req.inputs.goal_basis,
            monthly_expenses_today=req.inputs.amounts.get("current_expenses", 40000.0),
            target_age=target_age,
            duration_years=duration_years,
            target_goal_amount=req.inputs.amounts.get("target_goal", 1000000.0),
            existing_savings=req.inputs.amounts.get("existing_savings", 0.0),
            investment_mode=req.inputs.contribution_mode,
            monthly_contribution=req.inputs.amounts.get("monthly_contribution", 10000.0),
            lump_sum_contribution=req.inputs.amounts.get("one_time_contribution", 0.0),
            product_id=req.inputs.product_id,
            inflation_rate=req.assumptions.inflation_rate,
            expected_cagr=req.assumptions.return_rates.get("cagr", 0.10),
            request_id=req.request_id,
            scenario_hash=req.scenario_hash,
            profile_version=req.profile_version
        )

        internal_res = cls.calculate_plan_future(internal_req)

        return PlanFutureEnterpriseResponse(
            request_id=req.request_id,
            scenario_hash=internal_res.scenario_hash or "",
            status="warning" if internal_res.warnings else "success",
            result_id=str(uuid.uuid4()),
            generated_at=internal_res.generated_at or datetime.now(timezone.utc).isoformat(),
            cached=internal_res.cached,
            outputs=ScenarioOutputs(
                numeric_values=internal_res.breakdown,
                currency=req.inputs.currency,
                period="monthly" if req.mode == PlanCalculationMode.EXPENSES_PROJECTION else "total",
                projected_goal_age=internal_res.target_age,
                projected_goal_months=internal_res.duration_years * 12,
                formatted_headline=internal_res.headline,
                formatted_highlight=internal_res.highlight_value,
                formatted_explanation=internal_res.explanation_footnote,
                formatted_footnote=internal_res.disclaimer
            ),
            assumptions_used={
                "inflation_rate": req.assumptions.inflation_rate,
                "expected_cagr": req.assumptions.return_rates.get("cagr", 0.10),
                "goal_basis": req.inputs.goal_basis.value,
                "product_rules_version": req.assumptions.product_rules_version
            },
            source_references=[
                SourceReference(
                    source=ref["source"],
                    period=ref["period"],
                    rate=ref["rate"],
                    details=ref.get("details")
                ) for ref in internal_res.source_references
            ],
            method_summary=f"Deterministic compounding & inflation transformation engine ({req.meta.model})",
            warnings=internal_res.warnings,
            missing_inputs=[]
        )

    @classmethod
    def calculate_when_reach_goal(
        cls,
        req: WhenReachGoalRequest
    ) -> WhenReachGoalResponse:
        """
        Calculates time-to-goal using discrete monthly compounding and inflation adjustment.
        """
        from app.services.math_engine import calculate_when_reach_goal
        return calculate_when_reach_goal(req)



