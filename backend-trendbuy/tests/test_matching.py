from services.matching import family_signature, group_by_family, same_family


def test_same_product_different_store_wording_merges():
    a = family_signature("Apple iPhone 15 128GB Negro")
    b = family_signature("iPhone 15 de 128 GB, Negro - Libre")
    assert same_family(a, b)


def test_different_generation_does_not_merge():
    # Live bug: a short fuzzy base ("iphone") barely moves when the
    # generation number differs, so it must be an exact-match component,
    # not folded into the fuzzy comparison.
    a = family_signature("iPhone 14 128GB Negro")
    b = family_signature("iPhone 15 128GB Negro")
    assert not same_family(a, b)


def test_pro_max_does_not_merge_with_pro():
    a = family_signature("iPhone 15 Pro 128GB")
    b = family_signature("iPhone 15 Pro Max 128GB")
    assert not same_family(a, b)


def test_different_color_does_not_merge():
    # Live bug: colors were being stripped as "noise" and merged into one
    # family spanning a ~1400-2980EUR range across every color.
    a = family_signature("iPhone 17 Pro Max 256GB Negro")
    b = family_signature("iPhone 17 Pro Max 256GB Azul")
    assert not same_family(a, b)


def test_different_storage_does_not_merge():
    a = family_signature("Samsung Galaxy S24 128GB")
    b = family_signature("Samsung Galaxy S24 256GB")
    assert not same_family(a, b)


def test_screen_size_does_not_pollute_numbers_signature():
    # Live bug: SCREEN_SIZE_RE must strip "6.1''" before punctuation is
    # stripped to plain spaces, otherwise it degrades to bare digit tokens
    # ("6", "1") that get treated as generation numbers and wrongly split
    # one real model into two families. Asserted directly on `numbers`
    # rather than via same_family(), since an unrelated real word ("Pantalla")
    # would also legitimately move the fuzzy `base` comparison - not what
    # this test is about.
    signature = family_signature("iPhone 15 6.1'' 128GB Negro")
    assert signature.numbers == frozenset({"15"})


def test_group_by_family_clusters_correctly():
    items = [
        {"store": "Amazon", "name": "iPhone 15 128GB Negro", "price": 799, "url": "a1"},
        {"store": "PcComponentes", "name": "iPhone 15 de 128 GB Negro", "price": 789, "url": "a2"},
        {"store": "Amazon", "name": "iPhone 15 Pro Max 256GB Negro", "price": 1399, "url": "b1"},
        {"store": "Worten", "name": "Samsung Galaxy S24 128GB", "price": 699, "url": "c1"},
    ]

    families = group_by_family(items)
    sizes = sorted(len(family) for family in families)

    assert sizes == [1, 1, 2]
