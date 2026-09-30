"""MCP outfit tools: list, get, respond_to_outfit, submit_outfit_feedback."""

import pytest

from app.services.external_outfit_service import ExternalOutfitService
from app.services.suggestion_cache import has_cached, push_suggestions

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
@pytest.mark.parametrize(
    ("response", "cache_kept"),
    [("accepted", True), ("rejected", False), ("skipped", False)],
)
async def test_respond_to_outfit_sets_status(
    call_tool, db_session, test_user, response, cache_kept
):
    outfit = await _make_outfit(db_session, test_user)
    await push_suggestions(test_user.id, outfit.occasion, [{"items": [1], "headline": "cached"}])
    result = await call_tool(
        "respond_to_outfit", {"outfit_id": str(outfit.id), "response": response}
    )
    assert result["status"] == response
    await db_session.refresh(outfit)
    assert outfit.responded_at is not None
    assert await has_cached(test_user.id, outfit.occasion) is cache_kept


@pytest.mark.asyncio
async def test_respond_to_outfit_rejects_unknown_response(call_tool_raw, test_user):
    result = await call_tool_raw(
        "respond_to_outfit",
        {"outfit_id": "00000000-0000-0000-0000-000000000000", "response": "maybe"},
    )
    assert result["isError"] is True
    assert "skipped" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_respond_to_outfit_not_found(call_tool_raw, test_user):
    result = await call_tool_raw(
        "respond_to_outfit",
        {"outfit_id": "00000000-0000-0000-0000-000000000000", "response": "accepted"},
    )
    assert result["isError"] is True
    assert "Outfit not found" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_outfit_not_found(call_tool_raw, test_user):
    result = await call_tool_raw(
        "get_outfit", {"outfit_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert result["isError"] is True
    assert "Outfit not found" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_submit_outfit_feedback(call_tool, db_session, test_user):
    outfit = await _make_outfit(db_session, test_user)
    result = await call_tool(
        "submit_outfit_feedback",
        {
            "outfit_id": str(outfit.id),
            "accepted": True,
            "rating": 5,
            "comment": "great",
        },
    )
    assert result["accepted"] is True
    assert result["rating"] == 5
    status = await call_tool("get_outfit", {"outfit_id": str(outfit.id)})
    assert status["status"] == "accepted"


@pytest.mark.asyncio
async def test_submit_outfit_feedback_worn_bumps_wear(call_tool, db_session, test_user):
    top = await _make_item(db_session, test_user, type="top")
    bottom = await _make_item(db_session, test_user, type="bottom")
    outfit = await _make_outfit(db_session, test_user, items=[top, bottom])
    await call_tool("submit_outfit_feedback", {"outfit_id": str(outfit.id), "worn": True})
    item = await call_tool("get_item", {"item_id": str(top.id)})
    assert item["wear_count"] == 1


@pytest.mark.asyncio
async def test_submit_outfit_feedback_invalid_rating(call_tool_raw, db_session, test_user):
    outfit = await _make_outfit(db_session, test_user)
    result = await call_tool_raw(
        "submit_outfit_feedback", {"outfit_id": str(outfit.id), "rating": 9}
    )
    assert result["isError"] is True
