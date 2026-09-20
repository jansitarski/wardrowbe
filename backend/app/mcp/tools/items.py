import base64
import mimetypes
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ImageContent

from app.models.item import ClothingItem
from app.schemas.item import ItemFilter, ItemListResponse, ItemResponse
from app.services.image_service import ImageService
from app.services.item_service import ItemService

from ..runtime import ToolContext, tool_context

MAX_PAGE_SIZE = 100
IMAGE_VARIANTS = ("thumbnail", "medium", "full")


def clamp_page(page: int, page_size: int) -> tuple[int, int]:
    return max(page, 1), min(max(page_size, 1), MAX_PAGE_SIZE)


async def get_owned_item(ctx: ToolContext, item_id: UUID) -> ClothingItem:
    item = await ItemService(ctx.db).get_by_id(item_id, ctx.user.id)
    if not item:
        raise ToolError("Item not found")
    return item


def item_dump(item: ClothingItem) -> dict:
    return ItemResponse.model_validate(item).model_dump(mode="json")


def item_list_dump(items: list[ClothingItem], total: int, page: int, page_size: int) -> dict:
    return ItemListResponse(
        items=[ItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    ).model_dump(mode="json")


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    async def list_items(
        page: int = 1,
        page_size: int = 20,
        type: str | None = None,
        status: str | None = None,
        tagging_status: str | None = None,
        favorite: bool | None = None,
        needs_wash: bool | None = None,
        is_archived: bool = False,
        search: str | None = None,
    ) -> dict:
        """List the user's clothing items with filters. tagging_status='pending'
        is the external-tagging work queue."""
        page, page_size = clamp_page(page, page_size)
        filters = ItemFilter(
            type=type,
            status=status,
            tagging_status=tagging_status,
            favorite=favorite,
            needs_wash=needs_wash,
            is_archived=is_archived,
            search=search,
        )
        async with tool_context() as ctx:
            items, total = await ItemService(ctx.db).get_list(
                ctx.user.id, filters, page=page, page_size=page_size
            )
            return item_list_dump(items, total, page, page_size)

    @mcp.tool()
    async def get_item(item_id: UUID) -> dict:
        """Fetch one clothing item: tags, lifecycle state, wear/wash counters, image URLs."""
        async with tool_context() as ctx:
            return item_dump(await get_owned_item(ctx, item_id))

    @mcp.tool()
    async def get_item_image(item_id: UUID, variant: str = "medium") -> ImageContent:
        """Return the item's photo. variant: thumbnail | medium | full."""
        if variant not in IMAGE_VARIANTS:
            raise ToolError(f"variant must be one of: {', '.join(IMAGE_VARIANTS)}")
        async with tool_context() as ctx:
            item = await get_owned_item(ctx, item_id)
            relative = {
                "thumbnail": item.thumbnail_path,
                "medium": item.medium_path,
                "full": item.image_path,
            }[variant] or item.image_path
            path = ImageService().get_image_path(relative)
            if not path.is_file():
                raise ToolError("Image file missing from storage")
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return ImageContent(type="image", data=data, mimeType=mime)
