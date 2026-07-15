import logging
import os
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


logger = logging.getLogger(__name__)

# Amazon Associates: a plain ?tag= query param, no redirect needed.
AMAZON_TAG = os.getenv("AFFILIATE_AMAZON_TAG", "").strip()

# PcComponentes and MediaMarkt.es run their Spanish affiliate programs on two
# DIFFERENT networks - confirmed live (2026-07-15): PcComponentes is on Awin
# (merchant id 20982 for Spain, public info), MediaMarkt.es is on Tradedoubler.
# Worten.es wasn't confirmed on either at the time this was written - both
# blocks below are wired up so whichever one turns out to be right just needs
# its id filled in, no code change. Every value defaults to blank = no-op.
AWIN_PUBLISHER_ID = os.getenv("AFFILIATE_AWIN_PUBLISHER_ID", "").strip()
AWIN_MERCHANT_IDS = {
    # 20982 is PcComponentes' public Spain merchant id on Awin - safe to
    # default, it's not a secret, only AWIN_PUBLISHER_ID (your own account) is.
    "pccomponentes": os.getenv("AFFILIATE_AWIN_MID_PCCOMPONENTES", "20982").strip(),
    "worten": os.getenv("AFFILIATE_AWIN_MID_WORTEN", "").strip(),
}

TRADEDOUBLER_SITE_ID = os.getenv("AFFILIATE_TRADEDOUBLER_SITE_ID", "").strip()
TRADEDOUBLER_PROGRAM_IDS = {
    "mediamarkt": os.getenv("AFFILIATE_TRADEDOUBLER_PID_MEDIAMARKT", "").strip(),
    "worten": os.getenv("AFFILIATE_TRADEDOUBLER_PID_WORTEN", "").strip(),
}


def _detect_store(url: str, store_hint: str | None) -> str | None:
    # Hostname first - reliable regardless of how EnlaceTienda.tienda was
    # spelled/cased when scraped. Falls back to the store hint only for the
    # rare case of a malformed/relative url.
    host = urlsplit(url).netloc.lower()
    for key in ("amazon", "pccomponentes", "mediamarkt", "worten"):
        if key in host:
            return key

    hint = (store_hint or "").lower()
    for key in ("amazon", "pccomponentes", "mediamarkt", "worten"):
        if key in hint:
            return key

    return None


def _with_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _awin_deep_link(url: str, merchant_id: str) -> str:
    # Standard Awin deep-link redirect format - the click is tracked at
    # awin1.com before bouncing to the real destination.
    return (
        "https://www.awin1.com/cread.php"
        f"?awinmid={merchant_id}&awinaffid={AWIN_PUBLISHER_ID}&p={quote(url, safe='')}"
    )


def _tradedoubler_deep_link(url: str, program_id: str) -> str:
    # Tradedoubler's redirect format: p=program id, a=site id (your account,
    # shared across every Tradedoubler program), url=destination.
    return (
        "https://clk.tradedoubler.com/click"
        f"?p={program_id}&a={TRADEDOUBLER_SITE_ID}&url={quote(url, safe='')}"
    )


def tag_url(url: str | None, store: str | None = None) -> str | None:
    # Single boundary for turning a raw scraped store URL into whatever a
    # human actually clicks (search results, dashboard, email/Telegram
    # alerts) - every affiliate program lives here so nothing else in the
    # codebase needs to know these details. Untagged (missing env vars) is a
    # safe no-op: the original url passes through unchanged.
    if not url:
        return url

    store_key = _detect_store(url, store)

    if store_key == "amazon" and AMAZON_TAG:
        return _with_query_param(url, "tag", AMAZON_TAG)

    if store_key in AWIN_MERCHANT_IDS:
        merchant_id = AWIN_MERCHANT_IDS[store_key]
        if AWIN_PUBLISHER_ID and merchant_id:
            return _awin_deep_link(url, merchant_id)

    if store_key in TRADEDOUBLER_PROGRAM_IDS:
        program_id = TRADEDOUBLER_PROGRAM_IDS[store_key]
        if TRADEDOUBLER_SITE_ID and program_id:
            return _tradedoubler_deep_link(url, program_id)

    return url
