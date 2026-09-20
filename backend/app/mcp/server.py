from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .auth import MCPAuthMiddleware
from .tools import items, lifecycle, misc, outfits, tagging

SERVER_NAME = "wardrowbe"
SERVER_INSTRUCTIONS = (
    "Built-in Wardrowbe MCP server. Manage the authenticated user's wardrobe: "
    "browse and tag items, log wear and wash, review and author outfits."
)

_TOOL_MODULES = (misc, items, tagging, lifecycle, outfits)


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
