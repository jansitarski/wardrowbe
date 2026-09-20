"""Bearer gate for the mounted MCP app.

Reuses the API's JWT validation; the authenticated external id travels to tool
handlers via a contextvar because MCP tools never see the HTTP request.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import HTTPException

from app.config import get_settings
from app.utils.auth import decode_token

current_external_id: ContextVar[str | None] = ContextVar("mcp_current_external_id", default=None)

_NOT_FOUND = b'{"detail":"Not Found"}'
_NOT_AUTHENTICATED = b'{"detail":"Not authenticated"}'

Scope = dict
Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]


class MCPAuthMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if not get_settings().mcp_enabled:
            await _respond(send, 404, _NOT_FOUND)
            return
        token = _bearer_token(scope)
        if token is None:
            await _respond(send, 401, _NOT_AUTHENTICATED, challenge=True)
            return
        try:
            payload = decode_token(token)
        except HTTPException:
            await _respond(send, 401, _NOT_AUTHENTICATED, challenge=True)
            return
        reset = current_external_id.set(payload.sub)
        try:
            await self.app(scope, receive, send)
        finally:
            current_external_id.reset(reset)


def _bearer_token(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            scheme, _, param = value.decode("latin-1").partition(" ")
            if scheme.lower() == "bearer" and param.strip():
                return param.strip()
            return None
    return None


async def _respond(send: Send, status: int, body: bytes, challenge: bool = False) -> None:
    headers = [(b"content-type", b"application/json")]
    if challenge:
        headers.append((b"www-authenticate", b"Bearer"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
