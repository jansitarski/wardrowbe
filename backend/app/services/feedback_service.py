"""Outfit feedback application, shared by the REST route and the MCP tool."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import ClothingItem
from app.models.outfit import Outfit, OutfitStatus, UserFeedback
from app.models.user import User
from app.schemas.item import DEFAULT_WASH_INTERVALS
from app.services.studio_service import StudioService
from app.utils.timezone import get_user_today

if TYPE_CHECKING:
    from app.api.outfits import FeedbackRequest


async def apply_outfit_feedback(
    db: AsyncSession, user: User, outfit: Outfit, request: "FeedbackRequest"
) -> UserFeedback:
    """Upsert feedback on an owned outfit and apply its side effects.

    Raises ItemOwnershipError from the wore-instead path; the caller owns the
    transaction commit.
    """
    if outfit.feedback:
        feedback = outfit.feedback
    else:
        feedback = UserFeedback(outfit_id=outfit.id)
        outfit.feedback = feedback
        db.add(feedback)

    if request.accepted is not None:
        feedback.accepted = request.accepted
        outfit.status = OutfitStatus.accepted if request.accepted else OutfitStatus.rejected
        outfit.responded_at = datetime.utcnow()

    if request.rating is not None:
        feedback.rating = request.rating
    if request.comfort_rating is not None:
        feedback.comfort_rating = request.comfort_rating
    if request.style_rating is not None:
        feedback.style_rating = request.style_rating
    if request.comment is not None:
        feedback.comment = request.comment
    if request.worn and not feedback.worn_at:
        user_today = get_user_today(user)
        feedback.worn_at = user_today
        for outfit_item in outfit.items:
            item = outfit_item.item
            effective_interval = (
                item.wash_interval
                if item.wash_interval is not None
                else DEFAULT_WASH_INTERVALS.get(item.type, 3)
            )
            await db.execute(
                update(ClothingItem)
                .where(ClothingItem.id == item.id)
                .values(
                    wear_count=ClothingItem.wear_count + 1,
                    last_worn_at=user_today,
                    wears_since_wash=ClothingItem.wears_since_wash + 1,
                    needs_wash=ClothingItem.wears_since_wash + 1 >= effective_interval,
                )
            )
    if request.worn_with_modifications is not None:
        feedback.worn_with_modifications = request.worn_with_modifications
    if request.modification_notes is not None:
        feedback.modification_notes = request.modification_notes
    if request.actually_worn is not None:
        feedback.actually_worn = request.actually_worn
    if request.wore_instead_items is not None:
        feedback.wore_instead_items = [str(item_id) for item_id in request.wore_instead_items]
        if request.wore_instead_items:
            studio_service = StudioService(db)
            await studio_service.create_wore_instead(
                user=user,
                original_outfit_id=outfit.id,
                item_ids=list(request.wore_instead_items),
                rating=request.rating,
                comment=request.comment,
                scheduled_for=None,
            )

    return feedback
