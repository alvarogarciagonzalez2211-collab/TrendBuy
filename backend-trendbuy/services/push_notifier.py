import logging
import os
from decimal import Decimal
from typing import Any

import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Dispositivo
from services.notifier import discount_summary, format_price_es


load_dotenv()

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_BATCH_SIZE = 100


def _chunk(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def send_expo_push(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not tokens:
        return []

    access_token = os.getenv("EXPO_ACCESS_TOKEN")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    tickets: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=10) as client:
        for batch in _chunk(tokens, EXPO_BATCH_SIZE):
            messages = [
                {"to": token, "title": title, "body": body, "data": data or {}} for token in batch
            ]
            response = await client.post(EXPO_PUSH_URL, json=messages, headers=headers)
            response.raise_for_status()
            tickets.extend(response.json().get("data", []))

    return tickets


async def notify_deal_push(
    session: AsyncSession,
    product_name: str,
    old_price: Decimal,
    new_price: Decimal,
    url: str,
) -> bool:
    result = await session.execute(select(Dispositivo).where(Dispositivo.activo.is_(True)))
    devices = list(result.scalars().all())

    if not devices:
        return False

    _, percent = discount_summary(old_price, new_price)
    title = "Chollo detectado"
    # Kept short (no €-saved figure, unlike the Telegram/email versions) -
    # push notification bodies get truncated by the OS after ~2 lines.
    body = f"{product_name}: {format_price_es(old_price)} € → {format_price_es(new_price)} € (-{percent}%)"

    try:
        tickets = await send_expo_push(
            [device.push_token for device in devices], title, body, data={"url": url}
        )
    except Exception as exc:
        logger.exception("Expo push failed for product=%s: %s", product_name, exc)
        return False

    for device, ticket in zip(devices, tickets):
        if ticket.get("status") == "error" and ticket.get("details", {}).get("error") == "DeviceNotRegistered":
            device.activo = False

    logger.info("Push alert sent to %s device(s) product=%s new_price=%s", len(devices), product_name, new_price)
    return True
