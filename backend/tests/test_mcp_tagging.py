"""MCP tagging tools: set_item_tags write-back stamping, retag_item, update_item."""

import pytest

from app.models.item import TaggingStatus

from .test_mcp_items import _make_item


@pytest.mark.asyncio
async def test_set_item_tags_stamps_manual(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool(
        "set_item_tags",
        {
            "item_id": str(item.id),
            "type": "top",
            "colors": ["black"],
            "primary_color": "black",
            "material": "cotton",
            "style": ["goth"],
        },
    )
    assert result["tagging_status"] == "tagged"
    assert result["tagged_by"] == "manual"
    assert result["tagged_at"] is not None
    assert result["tags"]["material"] == "cotton"
    assert result["primary_color"] == "black"


@pytest.mark.asyncio
async def test_set_item_tags_requires_content(call_tool_raw, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool_raw("set_item_tags", {"item_id": str(item.id)})
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_set_item_tags_rewrite_keeps_manual(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user)
    await call_tool("set_item_tags", {"item_id": str(item.id), "colors": ["black"]})
    second = await call_tool("set_item_tags", {"item_id": str(item.id), "colors": ["red"]})
    assert second["tagged_by"] == "manual"
    assert second["colors"] == ["red"]


@pytest.mark.asyncio
async def test_retag_item_resets_to_pending(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user, tagging_status=TaggingStatus.tagged)
    result = await call_tool("retag_item", {"item_id": str(item.id)})
    assert result["tagging_status"] == "pending"
    assert result["tagged_by"] is None
    assert result["tagged_at"] is None


@pytest.mark.asyncio
async def test_update_item_notes_does_not_stamp(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool("update_item", {"item_id": str(item.id), "notes": "hand-wash only"})
    assert result["notes"] == "hand-wash only"
    assert result["tagging_status"] == "pending"
    assert result["tagged_by"] is None


@pytest.mark.asyncio
async def test_update_item_requires_fields(call_tool_raw, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool_raw("update_item", {"item_id": str(item.id)})
    assert result["isError"] is True
