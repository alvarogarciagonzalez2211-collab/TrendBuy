import os
from typing import Any
from urllib.parse import urlencode

import httpx


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
# Same graceful-degradation pattern as TELEGRAM_BOT_TOKEN/SMTP_HOST elsewhere
# in this project: unset in .env just means the feature quietly doesn't
# appear (api/auth.py's /config endpoint tells the frontend whether to show
# the "Continuar con Google" button), it never breaks the rest of login.
GOOGLE_LOGIN_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
# The OIDC userinfo endpoint (not the legacy /oauth2/v3/userinfo one) - both
# work, this one is the one Google's own docs currently point to.
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"


def build_authorize_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        # Always show the account chooser instead of silently reusing
        # whichever Google account happens to be active in the browser -
        # matters on a shared/library computer, and avoids someone landing
        # in the wrong TrendBuy account without meaning to.
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
