from services.search import is_supported_store_url


def test_amazon_url_is_supported():
    assert is_supported_store_url("https://www.amazon.es/dp/B0ABCDEFGH")


def test_pccomponentes_url_is_supported():
    assert is_supported_store_url("https://www.pccomponentes.com/producto-x")


def test_mediamarkt_url_is_supported():
    assert is_supported_store_url("https://www.mediamarkt.es/es/product/_producto-123.html")


def test_worten_url_is_supported():
    assert is_supported_store_url("https://www.worten.es/producto-z")


def test_unsupported_store_url_is_rejected():
    assert not is_supported_store_url("https://www.elcorteingles.es/producto-z")


def test_malformed_url_is_rejected():
    assert not is_supported_store_url("not a url")


def test_new_scraped_stores_are_supported_for_tracking():
    # KNOWN_STORES drives this - every store the keyword search can discover
    # must also be trackable by URL (generic JSON-LD detail scraper).
    for url in (
        "https://www.ikea.com/es/es/p/producto-1",
        "https://www.vinted.es/items/123",
        "https://www.druni.es/producto-y",
        "https://www.decathlon.es/es/p/bici/123.html",
        "https://www.sprintersports.com/producto",
        "https://www.primor.eu/es_es/producto.html",
        "https://www.casadellibro.com/libro/123",
    ):
        assert is_supported_store_url(url), url
