
# integrations/simply_client.py

import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

from integrations.simply_oauth import SimplyOAuthManager


logger = logging.getLogger(__name__)


SIMPLY_MCP_URL = "https://mcp.simply.com/v2"


ALLOWED_READ_ONLY_TOOLS = {
    "list-accounts",
    "list-subdomains",
}


class SimplyMCPClient:
    """
    Authenticated Simply.com MCP client.

    OAuth credentials are managed by SimplyOAuthManager
    and persisted in PostgreSQL.
    """

    MCP_URL = SIMPLY_MCP_URL

    def __init__(self, oauth_manager: SimplyOAuthManager):

        self.oauth = oauth_manager

        logger.info("SimplyMCPClient initialized.")

    # ========================================================
    # CREATE AUTHENTICATED CLIENT
    # ========================================================

    async def _create_client(self):

        access_token = await self.oauth.get_access_token()

        if not access_token:
            raise RuntimeError(
                "Could not obtain Simply.com access token."
            )

        return MultiServerMCPClient(
            {
                "simplycom": {
                    "transport": "streamable_http",
                    "url": self.MCP_URL,
                    "headers": {
                        "Authorization": f"Bearer {access_token}"
                    },
                }
            }
        )

    # ========================================================
    # DISCOVER TOOLS
    # ========================================================

    async def get_tools(self):

        client = await self._create_client()

        discovered_tools = await client.get_tools()

        discovered_names = {
            tool.name for tool in discovered_tools
        }

        allowed_tools = [
            tool
            for tool in discovered_tools
            if tool.name in ALLOWED_READ_ONLY_TOOLS
        ]

        missing_tools = (
            ALLOWED_READ_ONLY_TOOLS - discovered_names
        )

        logger.info(
            "Simply.com MCP discovered %s tools.",
            len(discovered_tools),
        )

        logger.info(
            "Enabled read-only tools: %s",
            [tool.name for tool in allowed_tools],
        )

        if missing_tools:
            logger.warning(
                "Simply.com tools unavailable: %s",
                sorted(missing_tools),
            )

        return allowed_tools

    # ========================================================
    # CALL TOOL
    # ========================================================

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict | None = None,
    ):

        if tool_name not in ALLOWED_READ_ONLY_TOOLS:
            raise PermissionError(
                f"Simply.com tool is not approved: {tool_name}"
            )

        client = await self._create_client()

        tools = await client.get_tools()

        tool = next(
            (
                item
                for item in tools
                if item.name == tool_name
            ),
            None,
        )

        if tool is None:
            raise RuntimeError(
                f"Simply.com MCP tool not found: {tool_name}"
            )

        logger.info(
            "Calling Simply.com MCP tool: %s",
            tool_name,
        )

        result = await tool.ainvoke(arguments or {})

        logger.info(
            "Simply.com MCP tool completed: %s",
            tool_name,
        )

        return result

    # ========================================================
    # LIST ACCOUNTS
    # ========================================================

    async def list_accounts(self):

        return await self.call_tool("list-accounts")

    # ========================================================
    # LIST SUBDOMAINS
    # ========================================================

    async def list_subdomains(self, domain: str):

        return await self.call_tool(
            "list-subdomains",
            {"domain": domain},
        )

    # ========================================================
    # OAUTH STATUS
    # ========================================================

    def get_oauth_status(self):

        return self.oauth.get_token_info()
