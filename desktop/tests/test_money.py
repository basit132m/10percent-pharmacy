from decimal import Decimal

import pytest

from pharmacy_desktop.core.money import fmt, percent_of, round_to_rupee, to_paisa, to_rupees


@pytest.mark.parametrize(
    "text,expected",
    [
        ("10", 1000),
        ("10.50", 1050),
        ("1,250.75", 125075),
        ("0.01", 1),
        ("Rs 99.99", 9999),
        ("", 0),
        (12.5, 1250),
        (Decimal("3.335"), 334),  # half-up, never bankers' rounding
    ],
)
def test_to_paisa_parses_what_a_person_types(text, expected):
    assert to_paisa(text) == expected


def test_round_trip_keeps_two_decimals():
    assert to_rupees(125075) == Decimal("1250.75")
    assert fmt(125075) == "1,250.75"
    assert fmt(-5000, symbol=True) == "Rs -50.00"


def test_ten_percent_of_a_bill():
    assert percent_of(to_paisa("1234.56"), 10) == to_paisa("123.46")
    assert percent_of(to_paisa("100"), 0) == 0


def test_hundred_ten_percent_discounts_add_up_exactly():
    # The float trap this module exists to avoid: 0.1 * 3 != 0.3
    total = sum(percent_of(to_paisa("0.30"), 10) for _ in range(100))
    assert total == 300  # 100 x 3 paisa, exactly


def test_round_off_to_the_nearest_rupee():
    assert round_to_rupee(to_paisa("99.49")) == to_paisa("99")
    assert round_to_rupee(to_paisa("99.50")) == to_paisa("100")
