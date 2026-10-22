"""
Deterministic Financial Math Engine for TCWC-25 Calculator.
Serves as the high-precision Python tool execution target for LLM function calling.
Computes inflation compounding, SIP/Lumpsum horizons, and reverse goal searches deterministically.
"""

import uuid
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.core.constants import (
    INVESTMENT_PRODUCTS,
    OFFICIAL_CPI_BENCHMARK,
    DEFAULT_INFLATION_RATE,
    MAX_SEARCH_MONTHS
)
from app.services.formatters import format_inr_exact, format_inr_compact, format_percentage
from app.schemas.when_reach_goal import WhenReachGoalRequest, WhenReachGoalResponse


def calculate_financial_projection(
    mode: str,
    current_age: int,
    target_age: Optional[int] = None,
    current_expense: float = 40000.0,
    goal_amount: float = 1000000.0,
    goal_basis: str = "COST_TODAY",
    inflation_rate: float = DEFAULT_INFLATION_RATE,
    product_key: str = "equity_mf",
    existing_savings: float = 0.0,
    contribution_type: str = "monthly",
    monthly_contribution: float = 0.0,
    lump_sum_contribution: float = 0.0,
    custom_cagr: Optional[float] = None,
    existing_investment: Optional[float] = None,
    monthly_investment: Optional[float] = None,
    years: Optional[int] = None,
    annual_return: Optional[float] = None,
    principal: Optional[float] = None,
    amount_invested_today: Optional[float] = None,
    annual_inflation: Optional[float] = None
) -> Dict[str, Any]:
    """
    Deterministic Python calculation tool called by LLM planners.
    Guarantees mathematically exact outputs without LLM hallucination.

    Modes:
      - 'EXPENSES' (State A): Future monthly expense projection
      - 'REQUIRED_INVESTMENT' (State B): Investment needed to hit target goal
      - 'REACH_WHEN' (State C): Age & tenure needed to reach goal
    """
    # Normalize mode string
    normalized_mode = mode.upper()
    if normalized_mode in ("EXPENSES", "EXPENSES_STATE_A", "EXPENSES_PROJECTION"):
        exec_mode = "EXPENSES"
    elif normalized_mode in ("INVESTMENT", "INVESTMENT_STATE_B", "REQUIRED_INVESTMENT"):
        exec_mode = "REQUIRED_INVESTMENT"
    elif normalized_mode in ("REACH_GOAL", "REACH_GOAL_STATE_C", "REACH_WHEN", "REVERSE_GOAL_AGE"):
        exec_mode = "REACH_WHEN"
    else:
        exec_mode = "EXPENSES"

    # Normalize goal basis
    is_cost_today = goal_basis.upper() in ("COST_TODAY", "TRUE")

    # Resolve product and return rate
    prod_meta = INVESTMENT_PRODUCTS.get(product_key, INVESTMENT_PRODUCTS["equity_mf"])
    cagr = custom_cagr if custom_cagr is not None else prod_meta["default_cagr"]
    compounding_freq = prod_meta.get("compounding_frequency", 1)

    warnings: List[str] = []
    source_refs: List[Dict[str, Any]] = [
        {
            "source": OFFICIAL_CPI_BENCHMARK["source"],
            "series": OFFICIAL_CPI_BENCHMARK["series"],
            "period": OFFICIAL_CPI_BENCHMARK["measurement_period"],
            "rate": OFFICIAL_CPI_BENCHMARK["annualized_5y_rate"],
            "details": (
                f"Official MoSPI trailing 5-year annualized benchmark: "
                f"{OFFICIAL_CPI_BENCHMARK['annualized_5y_formatted']} "
                f"(Dec 2019: {OFFICIAL_CPI_BENCHMARK['cpi_start']} -> Dec 2024: {OFFICIAL_CPI_BENCHMARK['cpi_end']})"
            )
        }
    ]

    # Validate horizon
    eff_target_age = target_age if (target_age and target_age > current_age) else current_age + 7
    tenure_years = max(1, eff_target_age - current_age)
    tenure_months = tenure_years * 12

    # Check product statutory constraints
    if product_key == "ppf" and tenure_years < 15:
        warnings.append("Public Provident Fund (PPF) mandates a statutory lock-in period of 15 years (180 months).")
    if product_key == "fixed_deposit" and tenure_years > 10:
        warnings.append("Fixed Deposit maximum term is 10 years (120 months); requires explicit reinvestment.")
    warnings.append("Projections assume a constant return rate. Does NOT silently assume auto-renewal, perpetual contribution, or reinvestment after product maturity.")

    future_expense = 0.0
    required_investment = 0.0
    monthly_amount = 0.0
    one_time_amount = 0.0
    inflated_target_cost = 0.0
    net_corpus_needed = 0.0
    nominal_maturity_corpus = 0.0
    projected_goal_age = eff_target_age
    future_value: Optional[float] = None
    inflated_cost: Optional[float] = None
    real_gain: Optional[float] = None
    principal_out: Optional[float] = None
    years_out: Optional[int] = None
    annual_return_pct: Optional[float] = None
    total_invested: Optional[float] = None
    estimated_gains: Optional[float] = None
    inflated_benchmark: Optional[float] = None
    assumed_return_pct: Optional[float] = None
    inflation_pct: Optional[float] = None
    breakdown: Dict[str, Any] = {
        "current_age": current_age,
        "target_age": eff_target_age,
        "tenure_years": tenure_years,
        "tenure_months": tenure_months,
        "inflation_rate": inflation_rate,
        "product_key": product_key,
        "product_name": prod_meta["name"],
        "cagr": cagr,
        "compounding_frequency": compounding_freq,
        "official_5y_cpi_rate": OFFICIAL_CPI_BENCHMARK["annualized_5y_rate"]
    }

    # Mode 1: EXPENSES
    if exec_mode == "EXPENSES":
        inflation_multiplier = (1.0 + inflation_rate) ** tenure_years
        future_expense = current_expense * inflation_multiplier
        nominal_maturity_corpus = future_expense
        formatted_future_expense = format_inr_exact(future_expense)

        purchasing_power_factor = 1.0 / inflation_multiplier if inflation_multiplier > 0 else 1.0
        real_purchasing_power_fine_print = (
            f"Due to compounding inflation of {format_percentage(inflation_rate)}, ₹100 today will have "
            f"purchasing power of ₹{100.0 * purchasing_power_factor:.1f} at age {eff_target_age}. "
            f"Monthly expense increases from {format_inr_exact(current_expense)} to {formatted_future_expense}."
        )

        headline = f"At age {eff_target_age}, you may need {formatted_future_expense} each month"
        highlight_value = formatted_future_expense
        explanation_footnote = "To maintain similar purchasing power. This is a monthly expense estimate, not the savings needed for retirement."

        breakdown.update({
            "monthly_expenses_today": round(current_expense, 2),
            "formatted_monthly_expenses_today": format_inr_exact(current_expense),
            "future_monthly_expenses": round(future_expense, 2),
            "formatted_future_monthly_expenses": formatted_future_expense,
            "inflation_multiplier": round(inflation_multiplier, 4),
            "purchasing_power_factor": round(purchasing_power_factor, 4)
        })

    # Mode 2: REQUIRED_INVESTMENT (Pure One-Time Compounding Tool with Inflation)
    elif exec_mode == "REQUIRED_INVESTMENT":
        if principal is not None or amount_invested_today is not None:
            eff_principal = float(principal if principal is not None else amount_invested_today)
            eff_years = years if years is not None else tenure_years
            eff_annual_return = annual_return if annual_return is not None else (custom_cagr if custom_cagr is not None else (cagr if cagr is not None else 0.10))
            eff_annual_inflation = annual_inflation if annual_inflation is not None else (inflation_rate if inflation_rate is not None else DEFAULT_INFLATION_RATE)

            future_value = eff_principal * ((1.0 + eff_annual_return) ** eff_years)
            inflated_cost = eff_principal * ((1.0 + eff_annual_inflation) ** eff_years)
            real_gain = future_value - inflated_cost

            principal_out = eff_principal
            years_out = eff_years
            annual_return_pct = round(eff_annual_return * 100, 1)
            inflation_pct = round(eff_annual_inflation * 100, 1)
            assumed_return_pct = annual_return_pct
            total_invested = eff_principal
            estimated_gains = real_gain
            inflated_benchmark = inflated_cost

            headline = f"At age {eff_target_age}, your today's investment will be"
            highlight_value = format_inr_exact(future_value)
            required_investment = future_value
            nominal_maturity_corpus = future_value
            explanation_footnote = (
                f"Compounded at {annual_return_pct}% assumed return · "
                f"A {format_inr_exact(eff_principal)} expense today will cost {format_inr_exact(inflated_cost)} then at {inflation_pct}% inflation"
            )
            real_purchasing_power_fine_print = explanation_footnote

            if is_cost_today:
                inflation_mult = (1.0 + eff_annual_inflation) ** eff_years
                inflated_target_cost = goal_amount * inflation_mult
            else:
                inflated_target_cost = goal_amount
                inflation_mult = 1.0
            effective_target_goal = inflated_target_cost

            fv_p0 = existing_savings * ((1.0 + eff_annual_return) ** eff_years)
            fv_pnew = lump_sum_contribution * ((1.0 + eff_annual_return) ** eff_years)
            net_corpus_needed = max(0.0, inflated_target_cost - fv_p0 - fv_pnew)
            net_goal_remaining = net_corpus_needed

            r_monthly = ((1.0 + eff_annual_return) ** (1.0 / 12.0)) - 1.0 if eff_annual_return > 0 else 0.0
            eff_months = eff_years * 12
            if net_corpus_needed <= 0.0:
                monthly_amount = 0.0
            elif r_monthly > 0 and eff_months > 0:
                monthly_amount = net_corpus_needed * (r_monthly / (((1.0 + r_monthly) ** eff_months) - 1.0))
            else:
                monthly_amount = net_corpus_needed / max(1, eff_months)

            wealth_mult = (1.0 + eff_annual_return) ** eff_years
            one_time_amount = net_corpus_needed / wealth_mult if (net_corpus_needed > 0 and wealth_mult > 0) else 0.0

        elif monthly_investment is not None and monthly_investment > 0:
            eff_annual_return = annual_return if annual_return is not None else (custom_cagr if custom_cagr is not None else cagr)
            eff_annual_inflation = annual_inflation if annual_inflation is not None else (inflation_rate if inflation_rate is not None else DEFAULT_INFLATION_RATE)
            eff_years = years if years is not None else tenure_years
            eff_months = eff_years * 12
            eff_existing_inv = existing_investment if existing_investment is not None else existing_savings
            eff_monthly_inv = monthly_investment

            r_monthly = ((1.0 + eff_annual_return) ** (1.0 / 12.0)) - 1.0 if eff_annual_return > 0 else 0.0
            fv_lump = eff_existing_inv * ((1.0 + r_monthly) ** eff_months)
            fv_sip = eff_monthly_inv * (((1.0 + r_monthly) ** eff_months - 1.0) / r_monthly) if (eff_monthly_inv > 0 and r_monthly > 0) else (eff_monthly_inv * eff_months if eff_monthly_inv > 0 else 0.0)
            future_value = fv_lump + fv_sip

            total_invested = eff_existing_inv + (eff_monthly_inv * eff_months)
            inflated_benchmark = total_invested * ((1.0 + eff_annual_inflation) ** eff_years)
            estimated_gains = future_value - total_invested
            inflated_cost = inflated_benchmark
            real_gain = future_value - inflated_cost
            eff_principal = eff_existing_inv
            principal_out = eff_principal
            years_out = eff_years
            annual_return_pct = round(eff_annual_return * 100, 1)
            inflation_pct = round(eff_annual_inflation * 100, 1)
            assumed_return_pct = annual_return_pct

            headline = f"At age {eff_target_age}, your today's investment will be"
            highlight_value = format_inr_exact(future_value)
            required_investment = future_value
            nominal_maturity_corpus = future_value
            explanation_footnote = (
                f"Total invested: {format_inr_exact(total_invested)} · "
                f"Estimated growth: {format_inr_exact(estimated_gains)} · "
                f"Compounded at {assumed_return_pct}% assumed return"
            )
            real_purchasing_power_fine_print = explanation_footnote

            if is_cost_today:
                inflation_mult = (1.0 + eff_annual_inflation) ** eff_years
                inflated_target_cost = goal_amount * inflation_mult
            else:
                inflated_target_cost = goal_amount
                inflation_mult = 1.0
            effective_target_goal = inflated_target_cost

            fv_p0 = existing_savings * ((1.0 + eff_annual_return) ** eff_years)
            fv_pnew = lump_sum_contribution * ((1.0 + eff_annual_return) ** eff_years)
            net_corpus_needed = max(0.0, inflated_target_cost - fv_p0 - fv_pnew)
            net_goal_remaining = net_corpus_needed

            if net_corpus_needed <= 0.0:
                monthly_amount = 0.0
            elif r_monthly > 0 and eff_months > 0:
                monthly_amount = net_corpus_needed * (r_monthly / (((1.0 + r_monthly) ** eff_months) - 1.0))
            else:
                monthly_amount = net_corpus_needed / max(1, eff_months)

            wealth_mult = (1.0 + eff_annual_return) ** eff_years
            one_time_amount = net_corpus_needed / wealth_mult if (net_corpus_needed > 0 and wealth_mult > 0) else 0.0

        else:
            eff_principal = principal if principal is not None else (
                amount_invested_today if amount_invested_today is not None else (
                    existing_investment if existing_investment is not None else (
                        existing_savings if existing_savings > 0 else (goal_amount if goal_amount > 0 else 100000.0)
                    )
                )
            )
            eff_years = years if years is not None else tenure_years
            eff_annual_return = annual_return if annual_return is not None else (custom_cagr if custom_cagr is not None else (cagr if cagr is not None else 0.10))
            eff_annual_inflation = annual_inflation if annual_inflation is not None else (inflation_rate if inflation_rate is not None else DEFAULT_INFLATION_RATE)

            future_value = eff_principal * ((1.0 + eff_annual_return) ** eff_years)
            inflated_cost = eff_principal * ((1.0 + eff_annual_inflation) ** eff_years)
            real_gain = future_value - inflated_cost

            principal_out = eff_principal
            years_out = eff_years
            annual_return_pct = round(eff_annual_return * 100, 1)
            inflation_pct = round(eff_annual_inflation * 100, 1)
            assumed_return_pct = annual_return_pct
            total_invested = eff_principal
            estimated_gains = real_gain
            inflated_benchmark = inflated_cost

            headline = f"At age {eff_target_age}, your today's investment will be"
            highlight_value = format_inr_exact(future_value)
            required_investment = future_value
            nominal_maturity_corpus = future_value
            explanation_footnote = (
                f"Compounded at {annual_return_pct}% assumed return · "
                f"A {format_inr_exact(eff_principal)} expense today will cost {format_inr_exact(inflated_cost)} then at {inflation_pct}% inflation"
            )
            real_purchasing_power_fine_print = explanation_footnote

            if is_cost_today:
                inflation_mult = (1.0 + eff_annual_inflation) ** eff_years
                inflated_target_cost = goal_amount * inflation_mult
            else:
                inflated_target_cost = goal_amount
                inflation_mult = 1.0
            effective_target_goal = inflated_target_cost

            fv_p0 = existing_savings * ((1.0 + eff_annual_return) ** eff_years)
            fv_pnew = lump_sum_contribution * ((1.0 + eff_annual_return) ** eff_years)
            net_corpus_needed = max(0.0, inflated_target_cost - fv_p0 - fv_pnew)
            net_goal_remaining = net_corpus_needed

            r_monthly = ((1.0 + eff_annual_return) ** (1.0 / 12.0)) - 1.0 if eff_annual_return > 0 else 0.0
            eff_months = eff_years * 12
            if net_corpus_needed <= 0.0:
                monthly_amount = 0.0
            elif r_monthly > 0 and eff_months > 0:
                monthly_amount = net_corpus_needed * (r_monthly / (((1.0 + r_monthly) ** eff_months) - 1.0))
            else:
                monthly_amount = net_corpus_needed / max(1, eff_months)

            wealth_mult = (1.0 + eff_annual_return) ** eff_years
            one_time_amount = net_corpus_needed / wealth_mult if (net_corpus_needed > 0 and wealth_mult > 0) else 0.0

        contrib_mode_norm = contribution_type.lower()
        if future_value > 0:
            required_investment = future_value
        else:
            required_investment = one_time_amount if contrib_mode_norm == "one_time" else monthly_amount
        formatted_inv = format_inr_exact(required_investment)

        breakdown.update({
            "future_value": round(future_value),
            "inflated_cost": round(inflated_cost),
            "real_gain": round(real_gain),
            "net_advantage": round(real_gain),
            "principal": round(eff_principal),
            "amount_invested_today": round(eff_principal),
            "years": eff_years,
            "target_age": eff_target_age,
            "annual_return_pct": annual_return_pct,
            "inflation_pct": inflation_pct,
            "total_invested": round(total_invested),
            "estimated_gains": round(estimated_gains),
            "inflated_benchmark": round(inflated_benchmark),
            "assumed_return_pct": assumed_return_pct,
            "target_age": eff_target_age,
            "base_goal_amount": goal_amount,
            "goal_basis": "cost_today" if is_cost_today else "future_amount",
            "effective_target_goal": round(inflated_target_cost, 2),
            "inflated_target_cost": round(inflated_target_cost, 2),
            "formatted_effective_target_goal": format_inr_compact(inflated_target_cost),
            "existing_savings_p0": existing_savings,
            "projected_existing_savings_fv": round(fv_p0, 2),
            "future_value_existing_savings": round(fv_p0, 2),
            "one_time_contribution_pnew": lump_sum_contribution,
            "projected_one_time_fv": round(fv_pnew, 2),
            "net_goal_remaining": round(net_corpus_needed, 2),
            "net_corpus_needed": round(net_corpus_needed, 2),
            "contribution_type": contrib_mode_norm,
            "monthly_amount": round(monthly_amount, 2),
            "one_time_amount": round(one_time_amount, 2),
            "required_investment": round(required_investment, 2),
            "formatted_required_investment": formatted_inv
        })

    # Mode 3: REACH_WHEN
    else:
        total_initial_wealth = existing_savings + lump_sum_contribution
        r_m = ((1.0 + cagr) ** (1.0 / 12.0)) - 1.0 if cagr > 0 else 0.0
        months_count = 0
        accumulated = total_initial_wealth

        curr_target = goal_amount

        if accumulated < curr_target:
            while months_count < MAX_SEARCH_MONTHS:
                months_count += 1
                accumulated = accumulated * (1.0 + r_m) + monthly_contribution
                curr_target = goal_amount * ((1.0 + inflation_rate) ** (months_count / 12.0)) if is_cost_today else goal_amount
                if accumulated >= curr_target:
                    break

        final_target = curr_target
        if accumulated < final_target:
            warnings.append(
                f"Goal of {format_inr_compact(goal_amount)} cannot be reached within the search limit of "
                f"{MAX_SEARCH_MONTHS // 12} years (600 months) with the given contribution rate."
            )

        computed_years = months_count // 12
        computed_months = months_count % 12
        projected_goal_age = current_age + computed_years
        tenure_years = computed_years
        tenure_months = months_count
        duration_years = computed_years
        duration_months = computed_months
        projected_age_years = projected_goal_age
        projected_age_months = computed_months
        projected_savings = round(accumulated)
        goal_cost_then = round(final_target)

        if computed_years > 0 and computed_months > 0:
            duration_str = f"{computed_years} years and {computed_months} months"
        elif computed_years > 0:
            duration_str = f"{computed_years} years"
        else:
            duration_str = f"{computed_months} months"

        basis_note = f"Inflation-adjusted target ({format_inr_compact(final_target)})" if is_cost_today else f"Fixed target ({format_inr_compact(goal_amount)})"
        headline = f"You can reach your goal in {duration_str} (at age {projected_goal_age})"
        highlight_value = duration_str
        nominal_maturity_corpus = accumulated
        required_investment = monthly_contribution

        real_purchasing_power_fine_print = (
            f"Target of {format_inr_compact(final_target)} achieved over {duration_str}. "
            f"Nominal corpus reaches {format_inr_compact(accumulated)}."
        )
        explanation_footnote = (
            f"To reach {basis_note} based on monthly savings of {format_inr_exact(monthly_contribution)} "
            f"and {prod_meta['name']} return of {format_percentage(cagr)}."
        )

        breakdown.update({
            "base_goal_amount": goal_amount,
            "final_effective_target": round(final_target, 2),
            "goal_basis": "cost_today" if is_cost_today else "future_amount",
            "existing_savings_p0": existing_savings,
            "one_time_contribution_pnew": lump_sum_contribution,
            "initial_total_wealth": total_initial_wealth,
            "monthly_contribution": monthly_contribution,
            "months_needed": months_count,
            "years_needed": computed_years,
            "months_remainder": computed_months,
            "reach_age": projected_goal_age,
            "final_projected_corpus": round(accumulated, 2),
            "duration_years": duration_years,
            "duration_months": duration_months,
            "projected_age_years": projected_age_years,
            "projected_age_months": projected_age_months,
            "projected_savings": projected_savings,
            "goal_cost_then": goal_cost_then
        })

    return {
        "mode": exec_mode,
        "future_expense": round(future_expense, 2),
        "required_investment": round(required_investment, 2),
        "monthly_amount": round(monthly_amount, 2),
        "one_time_amount": round(one_time_amount, 2),
        "inflated_target_cost": round(inflated_target_cost, 2),
        "net_corpus_needed": round(net_corpus_needed, 2),
        "duration_years": tenure_years,
        "duration_months": duration_months if exec_mode == "REACH_WHEN" else 0,
        "projected_age_years": projected_age_years if exec_mode == "REACH_WHEN" else None,
        "projected_age_months": projected_age_months if exec_mode == "REACH_WHEN" else None,
        "projected_savings": projected_savings if exec_mode == "REACH_WHEN" else None,
        "goal_cost_then": goal_cost_then if exec_mode == "REACH_WHEN" else None,
        "future_value": round(future_value) if future_value is not None else None,
        "inflated_cost": round(inflated_cost) if inflated_cost is not None else None,
        "real_gain": round(real_gain) if real_gain is not None else None,
        "net_advantage": round(real_gain) if real_gain is not None else None,
        "principal": round(principal_out) if principal_out is not None else None,
        "amount_invested_today": round(principal_out) if principal_out is not None else None,
        "years": years_out if years_out is not None else tenure_years,
        "target_age": eff_target_age,
        "annual_return_pct": annual_return_pct if annual_return_pct is not None else (assumed_return_pct if assumed_return_pct is not None else None),
        "inflation_pct": inflation_pct if inflation_pct is not None else None,
        "total_invested": round(total_invested) if total_invested is not None else None,
        "estimated_gains": round(estimated_gains) if estimated_gains is not None else None,
        "inflated_benchmark": round(inflated_benchmark) if inflated_benchmark is not None else None,
        "assumed_return_pct": assumed_return_pct if assumed_return_pct is not None else None,
        "nominal_maturity_corpus": round(nominal_maturity_corpus, 2),
        "real_purchasing_power_fine_print": real_purchasing_power_fine_print,
        "tenure_months": tenure_months,
        "tenure_years": tenure_years,
        "projected_goal_age": projected_goal_age,
        "headline": headline,
        "highlight_value": highlight_value,
        "subtitle": "Your estimate",
        "explanation_footnote": explanation_footnote,
        "disclaimer": "Illustration only · Returns are not guaranteed",
        "warnings": warnings,
        "source_references": source_refs,
        "breakdown": breakdown,
        "method_summary": "Deterministic calculation engine (TCWC-25 mathematical baseline)"
    }


