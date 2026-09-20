"""MCP misc tools: wardrobe summary aggregates."""

import pytest

from app.models.item import TaggingStatus

from .test_mcp_items import _make_item


@pytest.mark.asyncio
async def test_get_wardrobe_summary(call_tool, db_session, test_user):
    await _make_item(db_session, test_user, type="top")
    await _make_item(db_session, test_user, type="bottom", tagging_status=TaggingStatus.tagged)
    await _make_item(db_session, test_user, type="top", needs_wash=True)
    result = await call_tool("get_wardrobe_summary")
    assert result["total_items"] == 3
    assert result["items_pending_tagging"] == 2
    assert result["items_needing_wash"] == 1
    assert {t["type"] for t in result["types"]} == {"top", "bottom"}


@pytest.mark.asyncio
async def test_get_wardrobe_summary_empty(call_tool):
    result = await call_tool("get_wardrobe_summary")
    assert result["total_items"] == 0
    assert result["types"] == []
    assert result["colors"] == []
