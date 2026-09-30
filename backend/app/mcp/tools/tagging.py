from typing import Any, Literal
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app.schemas.item import ItemUpdate
from app.services.ai_service import VALID_TYPES
from app.services.item_service import ItemService, stamp_manual_tag_writeback

from ..runtime import tool_context, validated
from .items import get_owned_item, item_dump

# Derived from the same vocabulary the vision prompt uses, so the MCP schema
# lists every accepted type and the SDK rejects anything else before the handler.
ItemType = Literal[tuple(sorted(VALID_TYPES))]  # type: ignore[valid-type]


async def _apply_update(item_id: UUID, payload: dict[str, Any]) -> dict:
    update = validated(ItemUpdate, payload)
    update_data = update.model_dump(exclude_unset=True)
    async with tool_context() as ctx:
        item = await get_owned_item(ctx, item_id)
        stamp_manual_tag_writeback(item, update_data)
        item = await ItemService(ctx.db).update(item, update)
        return item_dump(item)


def _present(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    async def set_item_tags(
        item_id: UUID,
        type: ItemType | None = None,
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
        replaced as a whole; non-empty content marks the item tagged (tagged_by=manual).
        type is limited to the vision vocabulary listed in the schema; the web UI
        offers one type outside it (suit) that must be set there."""
        tags = _present(
            colors=colors,
            primary_color=primary_color,
            pattern=pattern,
            material=material,
            style=style,
            season=season,
            formality=formality,
            fit=fit,
        )
        payload = _present(type=type, subtype=subtype)
        if tags:
            payload["tags"] = tags
        if not payload:
            raise ToolError("Provide at least one tag field")
        return await _apply_update(item_id, payload)

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
        payload = _present(
            name=name, brand=brand, notes=notes, favorite=favorite, wash_interval=wash_interval
        )
        if not payload:
            raise ToolError("Provide at least one field to update")
        return await _apply_update(item_id, payload)
