
# integrations/initial_simply_oauth.py

import asyncio
import logging
import threading
import time

from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue, Empty
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from sqlalchemy import text

from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthToken, OAuthClientMetadata

from langchain_mcp_adapters.client import MultiServerMCPClient

from utils import engine, init_db


# ============================================================
# CONFIGURATION
# ============================================================

SIMPLY_MCP_URL = "https://mcp.simply.com/v2"

CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 3030

REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"

CALLBACK_TIMEOUT = 300

READ_ONLY_TOOLS = {
    "list-accounts",
}

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# ============================================================
# TEMPORARY OAUTH STORAGE
# ============================================================

class MemoryTokenStorage:

    def __init__(self):

        self._tokens = None
        self._client_info = None

    async def get_tokens(self):

        return self._tokens

    async def set_tokens(self, tokens):

        self._tokens = tokens

    async def get_client_info(self):

        return self._client_info

    async def set_client_info(self, client_info):

        self._client_info = client_info


# ============================================================
# CALLBACK SERVER
# ============================================================

callback_queue = Queue()

callback_server = None
callback_thread = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        parsed = urlparse(self.path)

        if parsed.path != "/callback":
            self.send_error(404)
            return

        params = parse_qs(parsed.query)

        result = {
            "code": params.get("code", [None])[0],
            "state": params.get("state", [None])[0],
            "error": params.get("error", [None])[0],
            "error_description": params.get(
                "error_description", [None]
            )[0],
        }

        callback_queue.put(result)

        if result["error"]:

            message = "Authorization failed."

        else:

            message = (
                "Authorization successful. "
                "You can close this browser tab."
            )

        body = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Simply.com OAuth</title>
        </head>
        <body>
            <h2>{message}</h2>
        </body>
        </html>
        """.encode("utf-8")

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.end_headers()

        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


# ============================================================
# OPEN AUTHORIZATION URL
# ============================================================

async def open_authorization_url(url: str):

    global callback_server, callback_thread

    while not callback_queue.empty():

        try:
            callback_queue.get_nowait()

        except Empty:
            break

    try:

        callback_server = HTTPServer(
            (CALLBACK_HOST, CALLBACK_PORT),
            OAuthCallbackHandler,
        )

    except OSError as exc:

        raise RuntimeError(
            f"Cannot start OAuth callback server "
            f"on port {CALLBACK_PORT}."
        ) from exc

    callback_thread = threading.Thread(
        target=callback_server.serve_forever,
        daemon=True,
    )

    callback_thread.start()

    print("\nOpening Simply.com authorization...")
    print(f"Callback: {REDIRECT_URI}")

    import webbrowser

    opened = webbrowser.open(url)

    if not opened:

        print("\nOpen this URL manually:\n")
        print(url)

    print("\nWaiting for authorization...")


# ============================================================
# RECEIVE CALLBACK
# ============================================================

async def get_authorization_callback():

    global callback_server, callback_thread

    try:

        result = await asyncio.to_thread(
            callback_queue.get,
            True,
            CALLBACK_TIMEOUT,
        )

    except Empty:

        raise TimeoutError(
            "OAuth callback timed out."
        )

    finally:

        if callback_server is not None:

            callback_server.shutdown()
            callback_server.server_close()
            callback_server = None

        if callback_thread is not None:

            callback_thread.join(timeout=2)
            callback_thread = None

    if result["error"]:

        raise RuntimeError(
            f"OAuth authorization failed: "
            f"{result['error']}"
        )

    if not result["code"] or not result["state"]:

        raise RuntimeError(
            "OAuth callback is missing code or state."
        )

    logger.info("OAuth callback received successfully.")

    return result["code"], result["state"]


# ============================================================
# SAVE CREDENTIALS TO POSTGRESQL
# ============================================================

def save_oauth_credentials(tokens, client_info):

    if not tokens or not tokens.access_token:
        raise RuntimeError("Missing access token.")

    if not tokens.refresh_token:
        raise RuntimeError("Missing refresh token.")

    if not tokens.expires_in or tokens.expires_in <= 0:
        raise RuntimeError("Invalid token expiration.")

    expires_at = int(
        time.time() + tokens.expires_in
    )

    try:

        with engine.begin() as connection:

            connection.execute(
                text("""
                    INSERT INTO simply_oauth_credentials (
                        id,
                        tokens,
                        client_info,
                        expires_at,
                        updated_at
                    )
                    VALUES (
                        1,
                        CAST(:tokens AS JSONB),
                        CAST(:client_info AS JSONB),
                        :expires_at,
                        NOW()
                    )
                    ON CONFLICT (id)
                    DO UPDATE SET
                        tokens = EXCLUDED.tokens,
                        client_info = EXCLUDED.client_info,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW()
                """),
                {
                    "tokens": tokens.model_dump_json(),
                    "client_info": client_info.model_dump_json(),
                    "expires_at": expires_at,
                },
            )

    except Exception as exc:

        raise RuntimeError(
            "Could not save OAuth credentials to PostgreSQL."
        ) from exc

    logger.info("OAuth credentials saved to PostgreSQL.")

    logger.info(
        "Access token available: %s",
        bool(tokens.access_token),
    )

    logger.info(
        "Refresh token available: %s",
        bool(tokens.refresh_token),
    )

    logger.info(
        "OAuth client ID available: %s",
        bool(client_info.client_id),
    )

    logger.info(
        "Token expiration: %s",
        expires_at,
    )


# ============================================================
# MAIN AUTHORIZATION
# ============================================================

async def main():

    storage = MemoryTokenStorage()

    oauth = OAuthClientProvider(
        server_url=SIMPLY_MCP_URL,

        client_metadata=OAuthClientMetadata(
            client_name="My Account Assistant",

            redirect_uris=[
                AnyUrl(REDIRECT_URI)
            ],

            grant_types=[
                "authorization_code",
                "refresh_token",
            ],

            response_types=["code"],
        ),

        storage=storage,

        redirect_handler=open_authorization_url,

        callback_handler=get_authorization_callback,
    )

    client = MultiServerMCPClient(
        {
            "simplycom": {
                "transport": "streamable_http",
                "url": SIMPLY_MCP_URL,
                "auth": oauth,
            }
        }
    )

    print("=" * 60)
    print("SIMPLY.COM INITIAL OAUTH AUTHORIZATION")
    print("=" * 60)

    print(f"\nConnecting to {SIMPLY_MCP_URL}")

    global callback_server, callback_thread

    try:

        # This initiates authorization when necessary.
        tools = await client.get_tools()

        print("\nAvailable read-only tools:")

        for tool in tools:

            if tool.name in READ_ONLY_TOOLS:

                print(f"- {tool.name}")

        # Retrieve OAuth credentials.
        tokens = await storage.get_tokens()

        client_info = await storage.get_client_info()

        if not tokens or not client_info:

            raise RuntimeError(
                "OAuth completed without storing credentials."
            )

        # Initialize the database if necessary.
        init_db()

        # Persist credentials in PostgreSQL.
        save_oauth_credentials(
            tokens,
            client_info,
        )

    finally:

        if callback_server is not None:

            callback_server.shutdown()
            callback_server.server_close()
            callback_server = None

        if callback_thread is not None:

            callback_thread.join(timeout=2)
            callback_thread = None

    print("\n" + "=" * 60)
    print("INITIAL OAUTH AUTHORIZATION COMPLETED")
    print("=" * 60)

    print("\nCredentials are now stored in PostgreSQL.")


async def run_initial_oauth():
    await main()

if __name__ == "__main__":
    asyncio.run(run_initial_oauth())