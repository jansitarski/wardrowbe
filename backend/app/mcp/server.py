from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .auth import MCPAuthMiddleware
from .tools import authoring, items, lifecycle, misc, outfits, tagging

SERVER_NAME = "wardrowbe"
SERVER_INSTRUCTIONS = (
    "Built-in Wardrowbe MCP server. Manage the authenticated user's wardrobe: "
    "browse and tag items, log wear and wash, review and author outfits."
)

MCP_PATH = "/mcp"

_TOOL_MODULES = (misc, items, tagging, lifecycle, outfits, authoring)


class MCPDispatchMiddleware:
    """Routes /mcp traffic to the MCP app ahead of FastAPI routing.

    A Starlette mount answers the exact mount path with a 307 slash redirect,
    which strict MCP clients don't follow on POST — so /mcp is dispatched here,
    with and without a trailing slash, before the router sees it.
    """

    def __init__(self, app, mcp_app) -> None:
        self.app = app
        self.mcp_app = mcp_app

    async def __call__(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        if scope["type"] == "http" and (path == MCP_PATH or path.startswith(MCP_PATH + "/")):
            scope = dict(scope)
            scope["path"] = path[len(MCP_PATH) :] or "/"
            scope["root_path"] = scope.get("root_path", "") + MCP_PATH
            await self.mcp_app(scope, receive, send)
            return
        await self.app(scope, receive, send)


def build_mcp_server() -> MCPServer:
    mcp = MCPServer(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    for module in _TOOL_MODULES:
        module.register(mcp)
    return mcp


def build_mcp_asgi(server: MCPServer) -> MCPAuthMiddleware:
    # Host validation is left to the deployment's reverse proxy: the endpoint is
    # bearer-authenticated, so browser DNS-rebinding is not a usable vector, and
    # self-hosted instances serve under arbitrary hostnames.
    return MCPAuthMiddleware(
        server.streamable_http_app(
            streamable_http_path="/",
            json_response=True,
            stateless_http=True,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
    )
