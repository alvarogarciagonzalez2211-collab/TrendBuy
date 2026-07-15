import importlib
from urllib.parse import quote

import services.affiliate as affiliate


ENV_KEYS = [
    "AFFILIATE_AMAZON_TAG",
    "AFFILIATE_AWIN_PUBLISHER_ID",
    "AFFILIATE_AWIN_MID_PCCOMPONENTES",
    "AFFILIATE_AWIN_MID_WORTEN",
    "AFFILIATE_TRADEDOUBLER_SITE_ID",
    "AFFILIATE_TRADEDOUBLER_PID_MEDIAMARKT",
    "AFFILIATE_TRADEDOUBLER_PID_WORTEN",
]


def reload_with_env(monkeypatch, **env):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(affiliate)


def test_no_env_configured_is_a_noop(monkeypatch):
    mod = reload_with_env(monkeypatch)
    url = "https://www.amazon.es/dp/B0ABCDEFGH"
    assert mod.tag_url(url, "Amazon") == url


def test_amazon_tag_added_to_bare_url(monkeypatch):
    mod = reload_with_env(monkeypatch, AFFILIATE_AMAZON_TAG="trendbuy-21")
    tagged = mod.tag_url("https://www.amazon.es/dp/B0ABCDEFGH", "Amazon")
    assert tagged == "https://www.amazon.es/dp/B0ABCDEFGH?tag=trendbuy-21"


def test_amazon_tag_preserves_existing_query_params(monkeypatch):
    mod = reload_with_env(monkeypatch, AFFILIATE_AMAZON_TAG="trendbuy-21")
    tagged = mod.tag_url("https://www.amazon.es/dp/B0ABCDEFGH?psc=1", "Amazon")
    assert "psc=1" in tagged
    assert "tag=trendbuy-21" in tagged


def test_pccomponentes_defaults_to_public_awin_merchant_id(monkeypatch):
    # 20982 is PcComponentes' real, publicly-listed Spain merchant id on Awin -
    # only the publisher id (the user's own account) should be required.
    mod = reload_with_env(monkeypatch, AFFILIATE_AWIN_PUBLISHER_ID="12345")
    original = "https://www.pccomponentes.com/producto-x"
    tagged = mod.tag_url(original, "PcComponentes")
    assert tagged.startswith("https://www.awin1.com/cread.php?")
    assert "awinmid=20982" in tagged
    assert "awinaffid=12345" in tagged
    assert f"p={quote(original, safe='')}" in tagged


def test_awin_wrap_skipped_without_publisher_id(monkeypatch):
    mod = reload_with_env(monkeypatch)
    original = "https://www.pccomponentes.com/producto-x"
    assert mod.tag_url(original, "PcComponentes") == original


def test_mediamarkt_uses_tradedoubler_not_awin(monkeypatch):
    mod = reload_with_env(
        monkeypatch,
        AFFILIATE_TRADEDOUBLER_SITE_ID="999",
        AFFILIATE_TRADEDOUBLER_PID_MEDIAMARKT="555",
        AFFILIATE_AWIN_PUBLISHER_ID="12345",
        AFFILIATE_AWIN_MID_WORTEN="6789",
    )
    original = "https://www.mediamarkt.es/producto-y"
    tagged = mod.tag_url(original, "MediaMarkt")
    assert tagged.startswith("https://clk.tradedoubler.com/click?")
    assert "p=555" in tagged
    assert "a=999" in tagged
    assert f"url={quote(original, safe='')}" in tagged


def test_mediamarkt_skipped_without_tradedoubler_ids(monkeypatch):
    mod = reload_with_env(monkeypatch, AFFILIATE_AWIN_PUBLISHER_ID="12345")
    original = "https://www.mediamarkt.es/producto-y"
    assert mod.tag_url(original, "MediaMarkt") == original


def test_worten_supports_either_network_awin(monkeypatch):
    mod = reload_with_env(monkeypatch, AFFILIATE_AWIN_PUBLISHER_ID="12345", AFFILIATE_AWIN_MID_WORTEN="42")
    tagged = mod.tag_url("https://www.worten.es/producto-z", "Worten")
    assert tagged.startswith("https://www.awin1.com/cread.php?")
    assert "awinmid=42" in tagged


def test_worten_supports_either_network_tradedoubler(monkeypatch):
    mod = reload_with_env(
        monkeypatch, AFFILIATE_TRADEDOUBLER_SITE_ID="999", AFFILIATE_TRADEDOUBLER_PID_WORTEN="77"
    )
    tagged = mod.tag_url("https://www.worten.es/producto-z", "Worten")
    assert tagged.startswith("https://clk.tradedoubler.com/click?")
    assert "p=77" in tagged


def test_unknown_store_passes_through_unchanged(monkeypatch):
    mod = reload_with_env(monkeypatch, AFFILIATE_AMAZON_TAG="trendbuy-21", AFFILIATE_AWIN_PUBLISHER_ID="12345")
    original = "https://www.elcorteingles.es/producto-z"
    assert mod.tag_url(original, "El Corte Ingles") == original


def test_none_url_passes_through(monkeypatch):
    mod = reload_with_env(monkeypatch)
    assert mod.tag_url(None, "Amazon") is None


def test_store_detection_falls_back_to_hint_for_relative_url(monkeypatch):
    mod = reload_with_env(monkeypatch, AFFILIATE_AMAZON_TAG="trendbuy-21")
    assert mod.tag_url("/dp/B0ABCDEFGH", "Amazon.es") == "/dp/B0ABCDEFGH?tag=trendbuy-21"


def test_any_store_activates_via_generic_awin_env_var(monkeypatch):
    # No code change needed to monetize a new store: any
    # AFFILIATE_AWIN_MID_<STORE> env var registers <store> for detection.
    mod = reload_with_env(monkeypatch, AFFILIATE_AWIN_PUBLISHER_ID="12345", AFFILIATE_AWIN_MID_DECATHLON="7777")
    original = "https://www.decathlon.es/es/p/bicicleta-x/123.html"
    tagged = mod.tag_url(original, "Decathlon")
    assert tagged.startswith("https://www.awin1.com/cread.php?")
    assert "awinmid=7777" in tagged


def test_any_store_activates_via_generic_tradedoubler_env_var(monkeypatch):
    mod = reload_with_env(
        monkeypatch,
        AFFILIATE_TRADEDOUBLER_SITE_ID="999",
        AFFILIATE_TRADEDOUBLER_PID_CASADELLIBRO="4242",
    )
    tagged = mod.tag_url("https://www.casadellibro.com/libro-x/123", "Casa del Libro")
    assert tagged.startswith("https://clk.tradedoubler.com/click?")
    assert "p=4242" in tagged


def test_multiword_store_hint_matches_hostname_style_key(monkeypatch):
    # Display names carry spaces ("Casa del Libro"); env keys are
    # hostname-style (casadellibro) - the hint fallback must bridge that.
    mod = reload_with_env(
        monkeypatch,
        AFFILIATE_TRADEDOUBLER_SITE_ID="999",
        AFFILIATE_TRADEDOUBLER_PID_CASADELLIBRO="4242",
    )
    tagged = mod.tag_url("/libro-x/123", "Casa del Libro")
    assert tagged.startswith("https://clk.tradedoubler.com/click?")


def test_unconfigured_generic_store_passes_through(monkeypatch):
    mod = reload_with_env(monkeypatch, AFFILIATE_AWIN_PUBLISHER_ID="12345")
    original = "https://www.decathlon.es/es/p/bicicleta-x/123.html"
    assert mod.tag_url(original, "Decathlon") == original
