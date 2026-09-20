from datetime import date
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app.schemas.item import ArchiveRequest, ItemFilter
from app.services.item_service import ItemService
from app.utils.timezone import get_user_today

from ..runtime import tool_context, validated
from .items import clamp_page, get_owned_item, item_dump, item_list_dump


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    async def archive_item(item_id: UUID, reason: str | None = None) -> dict:
        """Archive an item (hidden from suggestions; reversible with restore_item)."""
        request = validated(ArchiveRequest, {"reason": reason})
        async with tool_context() as ctx:
            item = await get_owned_item(ctx, item_id)
            item = await ItemService(ctx.db).archive(item, request.reason)
            return item_dump(item)

    @mcp.tool()
    async def restore_item(item_id: UUID) -> dict:
        """Restore an archived item."""
        async with tool_context() as ctx:
            item = await get_owned_item(ctx, item_id)
            item = await ItemService(ctx.db).restore(item)
            return item_dump(item)

    @mcp.tool()
    async def log_wear(
        item_id: UUID,
        worn_at: date | None = None,
        occasion: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Log that an item was worn (defaults to the user's current date)."""
        async with tool_context() as ctx:
            item = await get_owned_item(ctx, item_id)
            await ItemService(ctx.db).log_wear(
                item=item,
                worn_at=worn_at or get_user_today(ctx.user),
                occasion=occasion,
                notes=notes,
            )
            await ctx.db.refresh(item)
            return item_dump(item)

    @mcp.tool()
    async def log_wash(
        item_id: UUID,
        washed_at: date | None = None,
        method: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Log that an item was washed (defaults to the user's current date)."""
        async with tool_context() as ctx:
            item = await get_owned_item(ctx, item_id)
            if item.wears_since_wash == 0:
                raise ToolError("Item is already clean (0 wears since last wash)")
            await ItemService(ctx.db).log_wash(
                item=item,
                washed_at=washed_at or get_user_today(ctx.user),
                method=method,
                notes=notes,
            )
            await ctx.db.refresh(item)
            return item_dump(item)

    @mcp.tool()
    async def get_items_to_wash(page: int = 1, page_size: int = 20) -> dict:
        """List items whose wear count has reached their wash interval."""
        page, page_size = clamp_page(page, page_size)
        async with tool_context() as ctx:
            items, total = await ItemService(ctx.db).get_list(
                ctx.user.id, ItemFilter(needs_wash=True), page=page, page_size=page_size
            )
            return item_list_dump(items, total, page, page_size)
