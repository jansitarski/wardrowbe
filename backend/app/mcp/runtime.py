"""Per-tool-call context: the MCP-side equivalent of Depends(get_db) + get_current_user."""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypeVar

from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.user import User
from app.services.user_service import UserService

from .auth import current_external_id

ModelT = TypeVar("ModelT", bound=BaseModel)

# Test seam: conftest points this at the TEST_DATABASE_URL engine.
session_factory_override: async_sessionmaker[AsyncSession] | None = None


def _session_factory() -> async_sessionmaker[AsyncSession]:
    if session_factory_override is not None:
        return session_factory_override
    from app.database import async_session_maker

    return async_session_maker


@dataclass
class ToolContext:
    db: AsyncSession
    user: User


def validated(model_cls: type[ModelT], payload: dict) -> ModelT:
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc


def _detail_message(exc: HTTPException) -> str:
    if isinstance(exc.detail, dict):
        return str(exc.detail.get("message") or exc.detail)
    return str(exc.detail)


@asynccontextmanager
async def tool_context():
    external_id = current_external_id.get()
    if external_id is None:
        raise ToolError("Not authenticated")
    async with _session_factory()() as session:
        user = await UserService(session).get_by_external_id(external_id)
        if user is None or not user.is_active:
            raise ToolError("Unknown or inactive user")
        try:
            yield ToolContext(db=session, user=user)
        except ToolError:
            await session.rollback()
            raise
        except HTTPException as exc:
            await session.rollback()
            raise ToolError(_detail_message(exc)) from exc
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
