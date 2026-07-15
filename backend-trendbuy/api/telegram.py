import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from models.database import Usuario, get_session
from services.auth import consume_telegram_link_code, generate_telegram_link_code, unlink_telegram
from services.notifier import get_bot_username, send_telegram_message


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["telegram"])

TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")


async def _reply(chat_id: int, text: str) -> None:
    # Best-effort: a send failure here (e.g. the user blocked the bot right
    # after messaging it) must not turn into a 500 on the webhook itself -
    # Telegram treats a non-2xx as "delivery failed" and retries the same
    # update indefinitely, which would wedge the webhook on that one update.
    try:
        await send_telegram_message(chat_id, text)
    except Exception:
        logger.exception("Failed to reply to Telegram chat_id=%s", chat_id)


@router.post("/auth/telegram/link-code")
async def create_telegram_link_code(
    usuario: Usuario = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    bot_username = await get_bot_username()
    if bot_username is None:
        raise HTTPException(status_code=503, detail="El bot de Telegram no esta configurado.")

    code = await generate_telegram_link_code(session, usuario)
    return {"deep_link": f"https://t.me/{bot_username}?start={code}"}


@router.post("/auth/telegram/unlink")
async def remove_telegram_link(
    usuario: Usuario = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    await unlink_telegram(session, usuario)
    return {"ok": True}


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    # Telegram echoes back the secret_token we passed to setWebhook on every
    # request - the only way to confirm a POST here really came from
    # Telegram and not someone guessing the (unauthenticated-by-design) URL.
    if not TELEGRAM_WEBHOOK_SECRET or x_telegram_bot_api_secret_token != TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    update = await request.json()
    message = update.get("message")
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None or not text:
        return {"ok": True}

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""

        if not code:
            await _reply(
                chat_id,
                "Para vincular tu cuenta, pulsa el boton \"Vincular Telegram\" en trendbuy y abre el enlace que te da.",
            )
            return {"ok": True}

        usuario = await consume_telegram_link_code(session, code, chat_id)
        if usuario is None:
            await _reply(chat_id, "Este enlace de vinculacion no es valido o ha caducado. Pide uno nuevo desde trendbuy.")
        else:
            await _reply(
                chat_id,
                f"Listo, {usuario.email} vinculado. A partir de ahora tus avisos de bajada de precio llegaran aqui.",
            )
        return {"ok": True}

    if text == "/stop":
        result = await session.execute(select(Usuario).where(Usuario.telegram_chat_id == chat_id))
        usuario = result.scalar_one_or_none()
        if usuario is not None:
            usuario.notificaciones_activas = False
            await session.commit()
            await _reply(chat_id, "Notificaciones desactivadas. Puedes reactivarlas desde trendbuy.")
        return {"ok": True}

    return {"ok": True}
