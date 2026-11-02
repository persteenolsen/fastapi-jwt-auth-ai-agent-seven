import asyncio
import json
import logging

import httpx


# ============================================================
# CONFIGURATION
# ============================================================

SIMPLY_MCP_URL = "https://mcp.simply.com/v2"

DISCOVERY_TIMEOUT = 20

PROTECTED_RESOURCE_ENDPOINTS = [
    "https://mcp.simply.com/.well-known/oauth-protected-resource/v2",
    "https://mcp.simply.com/.well-known/oauth-protected-resource",
]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# INSPECT OAUTH METADATA
# ============================================================

async def inspect_endpoint(client, url):
    """
    Retrieve and inspect an OAuth metadata endpoint.
    """

    print(f"\nChecking: {url}")

    try:

        response = await client.get(url)

        print("HTTP status:", response.status_code)

        if response.status_code != 200:

            print("Metadata endpoint unavailable.")

            return None

        try:

            data = response.json()

        except ValueError:

            print("Endpoint returned invalid JSON.")

            return None

        if not isinstance(data, dict):

            print("Unexpected metadata format.")

            return None

        print("\nAvailable metadata:")

        metadata_fields = [
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "registration_endpoint",
            "grant_types_supported",
            "response_types_supported",
            "token_endpoint_auth_methods_supported",
            "scopes_supported",
            "code_challenge_methods_supported",
        ]

        for key in metadata_fields:

            if key in data:

                print(f"{key}: {data[key]}")

        return data

    except httpx.HTTPError as exc:

        logger.error(
            "HTTP request failed: %s",
            type(exc).__name__,
        )

        return None

    except Exception:

        logger.exception(
            "Unexpected discovery error."
        )

        return None


# ============================================================
# DISCOVER PROTECTED RESOURCE
# ============================================================

async def discover_protected_resource(client):
    """
    Discover the OAuth authorization servers
    protecting the Simply.com MCP resource.
    """

    print("\n" + "=" * 60)
    print("PROTECTED RESOURCE DISCOVERY")
    print("=" * 60)

    for endpoint in PROTECTED_RESOURCE_ENDPOINTS:

        metadata = await inspect_endpoint(
            client,
            endpoint,
        )

        if metadata is not None:

            return metadata

    return None


# ============================================================
# DISCOVER AUTHORIZATION SERVER
# ============================================================

async def discover_authorization_server(
    client,
    issuer,
):
    """
    Retrieve OAuth authorization server metadata.
    """

    print("\n" + "=" * 60)
    print("AUTHORIZATION SERVER DISCOVERY")
    print("=" * 60)

    print("\nAuthorization server:", issuer)

    metadata_url = (
        issuer.rstrip("/")
        + "/.well-known/oauth-authorization-server"
    )

    return await inspect_endpoint(
        client,
        metadata_url,
    )


# ============================================================
# VALIDATE OAUTH CAPABILITIES
# ============================================================

def validate_oauth_metadata(metadata):
    """
    Check whether the discovered server advertises
    the OAuth capabilities required by this project.
    """

    print("\n" + "=" * 60)
    print("OAUTH CAPABILITY VALIDATION")
    print("=" * 60)

    if not metadata:

        print("No authorization metadata available.")

        return

    authorization_endpoint = metadata.get(
        "authorization_endpoint"
    )

    token_endpoint = metadata.get(
        "token_endpoint"
    )

    grant_types = metadata.get(
        "grant_types_supported",
        [],
    )

    print(
        "\nAuthorization endpoint available:",
        bool(authorization_endpoint),
    )

    print(
        "Token endpoint available:",
        bool(token_endpoint),
    )

    print(
        "Authorization code grant supported:",
        "authorization_code" in grant_types,
    )

    print(
        "Refresh token grant supported:",
        "refresh_token" in grant_types,
    )

    print(
        "\nSupported grant types:",
        grant_types,
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 60)
    print("SIMPLY.COM OAUTH DISCOVERY TEST")
    print("=" * 60)

    print("\nMCP server:", SIMPLY_MCP_URL)

    async with httpx.AsyncClient(
        timeout=DISCOVERY_TIMEOUT,
        follow_redirects=True,
        headers={
            "Accept": "application/json",
        },
    ) as client:

        # ----------------------------------------------------
        # 1. Discover protected resource metadata
        # ----------------------------------------------------

        resource_metadata = (
            await discover_protected_resource(client)
        )

        if resource_metadata is None:

            print(
                "\nCould not retrieve protected resource metadata."
            )

            return

        # ----------------------------------------------------
        # 2. Identify authorization servers
        # ----------------------------------------------------

        authorization_servers = resource_metadata.get(
            "authorization_servers",
            [],
        )

        if not authorization_servers:

            print(
                "\nNo authorization servers found "
                "in protected resource metadata."
            )

            return

        print("\nDiscovered authorization servers:")

        for issuer in authorization_servers:

            print("-", issuer)

        # ----------------------------------------------------
        # 3. Discover authorization server metadata
        # ----------------------------------------------------

        for issuer in authorization_servers:

            metadata = await discover_authorization_server(
                client,
                issuer,
            )

            # ------------------------------------------------
            # 4. Validate OAuth capabilities
            # ------------------------------------------------

            validate_oauth_metadata(metadata)

    # --------------------------------------------------------
    # 5. COMPLETED
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("OAUTH DISCOVERY TEST COMPLETED")
    print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())
