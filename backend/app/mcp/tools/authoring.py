import logging
from datetime import date
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app.api.outfits import (
    StudioCreateRequest,
    SuggestionCreateRequest,
    outfit_to_response,
)
from app.api.pairings import PairingCreateRequest, pairing_to_response
from app.config import get_settings
from app.services.external_outfit_service import ExternalOutfitService
from app.services.learning_service import LearningService
from app.services.pairing_service import PairingService
from app.services.studio_service import ItemOwnershipError, StudioService, load_full_outfit
from app.services.suggestion_cache import clear_suggestions
from app.utils.rate_limit import rate_limit_by_user

from ..runtime import tool_context, validated

logger = logging.getLogger(__name__)


def register(mcp: MCPServer) -> None:
    @mcp.tool()
    async def create_outfit_suggestion(
        items: list[UUID],
        occasion: str,
        name: str | None = None,
        scheduled_for: date | None = None,
        reasoning: str | None = None,
        style_notes: str | None = None,
        season: str | None = None,
        formality: str | None = None,
        palette: list[str] | None = None,
        notes: str | None = None,
    ) -> dict:
        """Author an outfit suggestion (source=external, status=pending).
        Item order defines display positions."""
        request = validated(
            SuggestionCreateRequest,
            {
                "items": items,
                "occasion": occasion,
                "name": name,
                "scheduled_for": scheduled_for,
                "reasoning": reasoning,
                "style_notes": style_notes,
                "season": season,
                "formality": formality,
                "palette": palette,
                "notes": notes,
            },
        )
        async with tool_context() as ctx:
            await rate_limit_by_user(
                str(ctx.user.id), "external_suggestion", max_requests=20, window_seconds=60
            )
            service = ExternalOutfitService(ctx.db)
            try:
                outfit = await service.create_suggestion(
                    user=ctx.user,
                    item_ids=request.items,
                    occasion=request.occasion,
                    name=request.name,
                    scheduled_for=request.scheduled_for,
                    reasoning=request.reasoning,
                    style_notes=request.style_notes,
                    season=request.season,
                    formality=request.formality,
                    palette=request.palette,
                    notes=request.notes,
                )
            except ItemOwnershipError:
                raise ToolError("One or more items do not belong to you") from None
            await ctx.db.flush()
            await clear_suggestions(ctx.user.id, request.occasion)
            full = await service.get_full_outfit(outfit.id)
            return outfit_to_response(full).model_dump(mode="json")

    @mcp.tool()
    async def create_item_pairing(
        source_item_id: UUID,
        items: list[UUID],
        scheduled_for: date | None = None,
        reasoning: str | None = None,
        style_notes: str | None = None,
        season: str | None = None,
        formality: str | None = None,
        palette: list[str] | None = None,
        notes: str | None = None,
    ) -> dict:
        """Author a pairing for a source item (partners in items). The source
        item is prepended automatically when absent from items."""
        request = validated(
            PairingCreateRequest,
            {
                "items": items,
                "scheduled_for": scheduled_for,
                "reasoning": reasoning,
                "style_notes": style_notes,
                "season": season,
                "formality": formality,
                "palette": palette,
                "notes": notes,
            },
        )
        async with tool_context() as ctx:
            await rate_limit_by_user(
                str(ctx.user.id), "external_pairing", max_requests=20, window_seconds=60
            )
            source = await PairingService(ctx.db).get_source_item(ctx.user.id, source_item_id)
            if not source:
                raise ToolError("Source item not found or not available")
            service = ExternalOutfitService(ctx.db)
            try:
                outfit = await service.create_pairing(
                    user=ctx.user,
                    source_item_id=source_item_id,
                    item_ids=request.items,
                    scheduled_for=request.scheduled_for,
                    reasoning=request.reasoning,
                    style_notes=request.style_notes,
                    season=request.season,
                    formality=request.formality,
                    palette=request.palette,
                    notes=request.notes,
                )
            except ItemOwnershipError:
                raise ToolError("One or more items do not belong to you") from None
            except ValueError as exc:
                raise ToolError(str(exc)) from None
            await ctx.db.flush()
            full = await service.get_full_outfit(outfit.id)
            return pairing_to_response(full).model_dump(mode="json")

    @mcp.tool()
    async def create_outfit(
        items: list[UUID],
        occasion: str,
        name: str | None = None,
        scheduled_for: date | None = None,
        mark_worn: bool = False,
        season: str | None = None,
        formality: str | None = None,
        palette: list[str] | None = None,
        notes: str | None = None,
    ) -> dict:
        """Compose a manual outfit in the studio (source=manual, counts as accepted)."""
        if get_settings().studio_disabled:
            raise ToolError("Outfit studio is disabled on this server")
        request = validated(
            StudioCreateRequest,
            {
                "items": items,
                "occasion": occasion,
                "name": name,
                "scheduled_for": scheduled_for,
                "mark_worn": mark_worn,
                "season": season,
                "formality": formality,
                "palette": palette,
                "notes": notes,
            },
        )
        async with tool_context() as ctx:
            await rate_limit_by_user(
                str(ctx.user.id), "studio_create", max_requests=20, window_seconds=60
            )
            try:
                outfit = await StudioService(ctx.db).create_from_scratch(
                    user=ctx.user,
                    item_ids=request.items,
                    occasion=request.occasion,
                    name=request.name,
                    scheduled_for=request.scheduled_for,
                    mark_worn=request.mark_worn,
                    source_item_id=request.source_item_id,
                    season=request.season,
                    formality=request.formality,
                    palette=request.palette,
                    notes=request.notes,
                )
            except ItemOwnershipError:
                raise ToolError("One or more items do not belong to you") from None
            await ctx.db.flush()
            try:
                await LearningService(ctx.db).process_feedback(outfit.id, ctx.user.id)
            except Exception:
                logger.exception("learning process_feedback failed for outfit %s", outfit.id)
            await clear_suggestions(ctx.user.id, outfit.occasion)
            full = await load_full_outfit(ctx.db, outfit.id)
            return outfit_to_response(full).model_dump(mode="json")
