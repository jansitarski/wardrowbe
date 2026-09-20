from datetime import date, datetime
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.api.outfits import (
    OutfitListResponse,
    fetch_wore_instead_items_map,
    outfit_to_response,
)
from app.models.outfit import FamilyOutfitRating, Outfit, OutfitItem, OutfitStatus
from app.services.outfit_service import OutfitListFilters, OutfitService
from app.services.suggestion_cache import clear_suggestions

from ..runtime import ToolContext, tool_context
from .items import clamp_page


async def load_owned_outfit(ctx: ToolContext, outfit_id: UUID) -> Outfit:
    query = (
        select(Outfit)
        .where(and_(Outfit.id == outfit_id, Outfit.user_id == ctx.user.id))
        .options(
            selectinload(Outfit.items).selectinload(OutfitItem.item),
            selectinload(Outfit.feedback),
            selectinload(Outfit.family_ratings).selectinload(FamilyOutfitRating.user),
        )
    )
    outfit = (await ctx.db.execute(query)).scalar_one_or_none()
    if not outfit:
        raise ToolError("Outfit not found")
    return outfit


async def outfit_dump(ctx: ToolContext, outfit: Outfit) -> dict:
    wore = await fetch_wore_instead_items_map(ctx.db, [outfit], user_id=ctx.user.id)
    return outfit_to_response(outfit, wore).model_dump(mode="json")


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    async def get_recent_outfits(
        page: int = 1,
        page_size: int = 10,
        status: str | None = None,
        occasion: str | None = None,
        source: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict:
        """List the user's outfits, newest first. Filter by status
        (pending/accepted/rejected/skipped/...), occasion, source, or date range."""
        page, page_size = clamp_page(page, page_size)
        async with tool_context() as ctx:
            filters = OutfitListFilters(
                user_id=ctx.user.id,
                status_filter=status,
                occasion=occasion,
                source=source,
                date_from=date_from,
                date_to=date_to,
            )
            outfits, total = await OutfitService(ctx.db).list_with_filters(filters, page, page_size)
            wore = await fetch_wore_instead_items_map(ctx.db, outfits, user_id=ctx.user.id)
            return OutfitListResponse(
                outfits=[outfit_to_response(o, wore) for o in outfits],
                total=total,
                page=page,
                page_size=page_size,
                has_more=(page * page_size) < total,
            ).model_dump(mode="json")

    @mcp.tool()
    async def get_outfit(outfit_id: UUID) -> dict:
        """Fetch one outfit with its items, attributes, feedback, and image URLs."""
        async with tool_context() as ctx:
            outfit = await load_owned_outfit(ctx, outfit_id)
            return await outfit_dump(ctx, outfit)

    @mcp.tool()
    async def accept_outfit(outfit_id: UUID) -> dict:
        """Accept a pending outfit suggestion."""
        async with tool_context() as ctx:
            outfit = await load_owned_outfit(ctx, outfit_id)
            outfit.status = OutfitStatus.accepted
            outfit.responded_at = datetime.utcnow()
            await ctx.db.flush()
            return await outfit_dump(ctx, outfit)

    @mcp.tool()
    async def reject_outfit(outfit_id: UUID) -> dict:
        """Reject (dismiss) an outfit suggestion; clears cached suggestions for its occasion."""
        async with tool_context() as ctx:
            outfit = await load_owned_outfit(ctx, outfit_id)
            outfit.status = OutfitStatus.rejected
            outfit.responded_at = datetime.utcnow()
            await ctx.db.flush()
            await clear_suggestions(ctx.user.id, outfit.occasion)
            return await outfit_dump(ctx, outfit)

    @mcp.tool()
    async def skip_outfit(outfit_id: UUID) -> dict:
        """Skip an outfit suggestion; clears cached suggestions for its occasion."""
        async with tool_context() as ctx:
            outfit = await load_owned_outfit(ctx, outfit_id)
            outfit.status = OutfitStatus.skipped
            await ctx.db.flush()
            await clear_suggestions(ctx.user.id, outfit.occasion)
            return await outfit_dump(ctx, outfit)
