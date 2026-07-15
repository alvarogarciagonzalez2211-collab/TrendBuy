import logging
import os
from decimal import Decimal

import httpx
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def _deal_alert_message(product_name: str, old_price: Decimal, new_price: Decimal, url: str) -> str:
    return (
        f"\U0001f6a8 CHOLLO DETECTADO\n"
        f"{product_name} ha bajado de {money(old_price)}\u20ac a {money(new_price)}\u20ac.\n"
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
