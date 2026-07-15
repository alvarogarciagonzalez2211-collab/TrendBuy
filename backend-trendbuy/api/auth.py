from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Usuario, get_session
from services.auth import (
    COOKIE_SECURE,
    FRONTEND_URL,
    SESSION_COOKIE_NAME,
    SESSION_TTL_DAYS,
    consume_login_token,
    create_login_token,
    create_session,
    delete_session,
    get_or_create_usuario,
    get_usuario_from_session_token,
    verify_unsubscribe_token,
)
from services.email_sender import send_magic_link_email
from services.rate_limit import check_rate_limit


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Keyed by email (the actual abuse surface - it's real mail through a real
# inbox, see services/email_sender.py) and, best-effort, by IP. Behind the
# Next.js proxy every request currently arrives from the same internal
# address, so the IP limit today acts as one shared site-wide budget rather
# than a strict per-visitor one - still useful as a blunt cap, but the email
# limit below is the one that actually matters.
LOGIN_RATE_LIMIT_PER_EMAIL_PER_HOUR = 5
LOGIN_RATE_LIMIT_PER_IP_PER_HOUR = 20


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> Usuario:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")

    usuario = await get_usuario_from_session_token(session, token)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Sesion invalida o caducada")

    return usuario


class LoginRequest(BaseModel):
    email: EmailStr


class ConfirmRequest(BaseModel):
    token: str


GENERIC_LOGIN_RESPONSE = {"message": "Si el correo es valido, te hemos enviado un enlace de acceso."}


@router.post("/request-login")
async def request_login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    email_norm = payload.email.strip().lower()
    client_ip = request.client.host if request.client else "unknown"

    email_allowed = await check_rate_limit(
        f"ratelimit:login:email:{email_norm}", LOGIN_RATE_LIMIT_PER_EMAIL_PER_HOUR, 3600
    )
    ip_allowed = await check_rate_limit(f"ratelimit:login:ip:{client_ip}", LOGIN_RATE_LIMIT_PER_IP_PER_HOUR, 3600)

    if not email_allowed or not ip_allowed:
        # Same generic response as success - doesn't reveal to a script that
        # it just tripped a limit, only that no more mail is going out for
        # a while.
        return GENERIC_LOGIN_RESPONSE

    usuario = await get_or_create_usuario(session, payload.email)
    login_token = await create_login_token(session, usuario)
    confirm_url = f"{FRONTEND_URL}/auth/confirm?token={login_token}"
    await send_magic_link_email(usuario.email, confirm_url)

    # Always the same response regardless of delivery outcome (e.g. SMTP not
    # configured yet) - an unauthenticated caller shouldn't be able to probe
    # infra state, and every email "registers" on first use here anyway so
    # there's no real enumeration secret to protect, just good habit.
    return GENERIC_LOGIN_RESPONSE


@router.post("/confirm")
async def confirm_login(
    payload: ConfirmRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    usuario = await consume_login_token(session, payload.token)
    if usuario is None:
        raise HTTPException(status_code=400, detail="El enlace no es valido o ha caducado.")

    session_token = await create_session(session, usuario)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    return {"id": usuario.id, "email": usuario.email}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        await delete_session(session, token)

    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(usuario: Usuario = Depends(get_current_user)) -> dict[str, Any]:
    return {"id": usuario.id, "email": usuario.email, "telegram_linked": usuario.telegram_chat_id is not None}


def _unsubscribe_page(message: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>TrendBuy</title></head>
<body style="font-family: sans-serif; max-width: 480px; margin: 4rem auto; text-align: center; color: #18181b;">
<h1 style="font-size: 1.25rem;">TrendBuy</h1>
<p>{message}</p>
</body></html>"""
    )


@router.get("/unsubscribe")
async def unsubscribe(
    token: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    # Plain GET, no session/cookie required: this link is opened straight
    # from an email client, often on a different device than the one that's
    # logged in. One-click unsubscribe is the standard UX here, and it's
    # idempotent/low-stakes enough not to need the login flow's replay
    # protection - see services/auth.py::verify_unsubscribe_token.
    user_id = verify_unsubscribe_token(token)
    if user_id is None:
        return _unsubscribe_page("Este enlace no es valido.")

    result = await session.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = result.scalar_one_or_none()
    if usuario is None:
        return _unsubscribe_page("Este enlace no es valido.")

    usuario.notificaciones_activas = False
    await session.commit()

    return _unsubscribe_page("Se han desactivado tus notificaciones de bajada de precio. Tus favoritos siguen guardados.")
