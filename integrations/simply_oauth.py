
# integrations/simply_oauth.py

import asyncio
import json
import logging
import time

import httpx

from sqlalchemy import text

from mcp.shared.auth import OAuthToken

from utils import engine


logger = logging.getLogger(__name__)


# ============================================================
# EXCEPTIONS
# ============================================================

class SimplyOAuthError(Exception):
    pass


class SimplyOAuthRefreshError(SimplyOAuthError):
    pass


class SimplyOAuthPersistenceError(SimplyOAuthError):
    pass


# ============================================================
# OAUTH MANAGER
# ============================================================

class SimplyOAuthManager:

    TOKEN_ENDPOINT = "https://www.simply.com/oauth/token/"

    def __init__(
        self,
        refresh_buffer=120,
        timeout=30,
    ):

        self.refresh_buffer = refresh_buffer
        self.timeout = timeout

        self.tokens = None
        self.client_id = None
        self.expires_at = None

        self._refresh_lock = asyncio.Lock()

        self._load_credentials()

        logger.info("Simply OAuth manager initialized.")

    # ========================================================
    # LOAD CREDENTIALS
    # ========================================================

    def _load_credentials(self):

        with engine.connect() as connection:

            row = connection.execute(
                text("""
                    SELECT tokens, client_info, expires_at
                    FROM simply_oauth_credentials
                    WHERE id = 1
                """)
            ).mappings().first()

        if not row:
           raise SimplyOAuthError(
          "\n"
          "====================================================\n"
          "SIMPLY.COM OAUTH INITIALIZATION REQUIRED\n"
          "====================================================\n"
          "No OAuth credentials were found in PostgreSQL.\n\n"
          "The Simply.com integration has not been authorized yet.\n\n"
          "To fix this, run the following command from your "
          "project root:\n\n"
          "    python -m integrations.initial_simply_oauth\n\n"
          "Complete the authorization in your browser.\n"
          "Then restart FastAPI.\n"
          "===================================================="
        )

        try:

            self.tokens = OAuthToken.model_validate(
                row["tokens"]
            )

            client_info = row["client_info"]

            self.client_id = client_info.get("client_id")

            self.expires_at = float(row["expires_at"])

        except Exception as exc:

            raise SimplyOAuthError(
                "Could not load Simply.com credentials from PostgreSQL."
            ) from exc

        if not self.client_id:
            raise SimplyOAuthError("OAuth client ID is missing.")

        if not self.tokens.access_token:
            raise SimplyOAuthError("Access token is missing.")

        if not self.tokens.refresh_token:
            raise SimplyOAuthError("Refresh token is missing.")

        logger.info("Simply.com credentials loaded from PostgreSQL.")

    # ========================================================
    # TOKEN EXPIRATION
    # ========================================================

    def is_token_expired(self):

        if self.expires_at is None:
            return True

        return (
            time.time() + self.refresh_buffer
            >= self.expires_at
        )

    # ========================================================
    # REFRESH TOKEN
    # ========================================================

    async def _refresh_access_token(self, connection, tokens):

        old_refresh_token = tokens.refresh_token

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": old_refresh_token,
            "client_id": self.client_id,
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        logger.info("Refreshing Simply.com access token.")

        try:

            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    self.TOKEN_ENDPOINT,
                    data=payload,
                    headers=headers,
                )

        except httpx.HTTPError as exc:

            raise SimplyOAuthRefreshError(
                "Could not connect to Simply.com OAuth endpoint."
            ) from exc

        if response.status_code != 200:

            try:
                error_data = response.json()
                error = error_data.get("error", "Unknown OAuth error")
                description = error_data.get("error_description", "")

            except ValueError:
                error = "HTTP error"
                description = ""

            raise SimplyOAuthRefreshError(
                f"Simply.com token refresh failed: {error}. {description}"
            )

        try:
            token_data = response.json()

        except ValueError as exc:

            raise SimplyOAuthRefreshError(
                "Invalid JSON returned by Simply.com."
            ) from exc

        if not token_data.get("access_token"):
            raise SimplyOAuthRefreshError(
                "Refresh response did not contain an access token."
            )

        # Preserve refresh token if the provider does not rotate it.
        if not token_data.get("refresh_token"):
            token_data["refresh_token"] = old_refresh_token

        try:

            new_tokens = OAuthToken.model_validate(token_data)

        except Exception as exc:

            raise SimplyOAuthRefreshError(
                "Could not validate refreshed OAuth credentials."
            ) from exc

        if not new_tokens.refresh_token:
            raise SimplyOAuthRefreshError(
                "Refreshed credentials have no refresh token."
            )

        if not new_tokens.expires_in or new_tokens.expires_in <= 0:
            raise SimplyOAuthRefreshError(
                "Invalid token expiration returned by Simply.com."
            )

        new_expires_at = int(
            time.time() + new_tokens.expires_in
        )

        # ----------------------------------------------------
        # SAVE NEW TOKENS IN POSTGRESQL
        # ----------------------------------------------------

        try:

            connection.execute(
                text("""
                    UPDATE simply_oauth_credentials
                    SET
                        tokens = CAST(:tokens AS JSONB),
                        expires_at = :expires_at,
                        updated_at = NOW()
                    WHERE id = 1
                """),
                {
                    "tokens": new_tokens.model_dump_json(),
                    "expires_at": new_expires_at,
                },
            )

        except Exception as exc:

            raise SimplyOAuthPersistenceError(
                "Could not save refreshed OAuth credentials. "
                "Check PostgreSQL before attempting another refresh."
            ) from exc

        self.tokens = new_tokens
        self.expires_at = new_expires_at

        logger.info("Simply.com tokens refreshed and saved successfully.")

        return new_tokens

    # ========================================================
    # GET VALID ACCESS TOKEN
    # ========================================================

    async def get_access_token(self):

        async with self._refresh_lock:

            try:

                # The transaction and row lock coordinate
                # refresh operations across application workers.
                with engine.begin() as connection:

                    row = connection.execute(
                        text("""
                            SELECT tokens, client_info, expires_at
                            FROM simply_oauth_credentials
                            WHERE id = 1
                            FOR UPDATE
                        """)
                    ).mappings().first()

                    if not row:
                        raise SimplyOAuthError(
                            "Simply.com credentials not found."
                        )

                    # Always use the latest database credentials.
                    tokens = OAuthToken.model_validate(
                        row["tokens"]
                    )

                    client_info = row["client_info"]

                    self.client_id = client_info["client_id"]
                    self.tokens = tokens
                    self.expires_at = float(row["expires_at"])

                    # Another worker may already have refreshed
                    # the token while this worker was waiting.
                    if self.is_token_expired():

                        await self._refresh_access_token(
                            connection,
                            self.tokens,
                        )

                if not self.tokens or not self.tokens.access_token:
                    raise SimplyOAuthError(
                        "No valid access token available."
                    )

                return self.tokens.access_token

            except SimplyOAuthError:
                raise

            except Exception as exc:

                raise SimplyOAuthPersistenceError(
                    "Could not retrieve Simply.com credentials "
                    "from PostgreSQL."
                ) from exc

    # ========================================================
    # RELOAD CREDENTIALS
    # ========================================================

    def reload_credentials(self):

        self._load_credentials()

        logger.info("Simply.com credentials reloaded.")

    # ========================================================
    # TOKEN STATUS
    # ========================================================

    def get_token_info(self):

        expires_in = None

        if self.expires_at is not None:

            expires_in = max(
                0,
                int(self.expires_at - time.time())
            )

        return {
            "authenticated": bool(
                self.tokens and self.tokens.access_token
            ),
            "has_refresh_token": bool(
                self.tokens and self.tokens.refresh_token
            ),
            "expires_at": self.expires_at,
            "expires_in": expires_in,
            "needs_refresh": self.is_token_expired(),
        }



# ========================================================
# TEMPORARY TOKEN REFRESH TEST
# ========================================================

    async def force_refresh_for_testing(self):

        logger.info(
            "Forcing Simply.com token refresh for testing."
        )

        async with self._refresh_lock:

            try:

                with engine.begin() as connection:

                    row = connection.execute(
                        text("""
                            SELECT tokens, client_info, expires_at
                            FROM simply_oauth_credentials
                            WHERE id = 1
                            FOR UPDATE
                        """)
                    ).mappings().first()

                    if not row:
                        raise SimplyOAuthError(
                            "Simply.com credentials not found."
                        )

                    tokens = OAuthToken.model_validate(
                        row["tokens"]
                    )

                    client_info = row["client_info"]

                    self.client_id = client_info["client_id"]

                    # Force refresh using the actual
                    # implementation in this class.
                    await self._refresh_access_token(
                        connection,
                        tokens,
                    )

                logger.info(
                    "Forced token refresh completed."
                )

                return self.get_token_info()

            except SimplyOAuthError:
                raise

            except Exception as exc:

                logger.exception(
                    "Forced token refresh failed."
                )

                raise SimplyOAuthRefreshError(
                    "Token refresh test failed."
                ) from exc