def calculate_when_reach_goal(req: WhenReachGoalRequest) -> WhenReachGoalResponse:
    """
    Solves for the exact month when accumulated corpus meets or exceeds the target,
    handling discrete monthly compounding, month-end contribution timing,
    and inflation target adjustment up to 600 months.
    """
    is_cost_today = req.goal_basis.upper() in ("COST_TODAY", "TRUE")
    contrib_mode = req.contribution_mode.upper()

    # Initial capital P and recurring SIP PMT
    if req.amount_invested_today is not None:
        P = float(req.amount_invested_today)
    else:
        P = float(req.existing_savings) + (float(req.one_time_investment) if contrib_mode in ("ONE_TIME", "BOTH") else 0.0)

    if req.monthly_contribution is not None:
        PMT = float(req.monthly_contribution) if contrib_mode in ("MONTHLY", "BOTH") else 0.0
    else:
        PMT = float(req.monthly_investment) if contrib_mode in ("MONTHLY", "BOTH") else 0.0

    scenario_hash = req.scenario_hash or hashlib.sha256(
        json.dumps({
            "current_age": req.current_age,
            "goal_basis": "COST_TODAY" if is_cost_today else "FUTURE_AMOUNT",
            "target_amount": req.target_amount,
            "amount_invested_today": P,
            "contribution_mode": contrib_mode,
            "monthly_contribution": PMT,
            "assumed_annual_return": req.assumed_annual_return,
            "assumed_annual_inflation": req.assumed_annual_inflation,
            "max_search_months": req.max_search_months
        }, sort_keys=True).encode("utf-8")
    ).hexdigest()

    standard_sources = [{
        "series": "CPI-Combined",
        "source": "MoSPI / RBI",
        "period": "2019-2024",
        "rate": 0.054
    }]

    assumptions_payload = {
        "annual_return": req.assumed_annual_return,
        "annual_inflation": req.assumed_annual_inflation,
        "goal_basis": "COST_TODAY" if is_cost_today else "FUTURE_AMOUNT",
        "contribution_mode": contrib_mode,
        "amount_invested_today": P,
        "monthly_contribution": PMT
    }

    # Validation checks: Return INVALID_INPUT if target_amount <= 0 or (P <= 0 and PMT <= 0)
    if req.target_amount <= 0 or (P <= 0 and PMT <= 0):
        return WhenReachGoalResponse(
            request_id=req.request_id or str(uuid.uuid4()),
            scenario_hash=scenario_hash,
            status="INVALID_INPUT",
            years=None,
            months=None,
            total_months=None,
            projected_goal_age=None,
            final_corpus=None,
            final_target=None,
            total_invested=None,
            estimated_growth=None,
            assumptions_used=assumptions_payload,
            source_references=standard_sources,
            method_summary="Discrete monthly compounding with month-end contribution timing up to 600-month bound.",
            warnings=["Target goal amount must be strictly greater than 0, and you must provide either existing savings / amount invested today (> 0) or a planned investment (> 0)."],
            result_id=str(uuid.uuid4()),
            generated_time=datetime.now(timezone.utc).isoformat()
        )

    # Validation check: Return GOAL_ALREADY_REACHED if P >= target_amount
    if P >= req.target_amount:
        return WhenReachGoalResponse(
            request_id=req.request_id or str(uuid.uuid4()),
            scenario_hash=scenario_hash,
            status="GOAL_ALREADY_REACHED",
            years=0,
            months=0,
            total_months=0,
            projected_goal_age=req.current_age,
            final_corpus=round(P, 2),
            final_target=round(req.target_amount, 2),
            total_invested=round(P, 2),
            estimated_growth=0.0,
            assumptions_used=assumptions_payload,
            source_references=standard_sources,
            method_summary="Discrete monthly compounding with month-end contribution timing up to 600-month bound.",
            warnings=["Goal already reached with initial investment."],
            result_id=str(uuid.uuid4()),
            generated_time=datetime.now(timezone.utc).isoformat()
        )

    r_m = ((1.0 + req.assumed_annual_return) ** (1.0 / 12.0)) - 1.0 if req.assumed_annual_return > 0 else 0.0
    i_m = ((1.0 + req.assumed_annual_inflation) ** (1.0 / 12.0)) - 1.0 if is_cost_today else 0.0
    max_months = req.max_search_months or 600

    reached_month = None
    final_corpus = 0.0
    final_target = 0.0
    last_corpus = 0.0
    last_target = 0.0

    for m in range(1, max_months + 1):
        if r_m > 0:
            corpus_m = P * ((1.0 + r_m) ** m) + PMT * (((1.0 + r_m) ** m - 1.0) / r_m)
        else:
            corpus_m = P + PMT * m

        if is_cost_today:
            target_m = req.target_amount * ((1.0 + i_m) ** m)
        else:
            target_m = req.target_amount

        last_corpus = corpus_m
        last_target = target_m

        if corpus_m >= target_m:
            reached_month = m
            final_corpus = corpus_m
            final_target = target_m
            break

    if reached_month is not None:
        years = reached_month // 12
        months = reached_month % 12
        projected_goal_age = req.current_age + years
        total_invested = P + (PMT * reached_month)
        estimated_growth = max(0.0, final_corpus - total_invested)

        return WhenReachGoalResponse(
            request_id=req.request_id or str(uuid.uuid4()),
            scenario_hash=scenario_hash,
            status="SUCCESS",
            years=years,
            months=months,
            total_months=reached_month,
            projected_goal_age=projected_goal_age,
            final_corpus=round(final_corpus, 2),
            final_target=round(final_target, 2),
            total_invested=round(total_invested, 2),
            estimated_growth=round(estimated_growth, 2),
            assumptions_used=assumptions_payload,
            source_references=standard_sources,
            method_summary="Discrete monthly compounding with month-end contribution timing up to 600-month bound.",
            warnings=[],
            result_id=str(uuid.uuid4()),
            generated_time=datetime.now(timezone.utc).isoformat()
        )
    else:
        last_invested = P + (PMT * max_months)
        last_growth = max(0.0, last_corpus - last_invested)

        return WhenReachGoalResponse(
            request_id=req.request_id or str(uuid.uuid4()),
            scenario_hash=scenario_hash,
            status="UNREACHABLE_WITHIN_LIMIT",
            years=None,
            months=None,
            total_months=None,
            projected_goal_age=None,
            final_corpus=round(last_corpus, 2),
            final_target=round(last_target, 2),
            total_invested=round(last_invested, 2),
            estimated_growth=round(last_growth, 2),
            assumptions_used=assumptions_payload,
            source_references=standard_sources,
            method_summary="Discrete monthly compounding with month-end contribution timing up to 600-month bound.",
            warnings=["Goal not reachable within the 50-year (600 months) search limit. Consider increasing contributions or target duration."],
            result_id=str(uuid.uuid4()),
            generated_time=datetime.now(timezone.utc).isoformat()
        )

