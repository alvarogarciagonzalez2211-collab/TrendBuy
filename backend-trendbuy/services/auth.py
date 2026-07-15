import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Sesion, TokenAcceso, Usuario


logger = logging.getLogger(__name__)

LOGIN_TOKEN_TTL_MINUTES = 15
SESSION_TTL_DAYS = 30
SESSION_COOKIE_NAME = "trendbuy_session"
TELEGRAM_LINK_CODE_TTL_MINUTES = 10

# Only true behind real HTTPS - local docker compose serves the frontend over
# plain http://localhost, and browsers silently refuse to store/send a
# Secure cookie set over a non-HTTPS origin. Flip to true via env once this
# runs behind a real public domain + TLS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

_SECRET_KEY = os.getenv("SECRET_KEY")
if not _SECRET_KEY:
    # Falls back to a random key generated once per process so unsubscribe
    # tokens still work within a single run - but every restart invalidates
    # every link already sent, so production MUST set SECRET_KEY explicitly
    # in .env (any long random string, e.g. `python -c "import secrets;
    # print(secrets.token_hex(32))"`).
    logger.warning("SECRET_KEY not set - using an ephemeral key, unsubscribe links won't survive a restart.")
    _SECRET_KEY = secrets.token_hex(32)


def generate_token() -> str:
    # 32 random bytes, url-safe base64 - unguessable and short enough to fit
    # comfortably in a URL query string for the magic-link case.
    return secrets.token_urlsafe(32)


async def get_or_create_usuario(session: AsyncSession, email: str) -> Usuario:
    normalized = email.strip().lower()
    result = await session.execute(select(Usuario).where(Usuario.email == normalized))
    usuario = result.scalar_one_or_none()

    if usuario is None:
        usuario = Usuario(email=normalized)
        session.add(usuario)
        await session.flush()

    return usuario


async def create_login_token(session: AsyncSession, usuario: Usuario) -> str:
    token = generate_token()
    expira_en = datetime.utcnow() + timedelta(minutes=LOGIN_TOKEN_TTL_MINUTES)
    session.add(TokenAcceso(usuario_id=usuario.id, token=token, expira_en=expira_en))
    await session.commit()
    return token


async def consume_login_token(session: AsyncSession, token: str) -> Usuario | None:
    # Single-use: usado flips to True on first successful confirm, so a
    # replayed link (e.g. an email client's link-prescanning bot opening it
    # before the real user clicks "confirmar") can't grant a second session.
    result = await session.execute(select(TokenAcceso).where(TokenAcceso.token == token))
    login_token = result.scalar_one_or_none()

    if login_token is None or login_token.usado or login_token.expira_en < datetime.utcnow():
        return None

    login_token.usado = True

    result = await session.execute(select(Usuario).where(Usuario.id == login_token.usuario_id))
    usuario = result.scalar_one_or_none()
    if usuario is None:
        return None

    usuario.ultimo_login = datetime.utcnow()
    await session.commit()
    return usuario


async def create_session(session: AsyncSession, usuario: Usuario) -> str:
    token = generate_token()
    expira_en = datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)
    session.add(Sesion(usuario_id=usuario.id, token=token, expira_en=expira_en))
    await session.commit()
    return token


async def get_usuario_from_session_token(session: AsyncSession, token: str) -> Usuario | None:
    result = await session.execute(select(Sesion).where(Sesion.token == token))
    sesion = result.scalar_one_or_none()

    if sesion is None or sesion.expira_en < datetime.utcnow():
        return None

    result = await session.execute(select(Usuario).where(Usuario.id == sesion.usuario_id))
    return result.scalar_one_or_none()


async def delete_session(session: AsyncSession, token: str) -> None:
    result = await session.execute(select(Sesion).where(Sesion.token == token))
    sesion = result.scalar_one_or_none()

    if sesion is not None:
        await session.delete(sesion)
        await session.commit()


def generate_unsubscribe_token(usuario_id: int) -> str:
    # Stateless (no DB column/lookup needed): HMAC-signed user id, so the
    # link in every deal-alert email stays valid indefinitely without being
    # single-use like the login token above - unsubscribing is idempotent
    # and low-stakes, it doesn't need that same replay protection.
    user_id_str = str(usuario_id)
    signature = hmac.new(_SECRET_KEY.encode(), user_id_str.encode(), hashlib.sha256).hexdigest()
    return f"{user_id_str}.{signature}"


def verify_unsubscribe_token(token: str) -> int | None:
    try:
        user_id_str, signature = token.split(".", 1)
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        return None

    expected = hmac.new(_SECRET_KEY.encode(), user_id_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    return user_id


async def generate_telegram_link_code(session: AsyncSession, usuario: Usuario) -> str:
    # Short code (fits comfortably in a /start deep-link payload, which
    # Telegram caps at 64 chars) - re-requesting a code overwrites any
    # previous unused one, so only the latest link the user opened works.
    code = secrets.token_urlsafe(6)
    usuario.telegram_link_code = code
    usuario.telegram_link_code_expira_en = datetime.utcnow() + timedelta(minutes=TELEGRAM_LINK_CODE_TTL_MINUTES)
    await session.commit()
    return code


async def consume_telegram_link_code(session: AsyncSession, code: str, chat_id: int) -> Usuario | None:
    result = await session.execute(select(Usuario).where(Usuario.telegram_link_code == code))
    usuario = result.scalar_one_or_none()

    if usuario is None or usuario.telegram_link_code_expira_en is None:
        return None
    if usuario.telegram_link_code_expira_en < datetime.utcnow():
        return None

    # A chat_id can only belong to one account at a time (unique constraint) -
    # re-linking the same Telegram chat to a different email transfers it
    # rather than erroring out.
    previous_owner = await session.execute(select(Usuario).where(Usuario.telegram_chat_id == chat_id))
    previous_usuario = previous_owner.scalar_one_or_none()
    if previous_usuario is not None and previous_usuario.id != usuario.id:
        previous_usuario.telegram_chat_id = None

    usuario.telegram_chat_id = chat_id
    usuario.telegram_link_code = None
    usuario.telegram_link_code_expira_en = None
    await session.commit()
    return usuario


async def unlink_telegram(session: AsyncSession, usuario: Usuario) -> None:
    usuario.telegram_chat_id = None
    await session.commit()


async def get_usuario_by_telegram_chat_id(session: AsyncSession, chat_id: int) -> Usuario | None:
    result = await session.execute(select(Usuario).where(Usuario.telegram_chat_id == chat_id))
    return result.scalar_one_or_none()
