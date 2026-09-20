"""MCPAuthMiddleware: MCP_ENABLED gate, bearer JWT validation, contextvar propagation."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import create_access_token
from app.config import Settings
from app.mcp.auth import MCPAuthMiddleware, current_external_id


async def _echo_app(scope, receive, send):
    body = (current_external_id.get() or "").encode()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": body})


def _client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=MCPAuthMiddleware(_echo_app)),
        base_url="http://test",
    )


@pytest.fixture(autouse=True)
def _mcp_enabled(monkeypatch):
    monkeypatch.setattr("app.mcp.auth.get_settings", lambda: Settings(mcp_enabled=True))


@pytest.mark.asyncio
async def test_disabled_flag_returns_404(monkeypatch):
    monkeypatch.setattr("app.mcp.auth.get_settings", lambda: Settings(mcp_enabled=False))
    async with _client() as c:
        resp = await c.post("/")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_missing_token_returns_401_with_www_authenticate():
    async with _client() as c:
        resp = await c.post("/")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_malformed_scheme_returns_401():
    async with _client() as c:
        resp = await c.post("/", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401():
    async with _client() as c:
        resp = await c.post("/", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_passes_and_sets_contextvar():
    token = create_access_token("ext-user-42")
    async with _client() as c:
        resp = await c.post("/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.text == "ext-user-42"


@pytest.mark.asyncio
async def test_contextvar_reset_after_request():
    token = create_access_token("ext-user-42")
    async with _client() as c:
        await c.post("/", headers={"Authorization": f"Bearer {token}"})
    assert current_external_id.get() is None
