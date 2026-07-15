from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
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
)
from services.email_sender import send_magic_link_email


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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


@router.post("/request-login")
async def request_login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    usuario = await get_or_create_usuario(session, payload.email)
    login_token = await create_login_token(session, usuario)
    confirm_url = f"{FRONTEND_URL}/auth/confirm?token={login_token}"
    await send_magic_link_email(usuario.email, confirm_url)

    # Always the same response regardless of delivery outcome (e.g. SMTP not
    # configured yet) - an unauthenticated caller shouldn't be able to probe
    # infra state, and every email "registers" on first use here anyway so
    # there's no real enumeration secret to protect, just good habit.
    return {"message": "Si el correo es valido, te hemos enviado un enlace de acceso."}


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
    return {"id": usuario.id, "email": usuario.email}
