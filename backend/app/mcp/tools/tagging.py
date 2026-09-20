from typing import Any
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app.schemas.item import ItemUpdate
from app.services.item_service import ItemService, stamp_manual_tag_writeback

from ..runtime import tool_context, validated
from .items import get_owned_item, item_dump


async def _apply_update(item_id: UUID, payload: dict[str, Any]) -> dict:
    update = validated(ItemUpdate, payload)
    update_data = update.model_dump(exclude_unset=True)
    async with tool_context() as ctx:
        item = await get_owned_item(ctx, item_id)
        stamp_manual_tag_writeback(item, update_data)
        item = await ItemService(ctx.db).update(item, update)
        return item_dump(item)


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    async def set_item_tags(
        item_id: UUID,
        type: str | None = None,
        subtype: str | None = None,
        colors: list[str] | None = None,
        primary_color: str | None = None,
        pattern: str | None = None,
        material: str | None = None,
        style: list[str] | None = None,
        season: list[str] | None = None,
        formality: str | None = None,
        fit: str | None = None,
    ) -> dict:
        """Write tags back to an item (external tagging). The tags payload is
        replaced; non-empty content marks the item tagged (tagged_by=manual)."""
        tag_fields = {
            "colors": colors,
            "primary_color": primary_color,
            "pattern": pattern,
            "material": material,
            "style": style,
            "season": season,
            "formality": formality,
            "fit": fit,
        }
        payload: dict[str, Any] = {
            k: v
            for k, v in {
                "type": type,
                "subtype": subtype,
                "colors": colors,
                "primary_color": primary_color,
            }.items()
            if v is not None
        }
        if any(v is not None for v in tag_fields.values()):
            payload["tags"] = {k: v for k, v in tag_fields.items() if v is not None}
        if not payload:
            raise ToolError("Provide at least one tag field")
        return await _apply_update(item_id, payload)

    @mcp.tool()
    async def retag_item(item_id: UUID) -> dict:
        """Send an item back to the pending tagging queue (clears tagged_by/tagged_at)."""
        async with tool_context() as ctx:
            item = await get_owned_item(ctx, item_id)
            item = await ItemService(ctx.db).mark_pending(item)
            return item_dump(item)

    @mcp.tool()
    async def update_item(
        item_id: UUID,
        name: str | None = None,
        brand: str | None = None,
        notes: str | None = None,
        favorite: bool | None = None,
        wash_interval: int | None = None,
    ) -> dict:
        """Update non-tag item fields (name, brand, notes, favorite, wash_interval)."""
        payload = {
            k: v
            for k, v in {
                "name": name,
                "brand": brand,
                "notes": notes,
                "favorite": favorite,
                "wash_interval": wash_interval,
            }.items()
            if v is not None
        }
        if not payload:
            raise ToolError("Provide at least one field to update")
        return await _apply_update(item_id, payload)
