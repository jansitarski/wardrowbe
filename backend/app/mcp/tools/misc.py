from mcp.server import MCPServer

from app.config import get_settings
from app.schemas.item import ItemFilter
from app.services.item_service import ItemService

from ..runtime import tool_context


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    async def session_info() -> dict:
        """Describe the authenticated user and the backend's AI capability flags."""
        async with tool_context() as ctx:
            settings = get_settings()
            return {
                "user": {
                    "id": str(ctx.user.id),
                    "email": ctx.user.email,
                    "display_name": ctx.user.display_name,
                    "timezone": ctx.user.timezone,
                    "locale": ctx.user.locale,
                },
                "ai": {
                    "vision": settings.effective_ai_vision_enabled,
                    "text": settings.effective_ai_text_enabled,
                },
            }

    @mcp.tool()
    async def get_wardrobe_summary() -> dict:
        """Aggregate wardrobe stats: totals, tagging queue size, wash queue size,
        type and color distributions."""
        async with tool_context() as ctx:
            service = ItemService(ctx.db)
            _, total = await service.get_list(ctx.user.id, ItemFilter(), page=1, page_size=1)
            _, pending = await service.get_list(
                ctx.user.id, ItemFilter(tagging_status="pending"), page=1, page_size=1
            )
            _, needs_wash = await service.get_list(
                ctx.user.id, ItemFilter(needs_wash=True), page=1, page_size=1
            )
            return {
                "total_items": total,
                "items_pending_tagging": pending,
                "items_needing_wash": needs_wash,
                "types": await service.get_item_types(ctx.user.id),
                "colors": await service.get_color_distribution(ctx.user.id),
            }
