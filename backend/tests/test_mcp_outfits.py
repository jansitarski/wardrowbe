"""MCP outfit tools: recent list, get, accept/reject/skip."""

import pytest

from app.services.external_outfit_service import ExternalOutfitService

from .test_mcp_items import _make_item


async def _make_outfit(db_session, user, items=None, occasion="casual"):
    if items is None:
        items = [
            await _make_item(db_session, user, type="top"),
            await _make_item(db_session, user, type="bottom"),
        ]
    outfit = await ExternalOutfitService(db_session).create_suggestion(
        user=user, item_ids=[i.id for i in items], occasion=occasion
    )
    await db_session.commit()
    return outfit


@pytest.mark.asyncio
async def test_get_recent_outfits(call_tool, db_session, test_user):
    await _make_outfit(db_session, test_user)
    result = await call_tool("get_recent_outfits", {"page_size": 5})
    assert result["total"] == 1
    assert result["outfits"][0]["source"] == "external"


@pytest.mark.asyncio
async def test_get_recent_outfits_status_filter(call_tool, db_session, test_user):
    await _make_outfit(db_session, test_user)
    result = await call_tool("get_recent_outfits", {"status": "accepted"})
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_get_outfit(call_tool, db_session, test_user):
    outfit = await _make_outfit(db_session, test_user)
    result = await call_tool("get_outfit", {"outfit_id": str(outfit.id)})
    assert result["id"] == str(outfit.id)
    assert len(result["items"]) == 2


@pytest.mark.asyncio
async def test_accept_outfit(call_tool, db_session, test_user):
    outfit = await _make_outfit(db_session, test_user)
    result = await call_tool("accept_outfit", {"outfit_id": str(outfit.id)})
    assert result["status"] == "accepted"


@pytest.mark.asyncio
async def test_reject_outfit(call_tool, db_session, test_user):
    outfit = await _make_outfit(db_session, test_user)
    result = await call_tool("reject_outfit", {"outfit_id": str(outfit.id)})
    assert result["status"] == "rejected"


@pytest.mark.asyncio
async def test_skip_outfit(call_tool, db_session, test_user):
    outfit = await _make_outfit(db_session, test_user)
    result = await call_tool("skip_outfit", {"outfit_id": str(outfit.id)})
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_get_outfit_not_found(call_tool_raw, test_user):
    result = await call_tool_raw(
        "get_outfit", {"outfit_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert result["isError"] is True
    assert "Outfit not found" in result["content"][0]["text"]
