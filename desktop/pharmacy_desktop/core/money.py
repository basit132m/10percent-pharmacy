"""Money handling.

Every amount in the database is an integer number of **paisa** (1/100 of a
rupee). Integers cannot drift the way floats do, so a day of sales always adds
up to the invoice totals exactly. Conversion to and from the text a human types
happens only at the edges, here.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CURRENCY_SYMBOL = "Rs"
_HUNDRED = Decimal(100)


def to_paisa(value) -> int:
    """Parse user input (``"1,250.75"``, ``12.5``, ``Decimal``) into paisa."""
    if value is None or value == "":
        return 0
    if isinstance(value, int) and not isinstance(value, bool):
        return value * 100
    text = str(value).strip().replace(",", "").replace(CURRENCY_SYMBOL, "").strip()
    if not text:
        return 0
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:  # pragma: no cover - guarded by the UI
        raise ValueError(f"{value!r} is not a valid amount") from exc
    return int((amount * _HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_rupees(paisa: int) -> Decimal:
    """Paisa back to a rupee Decimal, for display and export."""
    return (Decimal(int(paisa)) / _HUNDRED).quantize(Decimal("0.01"))


def fmt(paisa: int, *, symbol: bool = False, grouping: bool = True) -> str:
    """Format paisa the way a receipt shows it: ``1,250.75``."""
    amount = to_rupees(paisa)
    negative = amount < 0
    amount = abs(amount)
    text = f"{amount:,.2f}" if grouping else f"{amount:.2f}"
    if negative:
        text = "-" + text
    return f"{CURRENCY_SYMBOL} {text}" if symbol else text


def percent_of(paisa: int, percent: float) -> int:
    """A percentage of an amount, rounded half-up to the nearest paisa."""
    if not percent:
        return 0
    value = (Decimal(int(paisa)) * Decimal(str(percent)) / _HUNDRED).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(value)


def round_to_rupee(paisa: int) -> int:
    """Round an amount to whole rupees — cash drawers have no paisa coins."""
    return int(
        (Decimal(int(paisa)) / _HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        * _HUNDRED
    )
