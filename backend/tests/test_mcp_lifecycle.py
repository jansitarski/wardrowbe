"""MCP lifecycle tools: archive/restore, wear/wash logging, wash queue."""

from datetime import date

import pytest

from .test_mcp_items import _make_item


@pytest.mark.asyncio
async def test_archive_and_restore(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user)
    archived = await call_tool("archive_item", {"item_id": str(item.id), "reason": "seasonal"})
    assert archived["status"] == "archived"
    restored = await call_tool("restore_item", {"item_id": str(item.id)})
    assert restored["status"] == "ready"


@pytest.mark.asyncio
async def test_log_wear_defaults_to_user_today(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool("log_wear", {"item_id": str(item.id)})
    assert result["wear_count"] == 1
    assert result["last_worn_at"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_log_wash_resets_wear_since_wash(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user, wears_since_wash=3, needs_wash=True)
    result = await call_tool("log_wash", {"item_id": str(item.id), "method": "machine"})
    assert result["wears_since_wash"] == 0
    assert result["needs_wash"] is False


@pytest.mark.asyncio
async def test_log_wash_rejects_clean_item(call_tool_raw, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool_raw("log_wash", {"item_id": str(item.id)})
    assert result["isError"] is True
    assert "already clean" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_items_to_wash(call_tool, db_session, test_user):
    await _make_item(db_session, test_user, needs_wash=True)
    await _make_item(db_session, test_user)
    result = await call_tool("get_items_to_wash")
    assert result["total"] == 1
    assert result["items"][0]["needs_wash"] is True
