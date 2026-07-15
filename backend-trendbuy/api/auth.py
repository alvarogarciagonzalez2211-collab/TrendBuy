import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
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
    generate_token,
    get_or_create_usuario,
    get_usuario_from_session_token,
    verify_unsubscribe_token,
)
from services.email_sender import send_magic_link_email
from services.google_auth import GOOGLE_LOGIN_ENABLED, build_authorize_url, exchange_code, fetch_userinfo
from services.rate_limit import check_rate_limit


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GOOGLE_STATE_COOKIE_NAME = "trendbuy_google_state"
GOOGLE_STATE_TTL_SECONDS = 600

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
        raise HTTPException(status_code=400, detail="El enlace no es válido o ha caducado.")

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


@router.get("/config")
async def auth_config() -> dict[str, bool]:
    # Lets the frontend decide whether to render "Continuar con Google" at
    # all - hitting /google/login when it's unconfigured would otherwise
    # full-page-navigate an anonymous visitor to a raw 503 JSON error.
    return {"google_login_enabled": GOOGLE_LOGIN_ENABLED}


def _google_redirect_uri() -> str:
    # Must exactly match a redirect URI registered on the Google Cloud OAuth
    # client - see .env.example. Same self-configuring idea as api/main.py's
    # Telegram webhook URL: derived from FRONTEND_URL, not a separate env
    # var, and it always goes through the /backend proxy because the browser
    # can never reach the API container directly (see frontend-trendbuy's
    # src/app/backend/[...path]/route.ts).
    return f"{FRONTEND_URL}/backend/api/v1/auth/google/callback"


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    if not GOOGLE_LOGIN_ENABLED:
        raise HTTPException(status_code=503, detail="El inicio de sesión con Google no está configurado.")

    # Short-lived, httponly, samesite=lax (not "strict" - the callback below
    # arrives as a top-level cross-site GET *from* accounts.google.com, and
    # only "lax" cookies survive that) round-tripped through the browser
    # instead of a server-side store, purely to detect a forged callback
    # (CSRF), not to identify a specific pending login.
    state = generate_token()
    response = RedirectResponse(build_authorize_url(_google_redirect_uri(), state), status_code=307)
    response.set_cookie(
        key=GOOGLE_STATE_COOKIE_NAME,
        value=state,
        max_age=GOOGLE_STATE_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    def _failure(reason: str) -> RedirectResponse:
        logger.warning("Google login failed: %s", reason)
        failure_response = RedirectResponse(f"{FRONTEND_URL}/auth/confirm?google_error=1", status_code=307)
        failure_response.delete_cookie(GOOGLE_STATE_COOKIE_NAME, path="/")
        return failure_response

    expected_state = request.cookies.get(GOOGLE_STATE_COOKIE_NAME)
    if error:
        return _failure(f"google returned error={error}")
    if not code or not state or not expected_state or state != expected_state:
        return _failure("missing or mismatched state")

    try:
        tokens = await exchange_code(code, _google_redirect_uri())
        userinfo = await fetch_userinfo(tokens["access_token"])
    except Exception:
        logger.exception("Google token exchange or userinfo fetch failed")
        return _failure("token exchange failed")

    email = userinfo.get("email")
    if not email or not userinfo.get("email_verified"):
        return _failure("email missing or unverified")

    # Same identity model as magic-link login: one Usuario per email, found
    # or created here exactly like get_or_create_usuario in request_login
    # above - a person who previously logged in by email and later uses
    # "Continuar con Google" with that same address lands in the same
    # account, not a duplicate one.
    usuario = await get_or_create_usuario(session, email)
    usuario.ultimo_login = datetime.utcnow()
    session_token = await create_session(session, usuario)

    success_response = RedirectResponse(FRONTEND_URL, status_code=307)
    success_response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    success_response.delete_cookie(GOOGLE_STATE_COOKIE_NAME, path="/")
    return success_response


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
        return _unsubscribe_page("Este enlace no es válido.")

    result = await session.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = result.scalar_one_or_none()
    if usuario is None:
        return _unsubscribe_page("Este enlace no es válido.")

    usuario.notificaciones_activas = False
    await session.commit()

    return _unsubscribe_page("Se han desactivado tus notificaciones de bajada de precio. Tus favoritos siguen guardados.")
