"""MCP server assembly: flag gating through the main app, tools/list, session_info."""

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
async def test_mcp_mount_404_when_disabled(client, auth_headers, path):
    resp = await client.post(path, json={}, headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
async def test_mcp_mount_401_when_enabled_without_valid_token(client, monkeypatch, path):
    from app.config import Settings

    monkeypatch.setattr("app.mcp.auth.get_settings", lambda: Settings(mcp_enabled=True))
    resp = await client.post(path, json={})
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_tools_list_requires_auth(mcp_call):
    resp = await mcp_call("tools/list", headers={"Authorization": "Bearer bad"})
    assert resp.status_code == 401


EXPECTED_TOOLS = {
    "session_info",
    "get_wardrobe_summary",
    "list_items",
    "get_item",
    "get_item_image",
    "set_item_tags",
    "update_item",
    "archive_item",
    "restore_item",
    "log_wear",
    "log_wash",
    "list_outfits",
    "get_outfit",
    "respond_to_outfit",
    "submit_outfit_feedback",
    "create_outfit_suggestion",
    "create_item_pairing",
    "create_outfit",
}


@pytest.mark.asyncio
async def test_tools_list_names(mcp_call):
    resp = await mcp_call("tools/list")
    assert resp.status_code == 200, resp.text
    names = {t["name"] for t in resp.json()["result"]["tools"]}
    assert names == EXPECTED_TOOLS
    assert READ_ONLY_TOOLS <= EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_session_info(call_tool, test_user):
    result = await call_tool("session_info")
    assert result["user"]["email"] == test_user.email
    assert result["user"]["timezone"] == "UTC"
    assert set(result["ai"]) == {"vision", "text"}


READ_ONLY_TOOLS = {
    "session_info",
    "get_wardrobe_summary",
    "list_items",
    "get_item",
    "get_item_image",
    "list_outfits",
    "get_outfit",
}


@pytest.mark.asyncio
async def test_read_tools_carry_read_only_hint(mcp_call):
    resp = await mcp_call("tools/list")
    assert resp.status_code == 200, resp.text
    tools = {t["name"]: t for t in resp.json()["result"]["tools"]}
    for name, tool in tools.items():
        read_only = tool.get("annotations", {}).get("readOnlyHint", False)
        assert read_only == (name in READ_ONLY_TOOLS), name
