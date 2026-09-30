"""MCP tagging tools: set_item_tags write-back stamping, update_item."""

import pytest

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


@pytest.mark.asyncio
async def test_set_item_tags_rejects_unsupported_type(call_tool_raw, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool_raw("set_item_tags", {"item_id": str(item.id), "type": "tights"})
    assert result["isError"] is True
    assert "tights" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_set_item_tags_schema_enumerates_types(mcp_call):
    resp = await mcp_call("tools/list")
    assert resp.status_code == 200, resp.text
    tools = {t["name"]: t for t in resp.json()["result"]["tools"]}
    type_schema = tools["set_item_tags"]["inputSchema"]["properties"]["type"]
    enum = next(opt["enum"] for opt in type_schema["anyOf"] if "enum" in opt)
    assert "jeans" in enum
    assert "tights" not in enum
