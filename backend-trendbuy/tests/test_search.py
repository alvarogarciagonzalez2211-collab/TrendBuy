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
