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


# --- JSON-LD generic extraction (scrape_generic_product's core) -------------

from scraper.scrapers import (  # noqa: E402
    KNOWN_STORES,
    detect_store_sections,
    extract_jsonld_product,
    parse_jsonld_price,
    resolve_search_scrapers,
    search_casadellibro,
    search_decathlon,
    search_pccomponentes,
    search_sprinter,
    store_display_name_for_url,
)


def test_parse_jsonld_price_machine_format():
    # JSON-LD uses '.' as decimal separator - parse_price (es-ES) would
    # misread "1439.99" as 143999.
    assert parse_jsonld_price("1439.99") == Decimal("1439.99")
    assert parse_jsonld_price(659.99) == Decimal("659.99")
    assert parse_jsonld_price(120) == Decimal("120.00")


def test_parse_jsonld_price_tolerates_es_formatting():
    assert parse_jsonld_price("1.439,99") == Decimal("1439.99")
    assert parse_jsonld_price("659,99 €") == Decimal("659.99")


def test_parse_jsonld_price_rejects_garbage():
    assert parse_jsonld_price(None) is None
    assert parse_jsonld_price("") is None
    assert parse_jsonld_price("gratis") is None
    assert parse_jsonld_price("0") is None


def test_extract_jsonld_product_plain_offer():
    payload = """
    {"@context": "https://schema.org", "@type": "Product",
     "name": "Silla ROSENTORP  blanca",
     "image": "https://example.com/silla.jpg",
     "offers": {"@type": "Offer", "price": "89.99", "priceCurrency": "EUR"}}
    """
    product = extract_jsonld_product([payload])
    assert product == {
        "name": "Silla ROSENTORP blanca",
        "price": Decimal("89.99"),
        "image_url": "https://example.com/silla.jpg",
    }


def test_extract_jsonld_product_inside_graph_with_aggregate_offer():
    # Magento/WooCommerce-style: Product nested in @graph, AggregateOffer.
    payload = """
    {"@context": "https://schema.org", "@graph": [
      {"@type": "Organization", "name": "Tienda"},
      {"@type": "Product", "name": "Perfume X",
       "image": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
       "offers": {"@type": "AggregateOffer", "lowPrice": 24.95, "highPrice": 39.95}}
    ]}
    """
    product = extract_jsonld_product([payload])
    assert product is not None
    assert product["price"] == Decimal("24.95")
    assert product["image_url"] == "https://example.com/a.jpg"


def test_extract_jsonld_product_skips_invalid_payloads():
    assert extract_jsonld_product(["not json", '{"@type": "BreadcrumbList"}']) is None


def test_extract_jsonld_product_ignores_product_without_price():
    payloads = [
        '{"@type": "Product", "name": "Sin precio"}',
        '{"@type": "Product", "name": "Con precio", "offers": {"price": "10.00"}}',
    ]
    product = extract_jsonld_product(payloads)
    assert product is not None
    assert product["name"] == "Con precio"


# --- Section routing for the new stores --------------------------------------


def test_deportes_query_routes_to_decathlon_and_sprinter():
    scrapers = resolve_search_scrapers("bicicleta de montaña")
    assert search_decathlon in scrapers
    assert search_sprinter in scrapers
    assert search_pccomponentes not in scrapers


def test_libros_query_routes_to_casadellibro():
    scrapers = resolve_search_scrapers("novela histórica")
    assert search_casadellibro in scrapers


def test_unrecognized_query_keeps_tech_default():
    scrapers = resolve_search_scrapers("iphone 15")
    assert search_pccomponentes in scrapers
    assert search_decathlon not in scrapers


def test_detect_sections_multi_match():
    assert set(detect_store_sections("libro de yoga")) == {"deportes", "libros"}


# --- Store registry -----------------------------------------------------------


def test_store_display_name_for_known_urls():
    assert store_display_name_for_url("https://www.decathlon.es/es/p/bici/123.html") == "Decathlon"
    assert store_display_name_for_url("https://www.casadellibro.com/libro/123") == "Casa del Libro"


def test_store_display_name_falls_back_to_host():
    assert store_display_name_for_url("https://www.tienda-rara.example/p/1") == "www.tienda-rara.example"


def test_known_stores_cover_original_four():
    for marker in ("amazon", "pccomponentes", "mediamarkt", "worten"):
        assert marker in KNOWN_STORES
