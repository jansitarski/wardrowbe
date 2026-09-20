from mcp.server import MCPServer

from app.config import get_settings

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
