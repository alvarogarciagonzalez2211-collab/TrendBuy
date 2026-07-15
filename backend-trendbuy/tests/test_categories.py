from services.categories import match_categories


def test_matches_moviles():
    assert "Moviles" in match_categories("Apple iPhone 15 Pro 128GB Negro")


def test_matches_televisores():
    assert "Televisores" in match_categories("Samsung Smart TV 55'' QLED 4K")


def test_matches_accented_keyword_case_insensitive():
    assert "Portatiles" in match_categories("PORTÁTIL Lenovo IdeaPad 15.6''")


def test_unmatched_product_returns_empty():
    assert match_categories("Bolsa de basura biodegradable 50 unidades") == []


def test_can_match_multiple_categories():
    # A gaming laptop plausibly matches both Portatiles and Informatica -
    # match_categories intentionally returns every match, not just one.
    matches = match_categories("Portatil gaming con tarjeta grafica dedicada")
    assert "Portatiles" in matches
    assert "Informatica" in matches
