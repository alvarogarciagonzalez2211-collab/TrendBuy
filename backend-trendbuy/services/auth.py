import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Sesion, TokenAcceso, Usuario


LOGIN_TOKEN_TTL_MINUTES = 15
SESSION_TTL_DAYS = 30
SESSION_COOKIE_NAME = "trendbuy_session"

# Only true behind real HTTPS - local docker compose serves the frontend over
# plain http://localhost, and browsers silently refuse to store/send a
# Secure cookie set over a non-HTTPS origin. Flip to true via env once this
# runs behind a real public domain + TLS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


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
