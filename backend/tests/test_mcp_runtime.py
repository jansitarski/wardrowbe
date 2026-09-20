"""tool_context(): user resolution from the auth contextvar, commit/rollback, error translation."""

import pytest
from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.mcp import runtime
from app.mcp.auth import current_external_id
from app.models.user import User


@pytest.fixture
def _factory(async_engine, monkeypatch):
    factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(runtime, "session_factory_override", factory)
    return factory


@pytest.mark.asyncio
async def test_unauthenticated_raises_tool_error(_factory):
    current_external_id.set(None)
    with pytest.raises(ToolError, match="Not authenticated"):
        async with runtime.tool_context():
            pass


@pytest.mark.asyncio
async def test_unknown_user_raises_tool_error(_factory):
    current_external_id.set("no-such-external-id")
    with pytest.raises(ToolError, match="Unknown or inactive user"):
        async with runtime.tool_context():
            pass


@pytest.mark.asyncio
async def test_resolves_user_and_commits(_factory, test_user):
    current_external_id.set(test_user.external_id)
    async with runtime.tool_context() as ctx:
        assert ctx.user.id == test_user.id
        ctx.user.display_name = "Changed by tool"
    async with _factory() as check:
        row = await check.execute(select(User).where(User.id == test_user.id))
        assert row.scalar_one().display_name == "Changed by tool"


@pytest.mark.asyncio
async def test_http_exception_translated_and_rolled_back(_factory, test_user):
    current_external_id.set(test_user.external_id)
    with pytest.raises(ToolError, match="Too many requests"):
        async with runtime.tool_context() as ctx:
            ctx.user.display_name = "Should not persist"
            raise HTTPException(
                status_code=429, detail="Too many requests. Please try again later."
            )
    async with _factory() as check:
        row = await check.execute(select(User).where(User.id == test_user.id))
        assert row.scalar_one().display_name == "Test User"


@pytest.mark.asyncio
async def test_dict_detail_message_extracted(_factory, test_user):
    current_external_id.set(test_user.external_id)
    with pytest.raises(ToolError, match="One or more items do not belong to you"):
        async with runtime.tool_context():
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "OUTFIT_ITEM_OWNERSHIP",
                    "message": "One or more items do not belong to you",
                },
            )
