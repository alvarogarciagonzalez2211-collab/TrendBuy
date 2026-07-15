import logging
import os
from decimal import ROUND_HALF_UP, Decimal

import httpx
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


def format_price_es(value: Decimal) -> str:
    # "1234.56" (Python's default Decimal str) reads as wrong/foreign to a
    # Spanish reader, who expects "." as the thousands separator and "," as
    # the decimal one ("1.234,56") - every price shown in a message the user
    # actually reads (Telegram/email/push) should go through this, not the
    # plain str()/f"{:.2f}" used for machine-readable API payloads.
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    integer_part, _, decimal_part = f"{abs(quantized):.2f}".partition(".")
    grouped = f"{int(integer_part):,}".replace(",", ".")
    return f"{sign}{grouped},{decimal_part}"


def discount_summary(old_price: Decimal, new_price: Decimal) -> tuple[Decimal, Decimal]:
    # Shared by every "before/after" message below so the \u20ac saved and the %
    # shown are always derived from the exact same two prices being quoted in
    # that message - never a percentage computed elsewhere/earlier that could
    # drift from the specific old/new figures the recipient is reading.
    savings = old_price - new_price
    percent = (savings / old_price * 100) if old_price > 0 else Decimal("0")
    return savings, percent.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _deal_alert_message(product_name: str, old_price: Decimal, new_price: Decimal, url: str) -> str:
    savings, percent = discount_summary(old_price, new_price)
    return (
        f"\U0001f6a8 CHOLLO DETECTADO\n"
        f"{product_name}\n"
        f"{format_price_es(old_price)} \u20ac \u2192 {format_price_es(new_price)} \u20ac "
        f"(-{percent}% \u00b7 ahorras {format_price_es(savings)} \u20ac)\n"
        f"{url}"
    )


async def send_telegram_message(chat_id: int | str, text: str) -> bool:
    # Shared low-level sender: both the broadcast bot (fixed TELEGRAM_CHAT_ID,
    # below) and per-user personal alerts (services/favorite_notifier.py,
    # dynamic chat_id from Usuario.telegram_chat_id) go through this.
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.warning("Telegram message skipped: TELEGRAM_BOT_TOKEN is missing.")
        return False

    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            endpoint,
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": False,
            },
        )
        response.raise_for_status()

    return True


async def send_telegram_alert(
    product_name: str,
    old_price: Decimal,
    new_price: Decimal,
    url: str,
) -> bool:
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not chat_id:
        logger.warning("Telegram alert skipped: TELEGRAM_CHAT_ID is missing.")
        return False

    return await send_telegram_message(chat_id, _deal_alert_message(product_name, old_price, new_price, url))


async def send_telegram_deal_alert(
    chat_id: int,
    product_name: str,
    old_price: Decimal,
    new_price: Decimal,
    url: str,
) -> bool:
    # Per-user variant of send_telegram_alert above, used by
    # services/favorite_notifier.py once a user links their own chat -
    # replaces the email alert for that user, doesn't touch the broadcast one.
    return await send_telegram_message(chat_id, _deal_alert_message(product_name, old_price, new_price, url))


_bot_username_cache: str | None = None


async def get_bot_username() -> str | None:
    # Cached for the process lifetime - the bot's username never changes at
    # runtime, and this avoids an extra Telegram API round trip on every
    # "vincular Telegram" click.
    global _bot_username_cache
    if _bot_username_cache is not None:
        return _bot_username_cache

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return None

    endpoint = f"https://api.telegram.org/bot{bot_token}/getMe"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(endpoint)
        response.raise_for_status()
        data = response.json()

    username = data.get("result", {}).get("username")
    if username:
        _bot_username_cache = username
    return username


async def set_telegram_webhook(webhook_url: str, secret_token: str) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return False

    endpoint = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            endpoint,
            json={"url": webhook_url, "secret_token": secret_token, "allowed_updates": ["message"]},
        )
        response.raise_for_status()
        data = response.json()

    if not data.get("ok"):
        logger.warning("setWebhook failed: %s", data)
    return bool(data.get("ok"))
