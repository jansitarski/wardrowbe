"""MCP authoring tools: create_outfit_suggestion, create_item_pairing, create_outfit."""

import pytest

from app.config import Settings

from .test_mcp_items import _make_item


@pytest.mark.asyncio
async def test_create_outfit_suggestion(call_tool, db_session, test_user):
    top = await _make_item(db_session, test_user, type="top")
    bottom = await _make_item(db_session, test_user, type="bottom")
    result = await call_tool(
        "create_outfit_suggestion",
        {
            "items": [str(top.id), str(bottom.id)],
            "occasion": "casual",
            "reasoning": "Monochrome layers for a cool day",
            "season": "autumn",
            "formality": "casual",
            "palette": ["black", "grey"],
        },
    )
    assert result["source"] == "external"
    assert result["status"] == "pending"
    assert [i["position"] for i in result["items"]] == [0, 1]
    assert result["season"] == "autumn"


@pytest.mark.asyncio
async def test_create_outfit_suggestion_invalid_occasion(call_tool_raw, db_session, test_user):
    top = await _make_item(db_session, test_user)
    result = await call_tool_raw(
        "create_outfit_suggestion",
        {"items": [str(top.id)], "occasion": "space-opera"},
    )
    assert result["isError"] is True
    assert "Invalid occasion" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_create_outfit_suggestion_foreign_item(call_tool_raw, db_session, test_user):
    from .test_mcp_items import _make_other_user

    other = await _make_other_user(db_session)
    foreign = await _make_item(db_session, other)
    result = await call_tool_raw(
        "create_outfit_suggestion",
        {"items": [str(foreign.id)], "occasion": "casual"},
    )
    assert result["isError"] is True
    assert "do not belong" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_create_item_pairing_prepends_source(call_tool, db_session, test_user):
    source = await _make_item(db_session, test_user, type="top")
    partner = await _make_item(db_session, test_user, type="bottom")
    result = await call_tool(
        "create_item_pairing",
        {"source_item_id": str(source.id), "items": [str(partner.id)]},
    )
    assert result["occasion"] == "pairing"
    assert result["source_item"]["id"] == str(source.id)


@pytest.mark.asyncio
async def test_create_item_pairing_unknown_source(call_tool_raw, test_user):
    result = await call_tool_raw(
        "create_item_pairing",
        {
            "source_item_id": "00000000-0000-0000-0000-000000000000",
            "items": ["00000000-0000-0000-0000-000000000001"],
        },
    )
    assert result["isError"] is True


@pytest.mark.asyncio
async def test_create_outfit_studio(call_tool, db_session, test_user):
    top = await _make_item(db_session, test_user, type="top")
    bottom = await _make_item(db_session, test_user, type="bottom")
    result = await call_tool(
        "create_outfit",
        {
            "items": [str(top.id), str(bottom.id)],
            "occasion": "casual",
            "name": "Saturday",
        },
    )
    assert result["source"] == "manual"


@pytest.mark.asyncio
async def test_create_outfit_respects_studio_kill_switch(
    call_tool_raw, db_session, test_user, monkeypatch
):
    monkeypatch.setattr(
        "app.mcp.tools.authoring.get_settings",
        lambda: Settings(mcp_enabled=True, studio_disabled=True),
    )
    top = await _make_item(db_session, test_user)
    result = await call_tool_raw("create_outfit", {"items": [str(top.id)], "occasion": "casual"})
    assert result["isError"] is True
    assert "studio" in result["content"][0]["text"].lower()
