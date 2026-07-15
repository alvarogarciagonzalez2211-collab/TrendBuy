from decimal import Decimal

from services.notifier import discount_summary, format_price_es


def test_format_price_es_adds_spanish_thousands_and_decimal_separators():
    assert format_price_es(Decimal("1234.56")) == "1.234,56"


def test_format_price_es_small_amount():
    assert format_price_es(Decimal("10")) == "10,00"


def test_format_price_es_rounds_half_up():
    assert format_price_es(Decimal("9.995")) == "10,00"


def test_discount_summary_matches_the_exact_prices_quoted():
    savings, percent = discount_summary(Decimal("100.00"), Decimal("90.00"))
    assert savings == Decimal("10.00")
    assert percent == Decimal("10")


def test_discount_summary_real_ten_euro_drop_is_not_reported_as_ninety_percent():
    # Regression guard for the exact confusion this was fixed for: a genuine
    # 10 EUR drop must be reported as a 10 EUR / small-percent drop, never
    # mixed up with an unrelated "100 -> 10" style jump.
    savings, percent = discount_summary(Decimal("30.00"), Decimal("20.00"))
    assert savings == Decimal("10.00")
    assert percent == Decimal("33")
