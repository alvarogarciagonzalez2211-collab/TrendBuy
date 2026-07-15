from decimal import Decimal

from scraper.scrapers import cheapest_price_in, parse_price, parse_price_lines


def test_parse_price_thousands_separator():
    # Live bug: "1.439€" was parsed as 143.00 (the thousands dot was
    # mistaken for a decimal point and everything after it truncated).
    assert parse_price("1.439€") == Decimal("1439.00")


def test_parse_price_no_thousands_separator():
    assert parse_price("29,99 €") == Decimal("29.99")


def test_parse_price_whole_euros_no_decimals():
    assert parse_price("659 €") == Decimal("659.00")


def test_parse_price_none_on_empty():
    assert parse_price(None) is None
    assert parse_price("") is None


def test_parse_price_lines_excludes_discount_badges():
    # Live bug: a "-15%" discount badge on its own line matched the price
    # regex and was parsed as a 15.00 EUR price.
    raw = "1.439,00 €\n-15%\n52,26 €/mes"
    prices = parse_price_lines(raw)
    assert prices == [Decimal("1439.00")]


def test_cheapest_price_in_picks_lower_regardless_of_order():
    # MediaMarkt lists the struck-through original price first,
    # PcComponentes lists the current (lower) price first - order-independent.
    assert cheapest_price_in("999,00 €\n799,00 €") == Decimal("799.00")
    assert cheapest_price_in("799,00 €\n999,00 €") == Decimal("799.00")


def test_cheapest_price_in_none_when_nothing_valid():
    assert cheapest_price_in("-20%\n/mes") is None
