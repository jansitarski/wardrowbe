"""MCP item read tools: list_items filtering, get_item, get_item_image, ownership."""

from pathlib import Path
from uuid import uuid4

import pytest

from app.config import get_settings
from app.models.item import ClothingItem, ItemStatus, TaggingStatus
from app.models.user import User


async def _make_item(db_session, user, **overrides) -> ClothingItem:
    defaults = {
        "user_id": user.id,
        "type": "top",
        "name": f"Item {uuid4().hex[:6]}",
        "image_path": f"{user.id}/{uuid4().hex}.webp",
        "status": ItemStatus.ready,
        "tagging_status": TaggingStatus.pending,
    }
    defaults.update(overrides)
    item = ClothingItem(**defaults)
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


async def _make_other_user(db_session) -> User:
    other = User(
        id=uuid4(),
        external_id=f"other-{uuid4()}",
        email=f"o-{uuid4()}@example.com",
        display_name="Other",
        timezone="UTC",
        is_active=True,
        onboarding_completed=False,
    )
    db_session.add(other)
    await db_session.commit()
    return other


@pytest.mark.asyncio
async def test_list_items_empty(call_tool):
    result = await call_tool("list_items")
    assert result["total"] == 0
    assert result["items"] == []


@pytest.mark.asyncio
async def test_list_items_tagging_status_filter(call_tool, db_session, test_user):
    await _make_item(db_session, test_user)
    await _make_item(db_session, test_user, tagging_status=TaggingStatus.tagged)
    pending = await call_tool("list_items", {"tagging_status": "pending"})
    assert pending["total"] == 1
    assert pending["items"][0]["tagging_status"] == "pending"


@pytest.mark.asyncio
async def test_list_items_clamps_page_size(call_tool, db_session, test_user):
    await _make_item(db_session, test_user)
    result = await call_tool("list_items", {"page_size": 5000})
    assert result["page_size"] == 100


@pytest.mark.asyncio
async def test_get_item_returns_signed_urls(call_tool, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool("get_item", {"item_id": str(item.id)})
    assert result["id"] == str(item.id)
    assert result["image_url"].startswith("/api/v1/images/")


@pytest.mark.asyncio
async def test_get_item_foreign_item_is_tool_error(call_tool_raw, db_session, test_user):
    other = await _make_other_user(db_session)
    foreign = await _make_item(db_session, other)
    result = await call_tool_raw("get_item", {"item_id": str(foreign.id)})
    assert result["isError"] is True
    assert "Item not found" in result["content"][0]["text"]


@pytest.mark.asyncio
async def test_get_item_image_reads_storage(call_tool_raw, db_session, test_user):
    item = await _make_item(db_session, test_user)
    file_path = Path(get_settings().storage_path) / item.image_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    result = await call_tool_raw("get_item_image", {"item_id": str(item.id), "variant": "full"})
    assert not result.get("isError"), result
    content = result["content"][0]
    assert content["type"] == "image"
    assert content["data"]


@pytest.mark.asyncio
async def test_get_item_image_invalid_variant(call_tool_raw, db_session, test_user):
    item = await _make_item(db_session, test_user)
    result = await call_tool_raw("get_item_image", {"item_id": str(item.id), "variant": "huge"})
    assert result["isError"] is True
    assert "variant" in result["content"][0]["text"]
