"""
Indian numbering system formatter for financial currency outputs.
Converts numbers into standard Indian Rupee notation (Lakhs, Crores) and compact representations.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def format_inr_exact(amount: Union[float, int, Decimal], include_symbol: bool = True, include_decimals: bool = False) -> str:
    """
    Formats a numeric value using the standard Indian comma grouping system:
    The rightmost three digits are grouped together, and thereafter groups of two digits.
    Example:
        1234567.89 -> '₹ 12,34,567.89' (or '₹ 12,34,568' if include_decimals=False)
        100000 -> '₹ 1,00,000'
        10000000 -> '₹ 1,00,00,000'
    """
    if amount is None:
        return "₹ 0" if include_symbol else "0"

    val = Decimal(str(amount))
    is_negative = val < 0
    val = abs(val)

    if include_decimals:
        val = val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        int_part, dec_part = f"{val:.2f}".split(".")
    else:
        val = val.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        int_part = str(int(val))
        dec_part = ""

    # Apply Indian comma grouping
    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last_three = int_part[-3:]
        remaining = int_part[:-3]
        # Group in 2s from right to left
        groups = []
        while remaining:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        formatted_int = ",".join(groups) + "," + last_three

    result = f"{formatted_int}.{dec_part}" if include_decimals and dec_part else formatted_int
    if is_negative:
        return f"-₹ {result}" if include_symbol else f"-{result}"
    return f"₹ {result}" if include_symbol else result


def format_inr_compact(amount: Union[float, int, Decimal], include_symbol: bool = True) -> str:
    """
    Formats a numeric value into compact Indian notation:
    >= 1 Crore (10^7) -> '₹ X.XX Cr'
    >= 1 Lakh (10^5)  -> '₹ X.XX L'
    >= 1 Thousand (10^3) -> '₹ X.XX K'
    < 1 Thousand      -> '₹ XXX'
    """
    if amount is None:
        return "₹ 0" if include_symbol else "0"

    val = float(amount)
    is_negative = val < 0
    abs_val = abs(val)

    prefix = "-" if is_negative else ""
    symbol = "₹ " if include_symbol else ""

    if abs_val >= 10_000_000:  # 1 Crore
        formatted = f"{abs_val / 10_000_000:.2f} Cr"
    elif abs_val >= 100_000:  # 1 Lakh
        formatted = f"{abs_val / 100_000:.2f} L"
    elif abs_val >= 1_000:    # 1 Thousand
        formatted = f"{abs_val / 1_000:.2f} K"
    else:
        formatted = f"{abs_val:.0f}"

    return f"{prefix}{symbol}{formatted}"


def format_percentage(rate: Union[float, Decimal], decimals: int = 1) -> str:
    """
    Formats a decimal rate (e.g., 0.055) into percentage string (e.g., '5.5%').
    """
    pct = float(rate) * 100
    return f"{pct:.{decimals}f}%"
