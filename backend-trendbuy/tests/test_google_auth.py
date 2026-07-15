import importlib
from urllib.parse import parse_qs, urlparse

import services.google_auth as google_auth


ENV_KEYS = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]


def reload_with_env(monkeypatch, **env):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(google_auth)


def test_disabled_when_env_not_set(monkeypatch):
    mod = reload_with_env(monkeypatch)
    assert mod.GOOGLE_LOGIN_ENABLED is False


def test_disabled_when_only_client_id_set(monkeypatch):
    mod = reload_with_env(monkeypatch, GOOGLE_CLIENT_ID="abc")
    assert mod.GOOGLE_LOGIN_ENABLED is False


def test_enabled_when_both_set(monkeypatch):
    mod = reload_with_env(monkeypatch, GOOGLE_CLIENT_ID="abc", GOOGLE_CLIENT_SECRET="shh")
    assert mod.GOOGLE_LOGIN_ENABLED is True


def test_authorize_url_carries_redirect_uri_and_state(monkeypatch):
    mod = reload_with_env(monkeypatch, GOOGLE_CLIENT_ID="abc", GOOGLE_CLIENT_SECRET="shh")
    redirect_uri = "https://trendbuy.example/backend/api/v1/auth/google/callback"
    url = mod.build_authorize_url(redirect_uri, "the-state-value")

    parsed = urlparse(url)
    assert parsed.netloc == "accounts.google.com"
    params = parse_qs(parsed.query)
    assert params["client_id"] == ["abc"]
    assert params["redirect_uri"] == [redirect_uri]
    assert params["state"] == ["the-state-value"]
    assert params["response_type"] == ["code"]
    assert "email" in params["scope"][0]
