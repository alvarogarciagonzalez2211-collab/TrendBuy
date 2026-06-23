import logging
import os
from decimal import Decimal

import httpx
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger(__name__)


def money(value: Decimal) -> str:
    return f"{value:.2f}"


async def send_telegram_alert(
    product_name: str,
    old_price: Decimal,
    new_price: Decimal,
    url: str,
) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.warning("Telegram alert skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
        return False

    message = (
        f"\U0001f6a8 CHOLLO DETECTADO\n"
        f"{product_name} ha bajado de {money(old_price)}\u20ac a {money(new_price)}\u20ac.\n"
        f"{url}"
    )
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            endpoint,
            json={
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": False,
            },
        )
        response.raise_for_status()

    return True
