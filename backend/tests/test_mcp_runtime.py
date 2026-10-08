from contextlib import contextmanager

import pytest
from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import select

from app.mcp import runtime
from app.mcp.auth import current_external_id
from app.models.user import User


@pytest.fixture(autouse=True)
def _session_maker(session_maker, monkeypatch):
    monkeypatch.setattr(runtime, "async_session_maker", session_maker)


@contextmanager
def _as_user(external_id: str | None):
    token = current_external_id.set(external_id)
    try:
        yield
    finally:
        current_external_id.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("external_id", "message"),
    [(None, "Not authenticated"), ("no-such-external-id", "Unknown or inactive user")],
)
async def test_requires_a_known_user(external_id, message):
    with _as_user(external_id):
        with pytest.raises(ToolError, match=message):
            async with runtime.tool_context():
                pass


@pytest.mark.asyncio
async def test_resolves_user_and_commits(session_maker, test_user):
    with _as_user(test_user.external_id):
        async with runtime.tool_context() as ctx:
            assert ctx.user.id == test_user.id
            ctx.user.display_name = "Changed by tool"
    async with session_maker() as check:
        row = await check.execute(select(User).where(User.id == test_user.id))
        assert row.scalar_one().display_name == "Changed by tool"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "detail", ["Item not found", {"error_code": "NOT_FOUND", "message": "Item not found"}]
)
async def test_http_exception_becomes_tool_error_and_rolls_back(session_maker, test_user, detail):
    with _as_user(test_user.external_id):
        with pytest.raises(ToolError, match="Item not found"):
            async with runtime.tool_context() as ctx:
                ctx.user.display_name = "Should not persist"
                raise HTTPException(status_code=404, detail=detail)
    async with session_maker() as check:
        row = await check.execute(select(User).where(User.id == test_user.id))
        assert row.scalar_one().display_name == "Test User"
